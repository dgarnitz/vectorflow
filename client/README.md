# VectorFlow Python Client
Use this Python client to embed documents and upload them to a vector database with VectorFlow. You can also check on the status of those embedding and upload jobs. 

### How to Use
The client has 2 methods for uploading documents to embed and 2 for checking statuses, listed below. All four methods return a python `response` object from the python `requests` library. You must parse the response using the `.json()` method. 

#### Initialize
```
from vectorflow_client.vectorflow import Vectorflow

vectorflow = Vectorflow()
vectorflow.embedding_api_key = "YOUR_OPEN_AI_KEY"
```

#### Embed a Single File
```
filepath = './src/api/tests/fixtures/test_medium_text.txt'
response = vectorflow.embed(filepath)
```
This points at your local VectorFlow instance by default. You can also point at our free hosted version of VectorFlow, which is more performant. Just alter the `base_url` parameter of the embed method and set the `internal api key` from the [managed service.](https://app.getvectorflow.com/home)
```
vectorflow.internal_api_key = 'SWITCHINGKEYS1234567890'
response = vectorflow.embed(filepath, base_url = "https://vectorflowembeddings.online")
```

#### Embed Multiple Files
```
paths = ['./src/api/tests/fixtures/test_pdf.pdf', './src/api/tests/fixtures/test_medium_text.txt']
response = vectorflow.upload(paths)
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

For more granular control over the chunking, embedding and vector DB configurations, override default values on the `Vectorflow` class or on its `embeddings` and `vector_db` fields. For example:

```
from vectorflow_client.vectorflow import Vectorflow
from vectorflow_client.embeddings_type import EmbeddingsType
from vectorflow_client.vector_db_type import VectorDBType

vectorflow = Vectorflow()

# use open source sentence transformer model
vectorflow.embeddings.hugging_face_model_name = "thenlper/gte-base"
vectorflow.embeddings.embeddings_type = EmbeddingsTypeClient.HUGGING_FACE

# use Pinecone
vectorflow.vector_db.vector_db_type = VectorDBType.PINECONE
vectorflow.vector_db.environment = "us-east-1-aws"
vectorflow.vector_db.index_name = "test"
```