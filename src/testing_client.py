import os
import requests
import json

filepath = 'src/api/tests/fixtures/test_medium_text.txt'
url = "http://localhost:8000/embed"
headers = {
    "Authorization": os.getenv("INTERNAL_API_KEY"),
    "X-EmbeddingAPI-Key": os.getenv("OPEN_AI_KEY"),
    "X-VectorDB-Key": os.getenv("QDRANT_KEY"),
}

data = {
    'EmbeddingsMetadata': json.dumps({
        "embeddings_type": "OPEN_AI", 
        "chunk_size": 256, 
        "chunk_overlap": 128
    }),
    'VectorDBMetadata': json.dumps({
        "vector_db_type": "QDRANT", 
        "index_name": "test-1536",
        "environment": os.getenv("TESTING_ENV")
    })
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
while job_status != "COMPLETED" and job_status != "FAILURE":
    headers = {
        "Authorization": os.getenv("INTERNAL_API_KEY"),
    }

    response = requests.get(
        url, 
        headers=headers
    )

    response_json = response.json()
    job_status = response_json['JobStatus']

print(f"Job status: {job_status}")
  