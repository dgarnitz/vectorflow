from qdrant_client import QdrantClient
from qdrant_client.http import models

client = QdrantClient("localhost", port=6333)

print("creating collection")
client.recreate_collection(
    collection_name="test",
    vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
)
print("collection created")

print("verifying collection")
collection = client.get_collection(collection_name="test")
print(collection)