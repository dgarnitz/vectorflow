import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from services.minio.minio_service import create_minio_client

bucket = os.getenv("MINIO_BUCKET")
print("Creating minio client")
client = create_minio_client()

print("Creating bucket")
client.make_bucket(bucket)

if client.bucket_exists(bucket):
    print(f"{bucket} bucket exists")
else:
    print(f"{bucket} bucket does not exist")
