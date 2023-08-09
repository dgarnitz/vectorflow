import sys
import os

# this is needed to import classes from the API. it will be removed when the worker is refactored
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import time
import pika
import json
import openai
import pinecone 
import logging
import worker.config as config
import services.database.batch_service as batch_service
import services.database.job_service as job_service
from shared.embeddings_type import EmbeddingsType
from shared.vector_db_type import VectorDBType
from shared.batch_status import BatchStatus
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.database.database import get_db
from shared.job_status import JobStatus

logging.basicConfig(filename='./log.txt', level=config.LOG_LEVEL)
base_request_url = os.getenv('API_REQUEST_URL') 

def process_batch(batch_id, source_data):
    with get_db() as db:
        batch = batch_service.get_batch(db, batch_id)
        
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
        else:
            logging.error('Unsupported embeddings type:', embeddings_type)
            update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)

def get_openai_embedding(batch, attempts=5):
    for i in range(attempts):
        try:
            response = openai.Embedding.create(
                model= "text-embedding-ada-002",
                input=batch
            )
            if response["data"]:
                return batch, response["data"]
        except Exception as e:
            logging.error('Open AI Embedding API call failed:', e)
            time.sleep(2**i)  # Exponential backoff: 1, 2, 4, 8, 16 seconds.
    return batch, None

def embed_openai_batch(batch, source_data):
    logging.info("Starting Open AI Embeddings")
    openai.api_key = os.getenv('OPEN_AI_KEY')

    chunked_data = chunk_data(source_data, batch.embeddings_metadata.chunk_size, batch.embeddings_metadata.chunk_overlap)
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

def chunk_data(data_chunks, chunk_size, chunk_overlap):
    data = "".join(data_chunks)
    chunks = []
    for i in range(0, len(data), chunk_size - chunk_overlap):
        chunks.append(data[i:i + chunk_size])
    return chunks

def create_openai_batches(batches):
    # Maximum number of items allowed in a batch by OpenAIs embedding API. There is also an 8191 token per item limit
    max_batch_size = config.MAX_OPENAI_EMBEDDING_BATCH_SIZE
    open_ai_batches = [batches[i:i + max_batch_size] for i in range(0, len(batches), max_batch_size)]
    return open_ai_batches

def write_embeddings_to_vector_db(text_embeddings_list, vector_db_metadata, batch_id, job_id):
    if vector_db_metadata.vector_db_type == VectorDBType.PINECONE:
        upsert_list = create_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_pinecone(upsert_list, vector_db_metadata)
    else:
        logging.error('Unsupported vector DB type:', vector_db_metadata.vector_db_type)

def create_source_chunk_dict(text_embeddings_list, batch_id, job_id):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            {"id":f"{job_id}_{batch_id}_{i}", 
            "values": embedding, 
            "metadata": {"source_text": source_text}})
    return upsert_list

def write_embeddings_to_pinecone(upsert_list, vector_db_metadata):
    pinecone_api_key = os.getenv('PINECONE_KEY')
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
    
# These implementations below mock the data service. Using these instead because DB not implement yet
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
        batch_id, source_data = data
        logging.info("Batch retrieved successfully")
        process_batch(batch_id, source_data)
        logging.info("Batch processed successfully")
    except Exception as e:
        logging.error('Error processing batch:', e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

if __name__ == "__main__":
    credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USERNAME'), os.getenv('RABBITMQ_PASSWORD'))

    connection_params = pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST'),
        credentials=credentials
    )

    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()

    queue_name = os.getenv('RABBITMQ_QUEUE')
    channel.queue_declare(queue=queue_name)

    channel.basic_consume(queue=queue_name, on_message_callback=callback)

    logging.info('Waiting for messages.')
    channel.start_consuming()
