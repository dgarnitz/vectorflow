import sys
import os

# this is needed to import classes from the API. it will be removed when the worker is refactored
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import re
import ssl
import time
import pika
import json
import openai
import pinecone
import requests 
import logging
import uuid
import weaviate
import worker.config as config
import services.database.batch_service as batch_service
import services.database.job_service as job_service
from shared.chunk_strategy import ChunkStrategy
from shared.embeddings_type import EmbeddingsType
from shared.vector_db_type import VectorDBType
from shared.batch_status import BatchStatus
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.database.database import get_db
from shared.job_status import JobStatus
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from pymilvus import Collection, connections

logging.basicConfig(filename='./worker/log.txt', level=logging.INFO)
logging.basicConfig(filename='./worker/error.txt', level=logging.ERROR)

def process_batch(batch_id, source_data):
    with get_db() as db:
        batch = batch_service.get_batch(db, batch_id)
        job = job_service.get_job(db, batch.job_id)

        if job.job_status == JobStatus.NOT_STARTED:
            job_service.update_job_status(db, job.id, JobStatus.IN_PROGRESS)
        
        if batch.batch_status == BatchStatus.NOT_STARTED:
            batch_service.update_batch_status(db, batch.id, BatchStatus.IN_PROGRESS)
        else:
            batch_service.update_batch_retry_count(db, batch.id, batch.retries+1)
            logging.info(f"Retrying batch {batch.id}")

        db.refresh(batch)
        embeddings_type = batch.embeddings_metadata.embeddings_type
        if embeddings_type == EmbeddingsType.OPEN_AI:
            try:
                vectors_uploaded = embed_openai_batch(batch, source_data)
                update_batch_and_job_status(batch.job_id, BatchStatus.COMPLETED, batch.id) if vectors_uploaded else update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)
            except Exception as e:
                logging.error('Error embedding batch:', e)
                update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)
        if embeddings_type == EmbeddingsType.HUGGING_FACE:
            try:
                vectors_uploaded = embed_hugging_face_batch(batch, source_data)
                update_batch_and_job_status(batch.job_id, BatchStatus.COMPLETED, batch.id) if vectors_uploaded else update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)
            except Exception as e:
                logging.error('Error embedding batch:', e)
                update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)
        else:
            logging.error('Unsupported embeddings type:', embeddings_type)
            update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)

# NOTE: this method will embed mulitple chunks (a list of strings) at once and return a list of lists of floats (a list of embeddings)
def get_openai_embedding(batch_of_chunks, attempts=5):
    for i in range(attempts):
        try:
            response = openai.Embedding.create(
                model= "text-embedding-ada-002",
                input=batch_of_chunks
            )
            if response["data"]:
                return batch_of_chunks, response["data"]
        except Exception as e:
            logging.error('Open AI Embedding API call failed:', e)
            time.sleep(2**i)  # Exponential backoff: 1, 2, 4, 8, 16 seconds.
    return batch_of_chunks, None

def embed_openai_batch(batch, source_data):
    logging.info("Starting Open AI Embeddings")
    openai.api_key = os.getenv('EMBEDDING_API_KEY')
    
    chunked_data = chunk_data(batch.embeddings_metadata.chunk_strategy, source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)
    open_ai_batches = create_openai_batches(chunked_data)
    text_embeddings_list = list()

    with ThreadPoolExecutor(max_workers=config.MAX_THREADS_OPENAI) as executor:
        futures = [executor.submit(get_openai_embedding, chunk) for chunk in open_ai_batches]
        for future in as_completed(futures):
            chunk, embeddings = future.result()
            if embeddings is not None:
                for text, embedding in zip(chunk, embeddings):
                    text_embeddings_list.append((text, embedding['embedding']))
            else:
                logging.error(f"Failed to get embedding for chunk {chunk}. Adding batch to retry queue.")
                update_batch_and_job_status(batch.job_id, BatchStatus.Failed, batch.id)
                return
    
    logging.info("Open AI Embeddings completed successfully")
    return write_embeddings_to_vector_db(text_embeddings_list, batch.vector_db_metadata, batch.id, batch.job_id) 

# NOTE: this method will embed one string at a time, not a list of strings, and return a list of floats (a single embedding)
def get_hugging_face_embedding(chunk, hugging_face_model_name, attempts=5):
    for i in range(attempts):
        try:
            model_info_file = os.getenv('HUGGING_FACE_MODEL_FILE')
            if not model_info_file:
                raise Exception("HUGGING_FACE_MODEL_FILE environment variable not set")
            
            with open(model_info_file, 'r') as file:
                model_endpoint_dict = json.load(file)
                hugging_face_endpoint = model_endpoint_dict[hugging_face_model_name]
                url = f"{hugging_face_endpoint}/embeddings"
                response = requests.post(url, data={'batch': chunk})
                json_data = response.json()
                if json_data["data"]:
                    return chunk, json_data["data"]
        except Exception as e:
            logging.error(f"Huggin Face Embedding API call failed for model {hugging_face_model_name}:", e)
            time.sleep(2**i)  # Exponential backoff: 1, 2, 4, 8, 16 seconds.
    if json_data["error"]:
        logging.error(f"Error in Hugging Face Embedding API call for model {hugging_face_model_name}: {json_data['error']}")
    return chunk, None

def embed_hugging_face_batch(batch, source_data):
    logging.info(f"Starting Hugging Face Embeddings with {batch.embeddings_metadata.hugging_face_model_name}")
    
    chunked_data = chunk_data(batch.embeddings_metadata.chunk_strategy, source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)
    text_embeddings_list = list()

    with ThreadPoolExecutor(max_workers=config.HUGGING_FACE_MAX_THREADS) as executor:
        futures = [executor.submit(get_hugging_face_embedding, chunk, batch.embeddings_metadata.hugging_face_model_name) for chunk in chunked_data]
        for future in as_completed(futures):
            chunk, embeddings = future.result()
            if embeddings is not None:
                text_embeddings_list.append((chunk, embeddings))
            else:
                logging.error(f"Failed to get embedding for chunk {chunk}. Adding batch to retry queue.")
                update_batch_and_job_status(batch.job_id, BatchStatus.Failed, batch.id)
                return
    
    logging.info("Hugging Face Embeddings completed successfully")
    return write_embeddings_to_vector_db(text_embeddings_list, batch.vector_db_metadata, batch.id, batch.job_id)

def chunk_data(chunk_strategy, source_data, chunk_size, chunk_overlap):
    if chunk_strategy == ChunkStrategy.EXACT:
        chunked_data = chunk_data_exact(source_data, chunk_size, chunk_overlap)

    elif chunk_strategy == ChunkStrategy.PARAGRAPH:
        chunked_data = chunk_data_by_paragraph(source_data,chunk_size, chunk_overlap)

    # chunk_strategy == ChunkStrategy.SENTENCE:
    else:
        # TODO: Implement logic for if a sentence is greater than the requested character count
        chunked_data = chunk_by_sentence(source_data)
    return chunked_data

def chunk_data_exact(data_chunks, chunk_size, chunk_overlap):
    data = "".join(data_chunks)
    chunks = []
    for i in range(0, len(data), chunk_size - chunk_overlap):
        chunks.append(data[i:i + chunk_size])
    return chunks

def chunk_data_by_paragraph(data_chunks, chunk_size, overlap, bound=0.75):
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

        chunks.append(data[start_idx:end_idx + overlap])

        # Update start_idx to be the current end_idx
        start_idx = end_idx

    return chunks

# TODO: Implement logic for if a sentence is greater than the requested character count
def chunk_by_sentence(data_chunks):
    # Split by periods, question marks, exclamation marks, and ellipses
    data = "".join(data_chunks)

    # The regular expression is used to find series of charaters that end with one the following chaacters (. ! ? ...)
    sentence_endings = r'(?<=[.!?…]) +'
    sentences = re.split(sentence_endings, data)
    return sentences

def create_openai_batches(batches):
    # Maximum number of items allowed in a batch by OpenAIs embedding API. There is also an 8191 token per item limit
    max_batch_size = config.MAX_OPENAI_EMBEDDING_BATCH_SIZE
    open_ai_batches = [batches[i:i + max_batch_size] for i in range(0, len(batches), max_batch_size)]
    return open_ai_batches

def write_embeddings_to_vector_db(text_embeddings_list, vector_db_metadata, batch_id, job_id):
    if vector_db_metadata.vector_db_type == VectorDBType.PINECONE:
        upsert_list = create_pinecone_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_pinecone(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.QDRANT:
        upsert_list = create_qdrant_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_qdrant(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.WEAVIATE:
        return write_embeddings_to_weaviate(text_embeddings_list, vector_db_metadata, batch_id, job_id)
    elif vector_db_metadata.vector_db_type == VectorDBType.MILVUS:
        upsert_list = create_wilvus_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_milvus(upsert_list, vector_db_metadata)
    else:
        logging.error('Unsupported vector DB type:', vector_db_metadata.vector_db_type)

def create_pinecone_source_chunk_dict(text_embeddings_list, batch_id, job_id):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            {"id": generate_uuid_from_tuple((job_id, batch_id, i)), 
            "values": embedding, 
            "metadata": {"source_text": source_text}})
    return upsert_list

def write_embeddings_to_pinecone(upsert_list, vector_db_metadata):
    pinecone_api_key = os.getenv('VECTOR_DB_KEY')
    pinecone.init(api_key=pinecone_api_key, environment=vector_db_metadata.environment)
    index = pinecone.Index(vector_db_metadata.index_name)
    if not index:
        logging.error(f"Index {vector_db_metadata.index_name} does not exist in environment {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting pinecone upsert for {len(upsert_list)} vectors")

    batch_size = config.PINECONE_BATCH_SIZE
    vectors_uploaded = 0

    for i in range(0,len(upsert_list), batch_size):
        try:
            upsert_response = index.upsert(vectors=upsert_list[i:i+batch_size])
            vectors_uploaded += upsert_response["upserted_count"]
        except Exception as e:
            logging.error('Error writing embeddings to pinecone:', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to pinecone")
    return vectors_uploaded

def generate_uuid_from_tuple(t, namespace_uuid='6ba7b810-9dad-11d1-80b4-00c04fd430c8'):
    namespace = uuid.UUID(namespace_uuid)
    name = "-".join(map(str, t))
    unique_uuid = uuid.uuid5(namespace, name)

    return str(unique_uuid)

def create_qdrant_source_chunk_dict(text_embeddings_list, batch_id, job_id):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            PointStruct(
                id=generate_uuid_from_tuple((job_id, batch_id, i)),
                vector=embedding,
                payload={"source_text": source_text}
            )
        )
    return upsert_list

def write_embeddings_to_qdrant(upsert_list, vector_db_metadata):
    qdrant_client = QdrantClient(
        url=vector_db_metadata.environment, 
        api_key=os.getenv('VECTOR_DB_KEY'),
        grpc_port=6334, 
        prefer_grpc=True,
        timeout=5
    )

    index = qdrant_client.get_collection(collection_name=vector_db_metadata.index_name)
    if not index:
        logging.error(f"Collection {vector_db_metadata.index_name} does not exist at cluster URL {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting qdrant upsert for {len(upsert_list)} vectors")

    batch_size = config.PINECONE_BATCH_SIZE

    for i in range(0, len(upsert_list), batch_size):
        try:
            qdrant_client.upsert(
                collection_name=vector_db_metadata.index_name,
                points=upsert_list[i:i+batch_size]
            )
        except Exception as e:
            logging.error('Error writing embeddings to qdrant:', e)
            return None
    
    logging.info(f"Successfully uploaded {len(upsert_list)} vectors to qdrant")
    return len(upsert_list)
    
def write_embeddings_to_weaviate(text_embeddings_list, vector_db_metadata,  batch_id, job_id):
    client = weaviate.Client(
        url=vector_db_metadata.environment,
        auth_client_secret=weaviate.AuthApiKey(api_key=os.getenv('VECTOR_DB_KEY')),
    )

    index = client.schema.get()
    class_list = [class_dict["class"] for class_dict in index["classes"]]
    if not index or not vector_db_metadata.index_name in class_list:
        logging.error(f"Collection {vector_db_metadata.index_name} does not exist at cluster URL {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting Weaviate upsert for {len(text_embeddings_list)} vectors")
    try:
        with client.batch(batch_size=config.PINECONE_BATCH_SIZE, dynamic=True, num_workers=2) as batch:
            for i, (text, vector) in enumerate(text_embeddings_list):
                properties = {
                    "source_data": text,
                    "vectoflow_id": generate_uuid_from_tuple((job_id, batch_id, i))
                }

                client.batch.add_data_object(
                    properties,
                    vector_db_metadata.index_name,
                    vector=vector
                )
    except Exception as e:
        logging.error('Error writing embeddings to weaviate:', e)
        return None
    
    logging.info(f"Successfully uploaded {len(text_embeddings_list)} vectors to Weaviate")
    return len(text_embeddings_list)

def create_wilvus_source_chunk_dict(text_embeddings_list, batch_id, job_id):
    ids = []
    source_texts = []
    embeddings = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        ids.append(generate_uuid_from_tuple((job_id, batch_id, i)))
        source_texts.append(source_text)
        embeddings.append(embedding)
    return [ids, source_texts, embeddings]

def write_embeddings_to_milvus(upsert_list, vector_db_metadata):
    connections.connect("default", 
        uri = vector_db_metadata.environment,
        token = os.getenv('VECTOR_DB_KEY')
    )

    collection = Collection(vector_db_metadata.index_name)
    if not collection:
        logging.error(f"Index {vector_db_metadata.index_name} does not exist in environment {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting Milvus insert for {len(upsert_list)} vectors")
    batch_size = config.PINECONE_BATCH_SIZE
    vectors_uploaded = 0

    for i in range(0,len(upsert_list), batch_size):
        try:
            insert_response = collection.insert(upsert_list[i:i+batch_size])
            vectors_uploaded += insert_response.insert_count
        except Exception as e:
            logging.error('Error writing embeddings to milvus:', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to milvus")
    return vectors_uploaded

def update_batch_and_job_status(job_id, batch_status, batch_id):
    try:
        with get_db() as db:
            updated_batch_status = batch_service.update_batch_status(db, batch_id, batch_status)
            job = job_service.update_job_with_batch(db, job_id, updated_batch_status)
            if job.job_status == JobStatus.COMPLETED:
                logging.info(f"Job {job_id} completed successfully")
            elif job.job_status == JobStatus.PARTIALLY_COMPLETED:
                logging.info(f"Job {job_id} partially completed. {job.batches_succeeded} out of {job.total_batches} batches succeeded")
                
    except Exception as e:
        logging.error('Error updating job and batch status:', e)

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        batch_id, source_data, vector_db_key, embeddings_api_key = data
        os.environ["VECTOR_DB_KEY"] = vector_db_key
        os.environ["EMBEDDING_API_KEY"] = embeddings_api_key

        logging.info("Batch retrieved successfully")
        process_batch(batch_id, source_data)
        logging.info("Batch processed successfully")
    except Exception as e:
        logging.error('Error processing batch:', e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection():
    while True:
        try:
            credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USERNAME'), os.getenv('RABBITMQ_PASSWORD'))

            connection_params = pika.ConnectionParameters(
                host=os.getenv('RABBITMQ_HOST'),
                credentials=credentials,
                port=os.getenv('RABBITMQ_PORT'),
                heartbeat=600,
                ssl_options=pika.SSLOptions(ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)),
                virtual_host="/"
            ) if os.getenv('RABBITMQ_PORT') == "5671" else pika.ConnectionParameters(
                host=os.getenv('RABBITMQ_HOST'),
                credentials=credentials,
                heartbeat=600,
            )

            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()

            queue_name = os.getenv('RABBITMQ_QUEUE')
            channel.queue_declare(queue=queue_name)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)

            logging.info('Waiting for messages.')
            channel.start_consuming()
            
        except Exception as e:
            logging.error('ERROR connecting to RabbitMQ, retrying now. See exception:', e)
            time.sleep(config.PIKA_RETRY_INTERVAL) # Wait before retrying

if __name__ == "__main__":
    start_connection()

