import os
from minio import Minio

def create_minio_client():
    return Minio(endpoint=os.getenv("MINIO_ENDPOINT"), 
                access_key=os.getenv("MINIO_ACCESS_KEY"), 
                secret_key=os.getenv("MINIO_SECRET_KEY"), 
                secure=False)