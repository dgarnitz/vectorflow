# VectorFlow Python Client
Use this Python client to embed documents with VectorFlow and check on the status of those embeddings. 

### How to Use
The client has 2 methods for uploading documents to embed and 2 for checking statuses, listed below. All four methods return a python `response` object from the python `requests` library. You must parse the response using the `.json()` method. 

#### Initialize
```
from vectorflow_client.vectorflow import Vectorflow

vectorflow = Vectorflow()
vectorflow.embedding_api_key = "YOUR_OPEN_AI_KEY"
```

#### Embed Multiple Files
```
paths = ['./src/api/tests/fixtures/test_pdf.pdf', './src/api/tests/fixtures/test_medium_text.txt']
response = vectorflow.upload(paths)
```

#### Embed a Single File
```
filepath = './src/api/tests/fixtures/test_medium_text.txt'
response = vectorflow.embed(filepath)
```

#### Get Statuses for Multiple Jobs
```
response = vectorflow.get_job_statuses(jobs_ids)
```

#### Get Status for Single Job
```
response = vectorflow.get_job_status(job_id)
```

### Notes on Default Setup
By default, this will set up vectorflow to embed files locally and upload them to a local instance of qdrant. It assumes you follow the default configuration in the VectorFlow repository's `setup.sh` which runs a collection of docker images locally using docker compose that will embed the documents with Open AI's ADA model and upload it to a local qdrant instance. 

For more granular control over the chunking, embedding and vector DB configurations, override default values on the `Vectorflow` class or on its `embeddings_metadata` and `vector_db_metadata` fields. For example:

```
from vectorflow_client.vectorflow import Vectorflow
from vectorflow_client.embeddings_type import EmbeddingsTypeClient
from vectorflow_client.vector_db_type import VectorDBTypeClient

vectorflow = Vectorflow()

# use open source sentence transformer model
vectorflow.embeddings_metadata.hugging_face_model_name = "thenlper/gte-base"
vectorflow.embeddings_metadata.embeddings_type = EmbeddingsTypeClient.HUGGING_FACE

# use Pinecone
vectorflow.vector_db_metadata.vector_db_type = VectorDBTypeClient.PINECONE
vectorflow.vector_db_metadata.environment = "us-east-1-aws"
vectorflow.vector_db_metadata.index_name = "test"
```