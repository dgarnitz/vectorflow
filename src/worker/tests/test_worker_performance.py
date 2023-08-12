import time
import openai
import os
import pinecone
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.worker.worker import chunk_data, create_openai_batches, create_pinecone_source_chunk_dict

def get_openai_embedding(chunk, attempts=5):
    for i in range(attempts):
        try:
            response = openai.Embedding.create(
                model= "text-embedding-ada-002",
                input=chunk
            )
            if response["data"][0]["embedding"]:
                return chunk, response["data"]
        except Exception as e:
            print('Open AI Embedding API call failed:', e)
            time.sleep(2**i)  # Exponential backoff: 1, 2, 4, 8, 16 seconds.
    return chunk, None

def embed_openai_batch_concurrency(chunked_data):
    openai.api_key = os.getenv('OPEN_AI_KEY')
    text_embeddings_list = list()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(get_openai_embedding, chunk) for chunk in chunked_data]
        for future in as_completed(futures):
            chunk, embeddings = future.result()
            if not embeddings:
                print(f"Failed to get embedding for chunk {chunk}. Adding batch to retry queue.")
                return
            else:
                for text, embedding in zip(chunk, embeddings):
                    text_embeddings_list.append((text, embedding['embedding']))
                print(f"Successfully retrieved {len(embeddings)} number of embeddings")
    return text_embeddings_list


def embed_openai_batch_without_concurrency(open_ai_batches):
    openai.api_key = os.getenv('OPEN_AI_KEY')
    for i, batch in enumerate(open_ai_batches):
        print(f"testing Batch {i}")
        for i in range(5):
            try:
                response = openai.Embedding.create(
                    model= "text-embedding-ada-002",
                    input=batch
                )
                
                if response["data"]:
                    print(f"Success retrieved {len(response['data'])} number of embeddings without concurrency")
                    break
            except Exception as e:
                print('Open AI Embedding API call failed:', e)
                time.sleep(2**i)  # Exponential backoff: 1, 2, 4, 8, 16 seconds.

                if i == 4:
                    print("Open AI Embedding API call failed after 5 attempts. Adding batch to retry queue.")
                    return
            
            if i == 4:
                    print("Open AI Embedding API call did not return a value for the embeddings after 5 attempts. Adding batch to retry queue.")
                    return
            
    return 

def write_embeddings_to_pinecone(upsert_lists, vector_db_metadata):
    pinecone_api_key = os.getenv('PINECONE_KEY')
    pinecone.init(api_key=pinecone_api_key, environment=vector_db_metadata['environment'])
    index = pinecone.Index(vector_db_metadata['index_name'])
    if not index:
        print(f"Index {vector_db_metadata['index_name']} does not exist in environment {vector_db_metadata['environment']}")
        return None
    
    for upsert_list in upsert_lists:
        print(f"Starting pinecone upsert for {len(upsert_list)} vectors")
        try:
            vectors_uploaded = index.upsert(vectors=upsert_list)
            print(f"Successfully uploaded {vectors_uploaded} vectors to pinecone")
            return vectors_uploaded
        except Exception as e:
            print('Error writing embeddings to pinecone:', e)
            return None
    
def write_embeddings_to_pinecone_concurrent(source_chunks, vector_db_metadata):
    pinecone_api_key = os.getenv('PINECONE_KEY')
    pinecone.init(api_key=pinecone_api_key, environment=vector_db_metadata['environment'])
    index = pinecone.Index(vector_db_metadata['index_name'])
    if not index:
        print(f"Index {vector_db_metadata['index_name']} does not exist in environment {vector_db_metadata['environment']}")
        return None

    vectors_uploaded = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(index.upsert, vectors=item): item for item in source_chunks}
        for future in as_completed(futures):
            try:
                result = future.result()
                vectors_uploaded += result
                print(f"Successfully uploaded vectors to pinecone")
            except Exception as e:
                print('Error writing embeddings to pinecone:', e)
    return vectors_uploaded

def test_embed_openai_batch():
    with open('tests/fixtures/test_long_text.txt', 'r') as f:
        file_content = f.read()
        text_array = file_content.split('\n')
        batch = chunk_data(text_array, 256, 128)
        open_ai_batches = create_openai_batches(batch)

        # without concurrency
        start_time_without_concurrency = time.time()
        embed_openai_batch_without_concurrency(open_ai_batches)
        end_time_without_concurrency = time.time()
        execution_time_without_concurrency = end_time_without_concurrency - start_time_without_concurrency
        print("EXECUTION TIME WITHOUT CONCURRENCY")
        print(execution_time_without_concurrency)

        # with concurrency
        start_time_with_concurrency = time.time()
        embed_openai_batch_concurrency(open_ai_batches)
        end_time_with_concurrency = time.time()
        execution_time_concurrency = end_time_with_concurrency - start_time_with_concurrency
        print("EXECUTION TIME WITH CONCURRENCY")
        print(execution_time_concurrency)

def test_pinecone_concurrently_batch_upload():
    with open('tests/fixtures/test_long_text.txt', 'r') as f:
        file_content = f.read()
        text_array = file_content.split('\n')
        batch = chunk_data(text_array, 256, 128)
       
        # limit to 512 because its below the pinecone size limit but will still test concurrent upload
        # the idea here is to see how small batches affect upload speed
        batch = batch[:128]
        open_ai_batches = create_openai_batches(batch)
        text_embeddings_list = embed_openai_batch_concurrency(open_ai_batches)
        vector_db_metadata = {"index_name": "test", "environment": "us-east-1-aws"}

        # without concurrency
        source_chunks = create_pinecone_source_chunk_dict(text_embeddings_list, "test_batch_id", "test_job_id")
        source_chunks = [source_chunks[:64], source_chunks[64:128]]
        start_time = time.time()
        write_embeddings_to_pinecone(source_chunks, vector_db_metadata)
        end_time = time.time()
        execution_time = end_time - start_time
        print("EXECUTION TIME WITHOUT CONCURRENCY")
        print(execution_time)

        # with concurrency
        source_chunks = create_pinecone_source_chunk_dict(text_embeddings_list, "test_batch_id", "test_job_id")
        source_chunks = [source_chunks[:64], source_chunks[64:128]]

        start_time_concurrent = time.time()
        write_embeddings_to_pinecone_concurrent(source_chunks, vector_db_metadata)
        end_time_concurrent = time.time()
        execution_time_concurrent = end_time_concurrent - start_time_concurrent
        print("EXECUTION TIME WITHCONCURRENCY")
        print(execution_time_concurrent)