import sys
import os

# this is needed to import classes from other directories
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import re
import time
import pika
import json
import openai
import requests 
import logging
import worker.config as config
import services.database.batch_service as batch_service
import services.database.job_service as job_service
import tiktoken
from pika.exceptions import AMQPConnectionError
from shared.chunk_strategy import ChunkStrategy
from shared.embeddings_type import EmbeddingsType
from shared.batch_status import BatchStatus
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.database.database import get_db, safe_db_operation
from shared.job_status import JobStatus
from shared.utils import send_embeddings_to_webhook, generate_uuid_from_tuple
from services.rabbitmq.rabbit_service import create_connection_params, publish_message_to_retry_queue

logging.basicConfig(filename='./worker-log.txt', level=logging.INFO)
logging.basicConfig(filename='./worker-errors.txt', level=logging.ERROR)
publish_channel = None
connection = None
consume_channel = None
retry_channel = None

def process_batch(batch_id, source_data, vector_db_key, embeddings_api_key):
    batch = safe_db_operation(batch_service.get_batch, batch_id)
    job = safe_db_operation(job_service.get_job, batch.job_id)

    # NOTE: it can be either because the /embed endpoint sckips the extractor
    if job.job_status == JobStatus.NOT_STARTED or job.job_status == JobStatus.CREATING_BATCHES:
        safe_db_operation(job_service.update_job_status, job.id, JobStatus.PROCESSING_BATCHES)
    
    if batch.batch_status == BatchStatus.NOT_STARTED:
        safe_db_operation(batch_service.update_batch_status, batch.id, BatchStatus.PROCESSING)
    else:
        safe_db_operation(batch_service.update_batch_retry_count, batch.id, batch.retries+1)
        logging.info(f"Retrying batch {batch.id} on job {batch.job_id}.\nAttempt {batch.retries} of {config.MAX_BATCH_RETRIES}")

    batch = safe_db_operation(batch_service.get_batch, batch_id)
    chunked_data: list[dict] = chunk_data(batch, source_data, job)

    embeddings_type = batch.embeddings_metadata.embeddings_type
    if embeddings_type == EmbeddingsType.OPEN_AI:
        try:
            embedded_chunks = embed_openai_batch(batch, chunked_data)
            if embedded_chunks:
                if job.webhook_url and job.webhook_key:
                    logging.info(f"Sending {len(embedded_chunks)} embeddings to webhook {job.webhook_url}")
                    response = send_embeddings_to_webhook(embedded_chunks, job)
                    process_webhook_response(response, job.id, batch.id)
                else:
                    upload_to_vector_db(batch_id, embedded_chunks)  
            else:
                logging.error(f"Failed to get OPEN AI embeddings for batch {batch.id}. Adding batch to retry queue.")
                update_batch_status(batch.job_id, BatchStatus.FAILED, batch.id, batch.retries)
                
                if batch.retries < config.MAX_BATCH_RETRIES:
                    logging.info(f"Adding Batch {batch.id} of job {batch.job_id} to retry queue.\nCurrent attempt {batch.retries} of {config.MAX_BATCH_RETRIES}")
                    json_data = json.dumps((batch_id, source_data, vector_db_key, embeddings_api_key))
                    publish_message_to_retry_queue(retry_channel, os.getenv('RETRY_QUEUE'), json_data)
                else:
                    logging.error(f"Max retries reached for batch {batch.id} for job {batch.job_id}.\nBATCH will be marked permanent as FAILED.")

        except Exception as e:
            logging.error('Error embedding batch: %s', e)
            update_batch_status(batch.job_id, BatchStatus.FAILED, batch.id)

            if batch.retries < config.MAX_BATCH_RETRIES:
                logging.info(f"Adding Batch {batch.id} of job {batch.job_id} to retry queue.\nCurrent attempt {batch.retries} of {config.MAX_BATCH_RETRIES}")
                json_data = json.dumps((batch_id, source_data, vector_db_key, embeddings_api_key))
                publish_message_to_retry_queue(retry_channel, os.getenv('RETRY_QUEUE'), json_data)
            else:
                logging.error(f"Max retries reached for batch {batch.id} for job {batch.job_id}.\nBATCH will be marked permanent as FAILED.")
    
    elif embeddings_type == EmbeddingsType.HUGGING_FACE:
        try:
            embed_hugging_face_batch(batch, chunked_data)
        except Exception as e:
            logging.error('Error embedding batch: %s', e)
            update_batch_status(batch.job_id, BatchStatus.FAILED, batch.id)

            if batch.retries < config.MAX_BATCH_RETRIES:
                logging.info(f"Adding Batch {batch.id} of job {batch.job_id} to retry queue.\nCurrent attempt {batch.retries} of {config.MAX_BATCH_RETRIES}")
                json_data = json.dumps((batch_id, source_data, vector_db_key, embeddings_api_key))
                publish_message_to_retry_queue(retry_channel, os.getenv('RETRY_QUEUE'), json_data)
            else:
                logging.error(f"Max retries reached for batch {batch.id} for job {batch.job_id}.\nBATCH will be marked permanent as FAILED.")
    else:
        logging.error('Unsupported embeddings type: %s', embeddings_type.value)
        update_batch_status(batch.job_id, BatchStatus.FAILED, batch.id, bypass_retries=True)      

# NOTE: this method will embed mulitple chunks (a list of strings) at once and return a list of lists of floats (a list of embeddings)
# NOTE: this assumes that the embedded chunks are returned in the same order the raw chunks were sent
def get_openai_embedding(chunks, attempts=5):
    batch_of_text_chunks = [chunk['text'] for chunk in chunks]
    for i in range(attempts):
        try:
            response = openai.Embedding.create(
                model= "text-embedding-ada-002",
                input=batch_of_text_chunks
            )
            if response["data"]:
                return chunks, response["data"]
        except Exception as e:
            logging.error('Open AI Embedding API call failed: %s', e)
            time.sleep(2**i)  # Exponential backoff: 1, 2, 4, 8, 16 seconds.
    return batch_of_text_chunks, None

def embed_openai_batch(batch, chunked_data):
    logging.info(f"Starting Open AI Embeddings for batch {batch.id} of job {batch.job_id}")
    openai.api_key = os.getenv('EMBEDDING_API_KEY')
    
    # Maximum number of items allowed in a batch by OpenAIs embedding API. There is also an 8191 token per item limit
    open_ai_batches = create_batches_for_embedding(chunked_data, max_batch_size=config.MAX_OPENAI_EMBEDDING_BATCH_SIZE)
    embedded_chunks: list[dict] = []

    with ThreadPoolExecutor(max_workers=config.MAX_THREADS_OPENAI) as executor:
        futures = [executor.submit(get_openai_embedding, chunk) for chunk in open_ai_batches]
        for future in as_completed(futures):
            chunks, embeddings = future.result()
            if embeddings is not None:
                for chunk, embedding in zip(chunks, embeddings):
                    chunk['vector'] = embedding['embedding']
                    embedded_chunks.append(chunk)
            else:
                logging.error(f"Failed to get Open AI embedding for chunk. Adding batch to retry queue.")
                return None
    
    logging.info("Open AI Embeddings completed successfully")
    return embedded_chunks

def publish_to_embedding_queue(batch_id, batch_of_chunks: list[dict], model_name, attempts=5):
    for _ in range(attempts):
        try:
            embedding_channel = connection.channel() 
            embedding_channel.queue_declare(queue=model_name)

            try:
                serialized_data = json.dumps((batch_id, batch_of_chunks, os.getenv('VECTOR_DB_KEY')))
            except (TypeError, ValueError) as e:
                # this will propagate up and be logged
                logging.error('Error serializing chunks to JSON: %s', e)
                raise e

            embedding_channel.basic_publish(exchange='',
                                        routing_key=model_name,
                                        body=serialized_data)
            logging.info(f"Message published to open source queue {model_name} successfully")
            return
        except pika.exceptions.AMQPConnectionError as e:
            logging.error('ERROR connecting to RabbitMQ, retrying now. See exception: %s', e)
            time.sleep(config.PIKA_RETRY_INTERVAL)
    
    # TODO: implement logic to handle partial failures & retries
    with get_db() as db:
        batch_service.update_batch_status(db, batch_id, BatchStatus.FAILED)
        logging.error(f"Failed to publish batch {batch_id} to open source queue {model_name} after {attempts} attempts.")

def embed_hugging_face_batch(batch, chunked_data):
    logging.info(f"Starting Hugging Face Embeddings with {batch.embeddings_metadata.hugging_face_model_name}")
    hugging_face_batches = create_batches_for_embedding(chunked_data, config.HUGGING_FACE_BATCH_SIZE)
    
    safe_db_operation(batch_service.update_batch_minibatch_count, batch.id, len(hugging_face_batches))
    
    for batch_of_chunks in hugging_face_batches:
        publish_to_embedding_queue(batch.id, batch_of_chunks, batch.embeddings_metadata.hugging_face_model_name)

def chunk_data(batch, source_data, job):
    if batch.embeddings_metadata.chunk_strategy == ChunkStrategy.EXACT:
        chunked_data = chunk_data_exact(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)

    elif batch.embeddings_metadata.chunk_strategy == ChunkStrategy.EXACT_BY_CHARACTERS:
        chunked_data = chunk_data_exact_by_characters(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)

    elif batch.embeddings_metadata.chunk_strategy == ChunkStrategy.PARAGRAPH:
        chunked_data = chunk_data_by_paragraph(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)

    elif batch.embeddings_metadata.chunk_strategy == ChunkStrategy.PARAGRAPH_BY_CHARACTERS:
        chunked_data = chunk_data_by_paragraph_by_characters(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)

    elif batch.embeddings_metadata.chunk_strategy == ChunkStrategy.SENTENCE:
        chunked_data = chunk_by_sentence(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)

    elif batch.embeddings_metadata.chunk_strategy == ChunkStrategy.SENTENCE_BY_CHARACTERS:
        chunked_data = chunk_by_sentence_by_characters(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)
    
    elif batch.embeddings_metadata.chunk_strategy == ChunkStrategy.CUSTOM:
        try:
            from custom_chunker import chunker
            chunked_data = chunker(source_data)
            validate_chunked_data(chunked_data)
        except ImportError:
            logging.error("Failed to import chunker from custom_chunker.py")
        except ChunkedDataValidationError as e:
            logging.error("Failed to validate chunked data: %s", e)
            chunked_data = None
    
    else:
        chunked_data = chunk_data_exact(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)

    if hasattr(job, 'chunk_validation_url') and job.chunk_validation_url:
        chunked_data = validate_chunks(chunked_data, job.chunk_validation_url)

    if not chunked_data:
        update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)
        raise Exception("Failed to chunk data") 
    return chunked_data

def validate_chunks(chunked_data, chunk_validation_url):
    try:
        response = requests.post(
            chunk_validation_url, 
            json={"chunks": chunked_data}, 
            headers={"Content-Type": "application/json"},
            timeout=config.VALIDATION_TIMEOUT 
        )

        if response.status_code == 200 and response.json()['valid_chunks']:
            return response.json()['valid_chunks']
        else:
            logging.error(f"Chunk validation failed for url {chunk_validation_url}")
            return None
    except requests.exceptions.Timeout:
        logging.error(f"Chunk validation timed out for url {chunk_validation_url}.")
        return None

class ChunkedDataValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)

def validate_chunked_data(chunked_data):
    # Check if chunked_data is a list of dictionaries
    if not isinstance(chunked_data, list) or not all(isinstance(item, dict) for item in chunked_data):
        raise ChunkedDataValidationError("chunked_data must be a list of dictionaries")

    # Check if every dictionary in the list has a "text" key
    for item in chunked_data:
        if "text" not in item:
            raise ChunkedDataValidationError("Each dictionary in chunked_data must have a 'text' key")

def chunk_data_exact(data_chunks, chunk_size, chunk_overlap):
    # Encodes data as tokens for the purpose of counting. 
    data = "".join(data_chunks)
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(data)

    chunks: list[dict] = []
    # Tracks token position in the text and takes chunks of the appropriate size. Decodes token chunks to return the original text covered by the token chunk.
    # Overlap is handled by the step size in the loop.
    for i in range(0, len(tokens), chunk_size - chunk_overlap):
        token_chunk = tokens[i:i + chunk_size]
        raw_chunk = encoding.decode(token_chunk)
        chunk_id = generate_uuid_from_tuple((raw_chunk, i, "exact"))
        chunk = {'text': raw_chunk, 'chunk_id': chunk_id}
        chunks.append(chunk)

    return chunks

def chunk_data_exact_by_characters(data_chunks, chunk_size, chunk_overlap):
    data = "".join(data_chunks)
    chunks = []
    for i in range(0, len(data), chunk_size - chunk_overlap):
        text = data[i:i + chunk_size]
        chunk_id = generate_uuid_from_tuple((text, i, "exact"))
        chunk = {'text': text, 'chunk_id': chunk_id}
        chunks.append(chunk)
    
    return chunks

# TODO: this splits by two new lines - '\n\n' - but it should also account for paragraphs split by one - '\n
def chunk_data_by_paragraph(data_chunks, chunk_size, overlap, bound=0.75):
    data = "".join(data_chunks)
    encoding = tiktoken.get_encoding("cl100k_base")
    
    # Ensure the paragraph character isn't searched outside of the bound
    check_bound = int(bound * chunk_size)
    paragraph_chunks = []
    paragraphs = re.split('\n\n', data)
    tokenized_paragraphs = [encoding.encode(paragraph) for paragraph in paragraphs]
    start_idx = 0
    
    # iterate through each paragraph, adding them together until the length is within the bound
    # the bound being the minimum length in tokens that the paragraph(s) must have
    while start_idx < len(tokenized_paragraphs):
        current_tokens = []
        
        # adding paragraphs until it is long enough to satisfy the bound
        while len(current_tokens) < check_bound and start_idx < len(tokenized_paragraphs):
            current_tokens.extend(tokenized_paragraphs[start_idx])
            start_idx += 1
        
        # if the length is greater than the max chunk size, break it down into exact blocks
        if len(current_tokens) > chunk_size:
            current_text = encoding.decode(current_tokens)
            chunk = chunk_data_exact([current_text], chunk_size, overlap)
            paragraph_chunks.extend(chunk)
        else:
            current_text = encoding.decode(current_tokens)
            chunk_id = generate_uuid_from_tuple((current_text, start_idx, "exact"))
            chunk = {'text': current_text, 'chunk_id': chunk_id}
            paragraph_chunks.append(chunk)

    return paragraph_chunks

def chunk_data_by_paragraph_by_characters(data_chunks, chunk_size, overlap, bound=0.75):
    data = "".join(data_chunks)
    total_length = len(data)
    chunks = []
    check_bound = int(bound * chunk_size)
    start_idx = 0

    while start_idx < total_length:
        # Set the end index to the minimum of start_idx + default_chunk_size or total_length
        end_idx = min(start_idx + chunk_size, total_length)

        # Find the next paragraph index within the current chunk and bound
        next_paragraph_index = data.find('\n\n', start_idx + check_bound, end_idx)

        # If a next paragraph index is found within the current chunk
        if next_paragraph_index != -1:
            # Update end_idx to include the paragraph delimiter
            end_idx = next_paragraph_index + 2

        text = data[start_idx:end_idx + overlap]
        chunk_id = generate_uuid_from_tuple((text, start_idx, "exact"))
        chunk = {'text': text, 'chunk_id': chunk_id}
        chunks.append(chunk)

        # Update start_idx to be the current end_idx
        start_idx = end_idx

    return chunks

def chunk_by_sentence(data_chunks, chunk_size, overlap):
    # Split by periods, question marks, exclamation marks, and ellipses
    data = "".join(data_chunks)

    # The regular expression is used to find series of charaters that end with one the following chaacters (. ! ? ...)
    sentence_endings = r'(?<=[.!?…]) +'
    sentences = re.split(sentence_endings, data)
    encoding = tiktoken.get_encoding("cl100k_base")

    sentence_chunks: list[dict] = []
    for i, sentence in enumerate(sentences):
        tokenized_sentence = encoding.encode(sentence)
        if len(tokenized_sentence) > chunk_size:
            chunks = chunk_data_exact([sentence], chunk_size, overlap)
            sentence_chunks.extend(chunks)
        else:
            chunk_id = generate_uuid_from_tuple((sentence, i, "sentence"))
            chunk = {'text': sentence, 'chunk_id': chunk_id}
            sentence_chunks.append(chunk)

    return sentence_chunks

def chunk_by_sentence_by_characters(data_chunks, chunk_size, overlap):
    # Split by periods, question marks, exclamation marks, and ellipses
    data = "".join(data_chunks)
    # The regular expression is used to find series of charaters that end with one the following chaacters (. ! ? ...)
    sentence_endings = r'(?<=[.!?…]) +'
    sentences = re.split(sentence_endings, data)

    sentence_chunks: list[dict] = []
    for i, sentence in enumerate(sentences):
        if len(sentence) > chunk_size:
            chunks = chunk_data_exact_by_characters([sentence], chunk_size, overlap)
            sentence_chunks.extend(chunks)
        else:
            chunk_id = generate_uuid_from_tuple((sentence, i, "sentence"))
            chunk = {'text': sentence, 'chunk_id': chunk_id}
            sentence_chunks.append(chunk)

    return sentence_chunks

def create_batches_for_embedding(chunks, max_batch_size):
    embedding_batches = [chunks[i:i + max_batch_size] for i in range(0, len(chunks), max_batch_size)]
    return embedding_batches

# TODO: refactor into utils
def update_batch_status(job_id, batch_status, batch_id, retries = None, bypass_retries=False):
    try:
        updated_batch_status = safe_db_operation(batch_service.update_batch_status, batch_id, batch_status)
        logging.info(f"Status for batch {batch_id} as part of job {job_id} updated to {updated_batch_status}") 
        if updated_batch_status == BatchStatus.FAILED and (retries == config.MAX_BATCH_RETRIES or bypass_retries):
            logging.info(f"Batch {batch_id} failed. Updating job status.")
            update_batch_and_job_status(job_id, BatchStatus.FAILED, batch_id)     
    except Exception as e:
        logging.error('Error updating batch status: %s', e)

def upload_to_vector_db(batch_id, text_embeddings_list):
    try:
        serialized_data = json.dumps((batch_id, text_embeddings_list, os.getenv('VECTOR_DB_KEY')))
        publish_channel.basic_publish(exchange='',
                                      routing_key=os.getenv('VDB_UPLOAD_QUEUE'),
                                      body=serialized_data)
        logging.info("Message published successfully")
    except Exception as e:
        logging.error('Error publishing message to RabbitMQ: %s', e)
        raise e

def process_webhook_response(response, job_id, batch_id):
    if response and hasattr(response, 'status_code') and response.status_code == 200:
        update_batch_and_job_status(job_id, BatchStatus.COMPLETED, batch_id)
    else:
        logging.error("Error sending embeddings to webhook. Response: %s", response)
        update_batch_and_job_status(job_id, BatchStatus.FAILED, batch_id)
        if response.json() and response.json()['error']:
            logging.error("Error message: %s", response.json()['error'])

# TODO: refactor into utils
def update_batch_and_job_status(job_id, batch_status, batch_id):
    try:
        if not job_id and batch_id:
            job = safe_db_operation(batch_service.get_batch, batch_id)
            job_id = job.job_id
        updated_batch_status = safe_db_operation(batch_service.update_batch_status, batch_id, batch_status)
        job = safe_db_operation(job_service.update_job_with_batch, job_id, updated_batch_status)
        if job.job_status == JobStatus.COMPLETED:
            logging.info(f"Job {job_id} completed successfully")
        elif job.job_status == JobStatus.PARTIALLY_COMPLETED:
            logging.info(f"Job {job_id} partially completed. {job.batches_succeeded} out of {job.total_batches} batches succeeded")
        elif job.job_status == JobStatus.FAILED:
            logging.info(f"Job {job_id} failed. {job.batches_succeeded} out of {job.total_batches} batches succeeded")
                
    except Exception as e:
        logging.error('Error updating job and batch status: %s', e)
        safe_db_operation(job_service.update_job_status, job_id, JobStatus.FAILED)

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        batch_id, source_data, vector_db_key, embeddings_api_key = data

        if vector_db_key:
            os.environ["VECTOR_DB_KEY"] = vector_db_key
        else:
            logging.info("No vector db key provided")
        
        if embeddings_api_key:
            os.environ["EMBEDDING_API_KEY"] = embeddings_api_key
        else:
            logging.info("No embeddings api key provided")

        logging.info("Batch retrieved successfully")
        process_batch(batch_id, source_data, vector_db_key, embeddings_api_key)
        logging.info("Batch processing finished. Check status BatchStatus for results")
    except Exception as e:
        logging.error('Error processing batch: %s', e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection(max_retries=5, retry_delay=5):
    global publish_channel
    global connection
    global consume_channel
    global retry_channel

    for attempt in range(max_retries):
        try:
            connection_params = create_connection_params()
            connection = pika.BlockingConnection(connection_params)
            consume_channel = connection.channel()
            publish_channel = connection.channel()
            retry_channel = connection.channel()

            consume_queue_name = os.getenv('EMBEDDING_QUEUE')
            publish_queue_name = os.getenv('VDB_UPLOAD_QUEUE')
            retry_queue_name = os.getenv('RETRY_QUEUE') 

            consume_channel.queue_declare(queue=consume_queue_name)
            publish_channel.queue_declare(queue=publish_queue_name)
            retry_channel.queue_declare(queue=retry_queue_name)

            consume_channel.basic_consume(queue=consume_queue_name, on_message_callback=callback)

            logging.info('Waiting for messages.')
            consume_channel.start_consuming()
            return  # If successful, exit the function

        except AMQPConnectionError as e:
            logging.error('AMQP Connection Error: %s', e)
        except Exception as e:
            logging.error('Unexpected error: %s', e)
        finally:
            if connection and not connection.is_closed:
                connection.close()

        logging.info('Retrying to connect in %s seconds (Attempt %s/%s)', retry_delay, attempt + 1, max_retries)
        time.sleep(retry_delay)

    raise Exception('Failed to connect after {} attempts'.format(max_retries))

if __name__ == "__main__":
    while True:
        try:
            start_connection()
        except Exception as e:
            logging.error('Error in start_connection: %s', e)
            logging.info('Restarting start_connection after encountering an error.')
            time.sleep(config.PIKA_RETRY_INTERVAL)
