import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import time
import requests
import openai
import pinecone 
from src.api.embeddings_type import EmbeddingsType
from src.api.vector_db_type import VectorDBType
from src.api.batch_status import BatchStatus
from concurrent.futures import ThreadPoolExecutor, as_completed

base_request_url = os.getenv('API_REQUEST_URL') 

def process_batch(batch):
    embeddings_type = batch['embeddings_metadata']['embeddings_type']
    if embeddings_type == EmbeddingsType.OPEN_AI.value:
        try:
            vectors_uploaded = embed_openai_batch(batch)
            update_job_status(batch['job_id'], BatchStatus.COMPLETED, batch['batch_id']) if vectors_uploaded else update_job_status(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])
        except Exception as e:
            print('Error embedding batch:', e)
            update_job_status(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])
    else:
        print('Unsupported embeddings type:', embeddings_type)
        update_job_status(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])

def get_openai_embedding(chunk, attempts=5):
    for i in range(attempts):
        try:
            response = openai.Embedding.create(
                model= "text-embedding-ada-002",
                input=chunk
            )
            if response["data"][0]["embedding"]:
                return chunk, response["data"][0]["embedding"]
        except Exception as e:
            print('Open AI Embedding API call failed:', e)
            time.sleep(2**i)  # Exponential backoff: 1, 2, 4, 8, 16 seconds.
    return chunk, None

def embed_openai_batch(batch):
    print("Starting Open AI Embeddings")
    openai.api_key = os.getenv('OPEN_AI_KEY')
    chunked_data = chunk_data(batch['source_data'], batch['embeddings_metadata']['chunk_size'], batch['embeddings_metadata']['chunk_overlap'])
    text_embeddings_map = dict()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(get_openai_embedding, chunk) for chunk in chunked_data]
        for future in as_completed(futures):
            chunk, embedding = future.result()
            if embedding is not None:
                text_embeddings_map[chunk] = embedding
            else:
                print(f"Failed to get embedding for chunk {chunk}. Adding batch to retry queue.")
                update_job_status(batch['job_id'], BatchStatus.Failed, batch['batch_id'])
                return
    print("Open AI Embeddings completed successfully")
    return write_embeddings_to_vector_db(text_embeddings_map, batch['vector_db_metadata'], batch['batch_id'], batch['job_id']) 

def chunk_data(data_chunks, chunk_size, chunk_overlap):
    data = "".join(data_chunks)
    chunks = []
    for i in range(0, len(data), chunk_size - chunk_overlap):
        chunks.append(data[i:i + chunk_size])
    return chunks

def write_embeddings_to_vector_db(text_embeddings_map, vector_db_metadata, batch_id, job_id):
    if vector_db_metadata['vector_db_type'] == VectorDBType.PINECONE.value:
        upsert_list = create_source_chunk_dict(text_embeddings_map, batch_id, job_id)
        return write_embeddings_to_pinecone(upsert_list, vector_db_metadata)
    else:
        print('Unsupported vector DB type:', vector_db_metadata['vector_db_type'])

def create_source_chunk_dict(text_embeddings_map, batch_id, job_id):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_map.items()):
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
        print(f"Index {vector_db_metadata['index_name']} does not exist in environment {vector_db_metadata['environment']}")
        return None
    
    print("Starting pinecone upsert")
    try:
        vectors_uploaded = index.upsert(vectors=upsert_list)
        print(f"Successfully uploaded {vectors_uploaded} vectors to pinecone")
        return vectors_uploaded
    except Exception as e:
        print('Error writing embeddings to pinecone:', e)
        return None
    
# this implementation mocks the data service. Using this instead because DB not implement yet
def update_job_status(job_id, batch_status, batch_id):
    headers = {"Content-Type": "application/json", "VectorFlowKey": os.getenv('INTERNAL_API_KEY')}
    data = {
        "batch_id": batch_id,
        "batch_status": batch_status.value,
    }
    response = requests.put(f"{base_request_url}/jobs/{job_id}", headers=headers, json=data)
    print(f"Response status: {response.status_code}")

    # TODO: implement webhook callback logic - can pass it back in the response and call it with the response code

if __name__ == "__main__":
    while True:
        headers = {"VectorFlowKey": os.getenv('INTERNAL_API_KEY')}
        response = requests.get(f"{base_request_url}/dequeue", headers=headers)
        if response.status_code == 404:
            print("Queue Empty - Sleeping for 5 seconds")
            time.sleep(5)
        elif response.status_code == 200:
            batch = response.json()['batch']
            print("Batch retrieved successfully")
            process_batch(batch)
            print("Batch processed successfully")
        elif response.status_code == 401:
            print('Invalid credentials')
        else:
            print('Unexpected status code:', response.status_code)


