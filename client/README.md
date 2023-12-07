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
This points at your local VectorFlow instance by default. You can also point at our free hosted version of VectorFlow, which is more performant. Just set the `base_url` and the `internal_api_key` on the client object, which you can get from [the managed service](https://app.getvectorflow.com/home).
```
vectorflow.internal_api_key = 'SWITCHINGKEYS1234567890'
vectorflow.base_url = "https://vectorflowembeddings.online"

response = vectorflow.embed(filepath)
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
from vectorflow_client.embeddings import Embeddings

vectorflow = Vectorflow(
  internal_api_key = 'SWITCHINGKEYS1234567890',
  vector_db_key = "your-vdb-key" ,
  base_url = "https://vectorflowembeddings.online"
)

# use open source sentence transformer model
embeddings = Embeddings(
  hugging_face_model_name = "thenlper/gte-base"
  embeddings_type = EmbeddingsTypeClient.HUGGING_FACE
)
vectorflow.embeddings = embeddings

# use Pinecone
vector_db = VectorDB(
	vector_db_type = VectorDBType.PINECONE,
	environment = "us-east-1-aws",
	index_name = "test-1536",
)
vectorflow.vector_db = vector_db
```

## Chunk Enhancer
The VectorFlow Client also features a RAG chunk enhancer. It works by passing it a list of chunks, the original source document and a use case describing the kind of searches you will run. It then adds extra relevant contextual information to the end of each chunk based on the use case to help facilitate better similarity searches. 

### Usage

```
from vectorflow_client.chunk_enhancer import ChunkEnhancer
import fitz

usecase = """
I am reviewing academic papers about search and evaluation techniques for large language models to try to utilize them more effectively.
I want to supplement my existing knowledge with state of the art techniques and see if I can apply them to my own work.
I will want to compare and contrast different techniques.
I will also want to learn about the detail technical workings of these, including at a mathematical level.
The purpose of this sytem is to help me while conducting both research and building real world applications using large language models.
"""

enhancer = ChunkEnhancer(usecase=usecase, openai_api_key="your-key")

doc = fitz.open("paper.pdf")
pdf_text = ""
for page in doc:
  pdf_text += page.get_text()

chunk1 = pdf_text[:2048]
chunks = [chunk1]
enhanced_chunks = enhancer.enhance_chunks(chunks, pdf_text)
```