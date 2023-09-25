import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

local_vector_db = os.getenv("LOCAL_VECTOR_DB")
client = QdrantClient(local_vector_db, port=6333)

print("creating open ai testing collection with 1536 dimensions")
client.recreate_collection(
    collection_name="test-1536",
    vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
)
print("collection created")

print("verifying collection")
collection = client.get_collection(collection_name="test-1536")
print(collection)

print("creating bge-small-en testing collection with 384 dimensions")
client.recreate_collection(
    collection_name="test-384",
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
)
print("collection created")

print("verifying collection")
collection = client.get_collection(collection_name="test-384")
print(collection)

print("creating image embedding testing collection with 512 dimensions")
client.recreate_collection(
    collection_name="test-512",
    vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
)
print("collection created")

print("verifying collection")
collection = client.get_collection(collection_name="test-512")
print(collection)