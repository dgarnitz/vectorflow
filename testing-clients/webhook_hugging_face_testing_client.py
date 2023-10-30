import os
import requests
import json

#####################
# Testing Variables #
#####################
filepath = './api/tests/fixtures/test_medium_text.txt'
url = "http://localhost:8000/embed"
embedding_key = os.getenv("OPEN_AI_KEY")
vector_db_key = os.getenv("QDRANT_KEY")
embedding_type="HUGGING_FACE"
vector_db_type = "QDRANT"
index_name = "test-1536" # NOTE: this is not actually needed with the webhook
testing_environment = os.getenv("TESTING_ENV")
internal_api_key = "test123"

##################
# Testing script #
##################

headers = {
    "Authorization": internal_api_key,
    "X-EmbeddingAPI-Key": embedding_key,
    "X-VectorDB-Key": vector_db_key,
    "X-Webhook-Key": "test-webhook-key",
}

data = {
    'EmbeddingsMetadata': json.dumps({
        "embeddings_type": embedding_type, 
        "chunk_size": 256, 
        "chunk_overlap": 128,
        "hugging_face_model_name": "BAAI/bge-small-en"
    }),
    'VectorDBMetadata': json.dumps({
        "vector_db_type": vector_db_type, 
        "index_name": index_name,
        "environment": testing_environment
    }),
    'DocumentID': "test-document-id",
    'WebhookURL': 'http://host.docker.internal:6060/vectors',
    'ChunkValidationURL': 'http://host.docker.internal:6060/validate',
}

files = {
    'SourceData': open(filepath, 'rb')
}

print("sending request")
response = requests.post(
    url, 
    headers=headers, 
    data=data, 
    files=files
)

if response.status_code != 200:
    print(f"Error: {response.text}")
    print(f"Status code: {response.status_code}")
    exit(1)

response_json = response.json()
job_id = response_json['JobID']
print(f"Job ID: {job_id}")

# poll the server for the job status
url = f"http://localhost:8000/jobs/{job_id}/status"
job_status = None
while job_status != "COMPLETED" and job_status != "FAILED":
    headers = {
        "Authorization": internal_api_key,
    }

    response = requests.get(
        url, 
        headers=headers
    )

    response_json = response.json()
    job_status = response_json['JobStatus']

print(f"Job status: {job_status}")
  