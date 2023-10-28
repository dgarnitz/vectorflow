import requests
import os
import json
import time
from get_jobs_by_ids import get_jobs_by_id

url = "http://localhost:8000/jobs"
embedding_key = os.getenv("OPEN_AI_KEY")
internal_api_key = "test123"
embedding_type="OPEN_AI"
vector_db_type = "QDRANT"
index_name = "test-1536"
testing_environment = "qdrant"

# File paths for test files
file1_path = './src/api/tests/fixtures/test_pdf.pdf'
file2_path = './src/api/tests/fixtures/test_medium_text.txt'
file3_path = './src/api/tests/fixtures/test_medium_text.txt'

data = {
    'EmbeddingsMetadata': json.dumps({
        "embeddings_type": embedding_type, 
        "chunk_size": 256, 
        "chunk_overlap": 128
    }),
    'VectorDBMetadata': json.dumps({
        "vector_db_type": vector_db_type, 
        "index_name": index_name,
        "environment": testing_environment
    })
}

# Construct the multi-part form data payload
multipart_form_data = [
    ('file',  ('test_pdf.pdf', open(file1_path, 'rb'), 'application/octet-stream')),
    ('file', ('test_medium_text.txt', open(file2_path, 'rb'), 'application/octet-stream')),
    ('file', ('test_medium_text.txt', open(file3_path, 'rb'), 'application/octet-stream'))
]

headers = {
    "Authorization": internal_api_key,
    "X-EmbeddingAPI-Key": embedding_key
}


# Perform the POST request with streaming
response = requests.post(url, files=multipart_form_data, headers=headers, stream=True, data=data)

print(response.status_code)

response_json = response.json()
print(response_json)

if "successful_uploads" in response_json and len(response_json["successful_uploads"]) > 0:
    jobs_ids = [v for _,v in response_json["successful_uploads"].items()]
    
    time.sleep(5) # wait for processing to complete 
    get_jobs_by_id(jobs_ids)

    time.sleep(5) # wait for processing to complete 
    get_jobs_by_id(jobs_ids)

    time.sleep(5) # wait for processing to complete 
    get_jobs_by_id(jobs_ids)

    time.sleep(5) # wait for processing to complete 
    get_jobs_by_id(jobs_ids)
