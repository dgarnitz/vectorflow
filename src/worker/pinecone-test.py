import pinecone
from vdb_upload_worker import create_pinecone_source_chunk_dict

vector = [0.1]*384
text_embedding_list = [("text", vector)]
upsert_list = create_pinecone_source_chunk_dict(text_embedding_list, 1, 1)

pinecone.init(api_key="70134137-9777-46bb-b853-9bb531056861", environment="us-east-1-aws")
index = pinecone.Index("test-384")
if not index:
   print(f"Index test-384 does not exist in environment us-east-1-aws")

print(f"Starting pinecone upsert for {len(upsert_list)} vectors")

batch_size = 128
vectors_uploaded = 0

for i in range(0,len(upsert_list), batch_size):
    try:
        upsert_response = index.upsert(vectors=upsert_list[i:i+batch_size])
        vectors_uploaded += upsert_response["upserted_count"]
    except Exception as e:
        print('Error writing embeddings to pinecone:', e)

print(f"Successfully uploaded {vectors_uploaded} vectors to pinecone")