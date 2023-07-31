import sys
import os

# this is needed to import classes from the API. it will be removed when the worker is refactored
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import time
import requests
import openai
import pinecone 
import logging
import worker.config as config
from api.embeddings_type import EmbeddingsType
from api.vector_db_type import VectorDBType
from api.batch_status import BatchStatus
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(filename='./log.txt', level=config.LOG_LEVEL)
base_request_url = os.getenv('API_REQUEST_URL') 

def process_batch(batch):
    if batch['batch_status'] == BatchStatus.NOT_STARTED.value:
        update_batch_status(batch['batch_status'], batch['batch_id'])
    else:
        update_batch_retry_count(batch['batch_id'], batch['retries']+1)
        logging.info(f"Retrying batch {batch['batch_id']}")
    
    embeddings_type = batch['embeddings_metadata']['embeddings_type']
    if embeddings_type == EmbeddingsType.OPEN_AI.value:
        try:
            vectors_uploaded = embed_openai_batch(batch)
            update_job_status(batch['job_id'], BatchStatus.COMPLETED, batch['batch_id']) if vectors_uploaded else update_job_status(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])
        except Exception as e:
            logging.error('Error embedding batch:', e)
            update_job_status(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])
    else:
        logging.error('Unsupported embeddings type:', embeddings_type)
        update_job_status(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])

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

def embed_openai_batch(batch):
    logging.info("Starting Open AI Embeddings")
    openai.api_key = os.getenv('OPEN_AI_KEY')

    chunked_data = chunk_data(batch['source_data'], batch['embeddings_metadata']['chunk_size'], batch['embeddings_metadata']['chunk_overlap'])
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
                update_job_status(batch['job_id'], BatchStatus.Failed, batch['batch_id'])
                return
    
    logging.info("Open AI Embeddings completed successfully")
    return write_embeddings_to_vector_db(text_embeddings_list, batch['vector_db_metadata'], batch['batch_id'], batch['job_id']) 

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
    if vector_db_metadata['vector_db_type'] == VectorDBType.PINECONE.value:
        upsert_list = create_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_pinecone(upsert_list, vector_db_metadata)
    else:
        logging.error('Unsupported vector DB type:', vector_db_metadata['vector_db_type'])

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
    pinecone.init(api_key=pinecone_api_key, environment=vector_db_metadata['environment'])
    index = pinecone.Index(vector_db_metadata['index_name'])
    if not index:
        logging.error(f"Index {vector_db_metadata['index_name']} does not exist in environment {vector_db_metadata['environment']}")
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
def update_job_status(job_id, batch_status, batch_id):
    headers = {"Content-Type": "application/json", "VectorFlowKey": os.getenv('INTERNAL_API_KEY')}
    data = {
        "batch_id": batch_id,
        "batch_status": batch_status.value,
    }
    response = requests.put(f"{base_request_url}/jobs/{job_id}", headers=headers, json=data)
    logging.info(f"Response status: {response.status_code}")

def update_batch_status(batch_status, batch_id):
    headers = {"Content-Type": "application/json", "VectorFlowKey": os.getenv('INTERNAL_API_KEY')}
    data = {
        "batch_id": batch_id,
        "batch_status": batch_status.value,
    }
    # response = requests.put(f"{base_request_url}/batch/{batch_id}", headers=headers, json=data)
    # logging.info(f"Response status: {response.status_code}")

def update_batch_retry_count(batch_id, retries):
    headers = {"Content-Type": "application/json", "VectorFlowKey": os.getenv('INTERNAL_API_KEY')}
    data = {
        "batch_id": batch_id,
        "retries": retries,
    }
    # response = requests.put(f"{base_request_url}/batch/{batch_id}", headers=headers, json=data)
    # logging.info(f"Response status: {response.status_code}")

if __name__ == "__main__":
    while True:
        headers = {"VectorFlowKey": os.getenv('INTERNAL_API_KEY')}
        response = requests.get(f"{base_request_url}/dequeue", headers=headers)
        if response.status_code == 404:
            logging.info(f"Queue Empty - Sleeping for {config.SLEEP_SECONDS} second(s)")
            time.sleep(config.SLEEP_SECONDS)
        elif response.status_code == 200:
            batch = response.json()['batch']
            logging.info("Batch retrieved successfully")
            process_batch(batch)
            logging.info("Batch processed successfully")
        elif response.status_code == 401:
            logging.error('Invalid credentials')
        else:
            logging.error('Unexpected status code:', response.status_code)


