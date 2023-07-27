import time
import openai
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.worker.worker import chunk_data, create_openai_batches

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
    text_embeddings_map = dict()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(get_openai_embedding, chunk) for chunk in chunked_data]
        for future in as_completed(futures):
            chunk, embeddings = future.result()
            if not embeddings:
                print(f"Failed to get embedding for chunk {chunk}. Adding batch to retry queue.")
                return
            else:
                for text, embedding in zip(chunk, embeddings):
                    text_embeddings_map[text] = embedding['embedding']
                print(f"Successfully retrieved {len(embeddings)} number of embeddings")
    print(f"Succesfully retrieved {len(text_embeddings_map.values())} vectors for {len(text_embeddings_map.keys())} texts")
    return


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

def test_embed_openai_batch(batch):
    start_time_without_concurrency = time.time()
    embed_openai_batch_without_concurrency(batch)
    end_time_without_concurrency = time.time()
    execution_time_without_concurrency = end_time_without_concurrency - start_time_without_concurrency
    print("EXECUTION TIME WITHOUT CONCURRENCY")
    print(execution_time_without_concurrency)

    start_time_with_concurrency = time.time()
    embed_openai_batch_concurrency(batch)
    end_time_with_concurrency = time.time()
    execution_time_concurrency = end_time_with_concurrency - start_time_with_concurrency
    print("EXECUTION TIME WITH CONCURRENCY")
    print(execution_time_concurrency)

with open('tests/fixtures/test_long_text.txt', 'r') as f:
    file_content = f.read()
    text_array = file_content.split('\n')
    batch = chunk_data(text_array, 256, 128)
    print(f"Preparing to test {len(batch)} vectors")

    open_ai_batches = create_openai_batches(batch)
    print(f"Uploaded in {len(open_ai_batches)} batches")

    test_embed_openai_batch(open_ai_batches)
