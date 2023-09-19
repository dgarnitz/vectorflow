import os
import requests

url = "https://localhost:8000/embed"
headers = {
    "Content-Type": "multipart/form-data",
    "headers": {
        "Authorization": os.getenv("INTERNAL_API_KEY"),
        "X-EmbeddingAPI-Key": os.getenv("OPEN_AI_KEY"),
        "X-VectorDB-Key": os.getenv("QDRANT_KEY"),
    }
}

data = {
    'EmbeddingsMetadata': {
        "embeddings_type": "OPEN_AI", 
        "chunk_size": 256, 
        "chunk_overlap": 128
        },
    'VectorDBMetadata': {
        "vector_db_type": "QDRANT", 
        "index_name": "test-1536",
        "environment": "https://2221925e-165f-43d1-9244-997fa6a47843.eu-central-1-0.aws.cloud.qdrant.io"
    }
}  

files = {
    'SourceData': open('path/to/file', 'rb')
}

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
url = f"https://localhost:8000/jobs/{job_id}/status"
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
  