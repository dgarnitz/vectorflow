import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from services.minio.minio_service import create_minio_client

print("Creating minio client")
client = create_minio_client()

print("Creating bucket")
client.make_bucket("vectorflow")

if client.bucket_exists("vectorflow"):
    print("vectorflow bucket exists")
else:
    print("vectorflow bucket does not exist")

####### testing - to be deleted #########
# print("Removing an object from minio")
# client.remove_object("vectorflow", "test_pdf.pdf")

# print("Deleting bucket")
# client.remove_bucket("vectorflow")
# if client.bucket_exists("vectorflow"):
#     print("vectorflow bucket exists")
# else:
#     print("vectorflow bucket does not exist")