import os
import requests
import json

#####################
# Testing Variables #
#####################
filepath = '/Users/davidgarnitz/Documents/other/garnitz.jpg'
url = "http://localhost:5000/images/query"
embedding_key = os.getenv("OPEN_AI_KEY")
vector_db_key = os.getenv("PINECONE_KEY")
vector_db_type = "PINECONE"
index_name = "test-512"
testing_environment = os.getenv("TESTING_ENV")

##################
# Testing script #
##################

headers = {
    "Authorization": os.getenv("INTERNAL_API_KEY"),
    "X-EmbeddingAPI-Key": embedding_key,
    "X-VectorDB-Key": vector_db_key,
}

data = {
    'ReturnVectors': False,
    'TopK': 1,
    'VectorDBMetadata': json.dumps({
        "vector_db_type": vector_db_type, 
        "index_name": index_name,
        "environment": testing_environment
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

print("response:", response.json())

  