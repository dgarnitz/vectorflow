<div align="center">
 <svg width="164" height="164" fill="none" xmlns="http://www.w3.org/2000/svg"><g filter="url(#a)"><rect x="32" y="20" width="100" height="100" rx="16" fill="#1E293B"/><rect x="32.5" y="20.5" width="99" height="99" rx="15.5" stroke="url(#b)"/></g><path d="m109.645 56.269-6.956-4.02m6.956 4.02v6.887m0-6.887-6.956 4.02m-48.697-4.02 6.957-4.02m-6.957 4.02 6.957 4.02m-6.957-4.02v6.887M81.82 72.34l6.956-4.02m-6.956 4.02-6.957-4.02m6.957 4.02v6.888m0 20.662 6.956-4.019m-6.956 4.02v-6.888m0 6.887-6.957-4.019m0-51.657 6.957-4.016 6.956 4.019m20.87 32.715v6.887l-6.956 4.02m-41.74 0-6.957-4.02v-6.887" stroke="url(#c)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><defs><radialGradient id="b" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="matrix(50 0 0 50 82 70)"><stop offset=".472" stop-color="#334155"/><stop offset=".764" stop-color="#94A3B8"/><stop offset="1" stop-color="#334155"/></radialGradient><linearGradient id="c" x1="89.747" y1="31.4" x2="40.821" y2="63.731" gradientUnits="userSpaceOnUse"><stop stop-color="#F1F5F9" stop-opacity=".01"/><stop offset="1" stop-color="#F1F5F9"/></linearGradient><filter id="a" x="0" y="0" width="164" height="164" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feColorMatrix in="SourceAlpha" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"/><feOffset dy="12"/><feGaussianBlur stdDeviation="16"/><feColorMatrix values="0 0 0 0 0.0588235 0 0 0 0 0.0901961 0 0 0 0 0.164706 0 0 0 0.64 0"/><feBlend in2="BackgroundImageFix" result="effect1_dropShadow_127_2"/><feBlend in="SourceGraphic" in2="effect1_dropShadow_127_2" result="shape"/></filter></defs></svg>
    <a href="https://www.getvectorflow.com/">
        <h1>VectorFlow</h1>
    </a>
    <h3>Open source, high-throughput, fault-tolerant vector embedding pipeline</h3>
    <span>Simple API endpoint that ingests large volumes of raw data, processes, and stores or returns the vectors quickly and reliably</span>
</div>
<h4 align="center">
  <a href="https://discord.gg/MEXuahMs2F">Join our Discord</a>  |
  <a href="https://www.getvectorflow.com/">Website</a>  |  
  <a href="mailto:dan@getvectorflow.com">Get in touch</a> |
  <a href="https://vectorflow.dev-docs.dev/docs/">Docs</a> |
  <a href="https://app.getvectorflow.com/">Free Hosted Version</a> 
</h4>

<div align="center">

[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/aQOlOT14DaA/0.jpg)](https://www.youtube.com/watch?v=aQOlOT14DaA)

</div>

# Introduction

VectorFlow is an open source, high throughput, fault tolerant vector embedding pipeline. With a simple API request, you can send raw data that will be chunked, embedded and stored in any vector database or returned back to you. VectorFlow is multi-modal and can ingest both textual and image data. 

This current version is an MVP. We recommend using it with Kubernetes in production (see below for details). For text-based files, it supports TXT, PDF, HTML and DOCX. For image files, it support JPG, JPEG, and PNG. 

# Run it Locally
With three commands you can run VectorFlow locally:
```
git clone https://github.com/dgarnitz/vectorflow.git
cd vectorflow
./setup.sh
```

#### Embed Documents with Client
To start embedding documents locally, [install the VectorFlow Client python library](https://pypi.org/project/vectorflow-client/) in your python application's virtual environment. 
```
pip install vectorflow-client
```
then run the following
```
from vectorflow-client.client.vectorflow import Vectorflow

vectorflow = Vectorflow()
vectorflow.embeddings_api_key = os.getenv("OPEN_AI_KEY")
paths = ['path_to_your_file1', 'path_to_your_file2', ...]
response = vectorflow.upload(paths)
```

You do **not** need to clone the VectorFlow repo to utilize the client functionality via pip. For more instructions see the `README.md` in the `client` directory.

See the appendix for details on how to use the `testing_clients` scripts.

## Docker-Compose

The best way to run VectorFlow is via `docker compose`. If you are running this on Mac, please grant Docker permissions to read from your Documents folder [as instructed here](https://stackoverflow.com/questions/58482352/operation-not-permitted-from-docker-container-logged-as-root). If this fails, remove the `volume` section from the `docker-compose.yml`.

### 1) Set Environment Variables

First create a folder, `env_scripts`, in the root for all the environment variables, then create `env_vars.env` in the `env_scripts` folder to add all the environment variables mentioned below. You only need to set the `LOCAL_VECTOR_DB` variable if you are running qdrant, Milvus or Weaviate locally.  

```
INTERNAL_API_KEY=your-choice
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=your-choice
POSTGRES_DB=vectorflow
POSTGRES_HOST=postgres
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_HOST=rabbitmq
EMBEDDING_QUEUE=embeddings
VDB_UPLOAD_QUEUE=vdb-upload
LOCAL_VECTOR_DB=qdrant | milvus | weaviate
API_STORAGE_DIRECTORY=/tmp
MINIO_ACCESS_KEY=minio99
MINIO_SECRET_KEY=minio123
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=vectorflow
```

You can choose a variable for `INTERNAL_API_KEY`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`, but they must be set.

### 2) Run Docker-Compose

Make sure you pull Rabbit MQ, Postgres, Min.io into your local docker repo. We also recommend running a vector DB in locally, so make sure to pull the image of the one you are using. Our `docker-compose` file will spin up qdrant by default and create two index/collections. If you plan to run Milvus or Weaviate, you will have to configure them on your own. 

```
docker pull rabbitmq
docker pull postgres
docker pull qdrant/qdrant | docker pull milvusdb/milvus | docker pull semitechnologies/weaviate
docker pull minio/minio
```

Then run:

```
docker-compose build --no-cache
docker-compose up -d
```

Note that the `init` containers are running a script that sets up the database schema, vector DB and Min.io object store. These containers stop after the script completes.

### 3) (optional) Configure Sentence Transformer open face models. 
VectorFlow can run any Sentence Transformer model but the `docker-compose` file will not spin it up automatically. Either run `app.py --model_name your-sentence-transformer-model`, or build and run the docker image in `src/hugging_face` with:

```
docker build --file hugging_face/Dockerfile -t vectorflow_hf:latest .
docker run --network=vectorflow --name=vectorflow_hf -d --env-file=/path/to/.env vectorflow_hf:latest --model_name "your_model_name_here"
```

Note that the Sentence Transformer models can be large and take several minutes to download from Hugging Face. VectorFlow does not provision hardware, so you must ensure your hardware has enough RAM/VRAM for the model. By default, VectorFlow will run models on GPU with CUDA if available. 

## Using VectorFlow

The best way to use VectorFlow is with the python client. 

To use VectorFlow for development, make an HTTP request to your API's URL - for example, `localhost:8000` from your development machine, or `vectorflow_api:8000` from within another docker container.

### Request & Response Payload

All requests require an HTTP Header with `Authorization` key which is the same as your `INTERNAL_API_KEY` env var that you defined before (see above). You must pass your vector database api key with the HTTP Header `X-VectorDB-Key` if you are running a connecting to a cloud-based instance of a vector DB, and the embedding api key with `X-EmbeddingAPI-Key` if you are using OpenAI. HuggingFace Sentence Transformer embeddings do not require an api key, but you must follow the above steps to run the container with the model you need. 

VectorFlow currently supports Pinecone, Qdrant, Weaviate, Milvus, Redis, MongoDB and LanceDB vector databases. 

If you are using MongoDB, please note that for the `environment` variable, you will need to pass your MongoDB connection URI, which you can find in your Atlas Console under `Database Deployments->Connect->Drivers`. Your URI should look like `mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority`, where you will replace `<username>` with your username, and pass the string as the environment variable keeping `<password>` as is in the string. For the password, you pass it in the `X-VectorDB-Key` header option.

#### Embed a Single File
To submit a single file for embedding, make a `POST` request to the `/embed` endpoint with a file attached, the `'Content-Type: multipart/form-data'` header and the following payload:

```
{
    'SourceData=path_to_txt_file'
    'LinesPerBatch=4096'
    'EmbeddingsMetadata={
        "embeddings_type": "OPEN_AI | HUGGING_FACE | IMAGE",
        "chunk_size": 512,
        "chunk_overlap": 128,
        "chunk_strategy": "EXACT | PARAGRAPH | SENTENCE | CUSTOM",
        "hugging_face_model_name": "sentence-transformer-model-name-here"
    }'
    'VectorDBMetadata={
        "vector_db_type": "PINECONE | QDRANT | WEAVIATE | MILVUS | REDIS | LANCEDB | MONGODB",
        "index_name": "index_name",
        "environment": "env_name"
    }'
    'DocumentID=your-optional-internal-tracking-id'
}
```

This will create a `job and you will get the following payload back:

```
{
    message': f"Successfully added {batch_count} batches to the queue",
    'JobID': job_id
}
```

Right now this endpoint only supports uploading single files at a time, up to 25 MB due to timeout issues. Note that it may be deprecated.

#### Embed Multiple Files At Once
To submit multiple files for embedding, make a `POST` request to the `/jobs` endpoint. The payload is the same as for single file embedding except the way you attach multiple files is different:

```
{
    'files=[
        ('file',  ('test_pdf.pdf', open(file1_path, 'rb'), 'application/octet-stream')),
        ('file', ('test_medium_text.txt', open(file2_path, 'rb'), 'application/octet-stream'))
    ]'
}
```
*NOTE:* You must `stream` the files to the endpoint, not send it as a conventional post request or it will fail. 

This endpoint will create one `job` per file uploaded. You will get the following JSON payload back:

```
{   
    'successful_uploads': successfully_uploaded_files,
    'failed_uploads': failed_uploads,
    'empty_files_count': empty_files_count,
    'duplicate_files_count': duplicate_files_count
}
```

Where `successfully_uploaded_files` is a list of tuples containing `(file name, job id)` and `failed_uploads` is a list of file names that failed to upload so you can retry them. 

#### Get a Single Job Status
To check the status of a `job`, make a `GET` request to this endpoint: `/jobs/<int:job_id>/status`. The response will be in the form:

```
{
    'JobStatus': job_status
}
```

#### Get Multiple Job Statuses
To check the status of multiples `job`, make a `POST` request to this endpoint: `/jobs/status`. The request body will be in the form:

```
{
    'JobIDs': job_ids
}
```

and the response will be in the form
```
{
    'Jobs': [{'JobID': job_id, 'JobStatus': job_status}, ...]}
```
There is an example in `testing_clients/get_jobs_by_ids.py`.

### Vector Database Standard Metadata Schema 
VectorFlow enforces a standardized schema for uploading data to a vector store:
```
id: string
source_data: string
source_document: string
embeddings: float array
```

The id can be used for deduplication and idempotency. Please note for Weaviate, the id is called `vectorflow_id`. 

We plan deprecicate this in the near futuer to support dynamically detected and/or configurable schemas down the road. 

### Chunking Schema & Custom Chunking
VectorFlow's built in chunkers count by token not by character. A `chunk` in vectorflow is a dictionary that has the following keys:
```
text: str
vector: list[float]
```

You may run a custom chunker by adding a file, `custom_chunker.py`, with a method, `chunker(source_data: list[str])` to the `src/worker` directory prior to build the docker image for the worker. This chunker must return a list of `chunk` dictionaries that conform to the standard above. 

You can add any keys you want to the `chunk` dictionary as long as its _JSON serializable_, meaning no custom classes or function, datetimes types or circular code references. You can use this custom chunk to then upload metadata to the vector DB with whatever schema you desire. 

### Raw Embeddings Webhook
If you wish to use VectorFlow only for chunking and generating embeddings, pass a `WebhookURL` parameter in the body of the `/embed` request and a `X-Webhook-Key` as a header. VectorFlow assumes a webhook key is required for writing back to any endpoint. The embeddings are sent back along with the source chunks in the `chunk` dictionary outlined above. This is sent as json with the following form:
```
{
    'Embeddings': list[dict],
    'DocumentID': str,
    'JobID': int
}
```

### Chunk Validation Webhook
If you wish to validate which chunks you wish to embed, pass a `ChunkValidationURL` parameter in the body of the `/embed` request. This will send the request with the following json payload, `{"chunks": chunked_data}`, where `chunked_data` is a list of `chunk` dictionaries. It will expected back json containing key `valid_chunks` with a list of valid chunks for embedding. This endpoint will timeout after 30 seconds by default but can be configured in the application code. 

### S3 Endpoint
VectorFlow is integrated with AWS s3. You can pass a pre-signed s3 URL in the body of the HTTP instead of a file. Use the form field `PreSignedURL` and hit the endpoint `/s3`. This endpoint has the same configuration and restrictions as the `/embed` endpoint. 

### Telemetry
VectorFlow uses PostHog to anonymously collect data about usage. This does not collect any personally identifiable information. If you want to disable it though, add the following enviroment variable to your `env_vars.env`:
```
TELEMETRY_DISABLED=True
```

## Kubernetes
You can run VectorFlow locally in Kubernetes with minikube using `./kube/scripts/deploy-local-k8s.sh`, which will apply all the yaml files located in `kube/`. This script will not work if you have not installed docker, minikube and kubectl. 

This script will first build the images locally, then transfer them into minikube. If you want to check what images are available in minikube, run the following:

```
eval $(minikube docker-env)
docker images
```

You will need to run `minikube tunnel` to access the resources located in the cluster from your development machine. The setup script will load the images from your local docker context into minikube's. 

You can use the yaml files in `kube/` as a basis for a production deployment but you will need to customize slightly to the needs of your specific cluster. **Contact us if you need help.**

# Contributing

We love feedback from the community. If you have an idea of how to make this project better, we encourage you to open an issue or join our Discord. Please tag `dgarnitz` and `danmeier2`.

Our roadmap is outlined in the section below and we would love help in building it out. Our open issues are a great place to start and can be viewed [here](https://github.com/dgarnitz/vectorflow/issues). If you want to work on something not listed there, we recommend you open an issue with a proposed approach in mind before submitting a PR.

Please tag `dgarnitz` on all PRs and *update the README* to reflect your changes.

### Testing

When submitting a PR, please add units tests to cover the functionality you have added. Please re-run existing tests to ensure there are no regressive bugs. Run from the `src` directory. To run an individual test use:

```
python -m unittest module.tests.test_file.TestClass.test_method
```

To run all the tests in the file use: 
```
python -m unittest module.tests.test_file
```

For end-to-end testing, it is recommend to build and run using the docker-compose, but take down the container you are altering and run it locally on your development machine. This will avoid the need to constantly rebuild the images and re-run the containers. Make sure to change the environment variables in your development machine terminal to the correct values (i.e. `localhost` instead of `rabbitmq` or `postgres`) so that the docker containers can communicate with your development machine. Once it works locally you can perform a final test with everything in docker-compose.

### Verifying
Please verify that all changes work with docker-compose before opening a PR. 

We also recommend you add verification evidence, such as screenshots, that show that your code works in an end to end flow. 


# Roadmap

- [ ] Support for multi-file, directory data ingestion from sources such as Salesforce, Google Drive, etc
- [ ] Retry mechanism
- [ ] Langchain & Llama Index integrations
- [ ] Support callbacks for writing object metadata to a separate store
- [ ] Dynamically configurable vector DB schemas
- [ ] Deduplication capabilities
- [ ] Vector version control
- [ ] "Smart" chunker
- [ ] "Smart" metadata extractor

# Appendix

## Embed with Testing Scripts
One easy way to use VectorFlow is with the our testing clients, located in `testing_clients/` directory. There are several scripts, with different configurations for qickly uploading data. We recommmend starting with the `testing_clients/standard_upload_client.py` - Running this script will submit a single document to VectorFlow for embedding with Open AI ADA and upload to the local qdrant instance. You can change the values to match your configuration. To upload multiple files at once, use the `testing_clients/streaming_upload_client.py`

Note that the `TESTING_ENV` variable is the equivalent of the `environment` field in the `VectorDBMetadata`, which corresponds to an environment in Pincone, a class in Weaviate, a collection in qdrant, etc. 
The `testing_clients` directory has sample scripts you can follow to run vectorflow. Add your embedding and database keys to the `env_scrips/env_vars.sh` script that was generated and set the `filepath` variable in `testing_clients/standard_upload_client.py` to point to the file you want to embed. Then run:
```
source env_scrips/env_vars.sh
python clients/standard_upload_client.py
```

To upload multiple files at once, use the `testing_clients/streaming_upload_client.py`

See above for a more detailed description of how to manually set up and configure the system. Please note that the `setup` script will not create a development environment on your machine, it only sets up and runs the docker-compose. We do not advise using VectorFlow on Windows. 

## Image Embedding & Similarity Search
VectorFlow can embed images using the [Image2Vec library](https://github.com/christiansafka/img2vec). It will create a 512 dimensional vector by default from any image. You can also perform a Top-K image similarity search. 

### How to Use Image Upload
Send a POST request to the `/images` endpoint to utilize this capability. You pass the same set of fields in `VectorDBMetadata` as you would for the `/embed` or `/s3` endpoints but for `EmbeddingsMetadata` you only need to pass `"embeddings_type": "IMAGE"` 

The `docker-compose` file will not spin this capability up automatically. Either run `app.py --model_name your-sentence-transformer-model`, or build and run the docker image in `src/images` with:

```
docker build --file images/Dockerfile -t vectorflow_image_embedding:latest .
docker run --network=vectorflow --name=vectorflow_image_embedding -d --env-file=/path/to/.env vectorflow_image_embedding:latest
```

Note that the Image2Vec uses the ResNet 18 by default. You can configure it to run larger models with higher dimensionality for more fine-grained embeddings. These take several minutes to download the weights from the source. VectorFlow does not provision hardware, so you must ensure your hardware has enough RAM/VRAM for the model. By default, VectorFlow will run models on GPU with CUDA if available.

### How to Use Image Search
Performing an image similarity search requires running another service. You can build and run it using docker:
```
docker build --file images/Dockerfile.search -t vectorflow_image_search:latest .
docker run --network=vectorflow --name=vectorflow_image_search -d --env-file=/path/to/.env vectorflow_image_search:latest
```

### Request
To perform a search, send a `POST` request to `/images/search` endpoint with an image file attached, the `'Content-Type: multipart/form-data'` header and the following body:
```
{
    'ReturnVectors': boolean,
    'TopK': integer, less than 1000,
    'VectorDBMetadata={
        "vector_db_type": "PINECONE | QDRANT | WEAVIATE | MILVUS | REDIS",
        "index_name": "index_name",
        "environment": "env_name"
    }'
}
```
All requests require an HTTP Header with `Authorization` key which is the same as your `INTERNAL_API_KEY` env var that you defined before (see above). You must pass your vector database api key with the HTTP Header `X-VectorDB-Key` if you are running a connecting to a cloud-based instance of a vector DB. 

### Response
An image similarity search will return a response object containing the top K matches, plus the raw vectors if requested, with of the following form:
```
{
    "similar_images": list of match objects
    "vectors": list of list of floats
}
```
where `match`` objects are defined as:
```
{
    "id": str,
    "score": float,
    "metadata": {"source_document" : str}
}
```