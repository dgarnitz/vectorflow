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
  <a href="mailto:dan@getvectorflow.com">Get in touch</a>
</h4>

<div align="center">

[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/aQOlOT14DaA/0.jpg)](https://www.youtube.com/watch?v=aQOlOT14DaA)

</div>

# Introduction

VectorFlow is an open source, high throughput, fault tolerant vector embedding pipeline. With a simple API request, you can send raw data that will be embedded and stored in any vector database or returned back to you.

This current version is an MVP and should not be used in production yet. Right now the system only supports uploading single TXT or PODF files at a time, up to 25 MB.

# Run it Locally

## Docker-Compose

The best way to run VectorFlow is via `docker compose`.

### 1) Set Environment Variables

First create a folder in the root for all the environment variables:

```
mkdir env_scripts
cd env_scripts
touch env_vars.env
```

This creates a file called `env_vars.env` in the `env_scripts` folder to add all the environment variables mentioned below.

```
INTERNAL_API_KEY=your-choice
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=your-choice
POSTGRES_DB=your-choice
POSTGRES_HOST=postgres
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_HOST=rabbitmq
RABBITMQ_QUEUE=your-choice
```

You can choose a variable for `INTERNAL_API_KEY`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `RABBITMQ_QUEUE` freely.

### 2) Run Docker-Compose

If you are running locally, make sure you pull Rabbit MQ and Postgres into your local docker repo:

```
docker pull rabbitmq
docker pull postgres
```

Then run:

```
docker-compose build --no-cache
docker-compose up -d
```

Note that the `db-init` container is running a script that sets up the database schema and will stop after the script completes.

## Using VectorFlow

To use VectorFlow in a live system, make an HTTP request to your API's URL at port 8000 - for example, `localhost:8000` from your development machine, or `vectorflow_api:8000` from within another docker container.

### Request & Response Payload

All requests require an HTTP Header with `Authorization` key which is the same as your `INTERNAL_API_KEY` env var that you defined before (see above). You must pass your vector database api key with the HTTP Header `X-VectorDB-Key` and the embedding api key with `X-EmbeddingAPI-Key`.

VectorFlow currently supports OpenAI ADA embeddings and Pinecone, Qdrant, Weaviate, and Milvus vector databases. 

To check the status of a `job`, make a `GET` request to this endpoint: `/jobs/<int:job_id>/status`. The response will be in the form:

```
{
    'JobStatus': job_status.value
}
```

To submit a `job` for embedding, make a `POST` request to this endpoint: `/embed` with the following payload and the `'Content-Type: multipart/form-data'` header:

```
{
    'SourceData=path_to_txt_file'
    'LinesPerBatch=4096'
    'EmbeddingsMetadata={
        "embeddings_type": "open_ai",
        "chunk_size": 512,
        "chunk_overlap": 128,
        "chunk_strategy": "EXACT | PARAGRAPH | SENTENCE"
    }'
    'VectorDBMetadata={
        "vector_db_type": "PINECONE | QDRANT | WEAVIATE | MILVUS",
        "index_name": "index_name",
        "environment": "env_name"
    }'
}
```

You will get the following payload back:

```
{
    message': f"Successfully added {batch_count} batches to the queue",
    'JobID': job_id
}
```

### Sample Curl Request

The following request will embed a TXT document with OpenAI's ADA model and upload the results to a Pinecone index called `test`. Make sure that your Pinecone index is called `test`. If you run the curl command from the root directory the path to the test_text.txt is `./src/api/tests/fixtures/test_text.txt`, changes this if you want to use another TXT document to embed.

```
curl -X POST -H 'Content-Type: multipart/form-data' -H "Authorization: INTERNAL_API_KEY" -H "X-EmbeddingAPI-Key: your-key-here" -H "X-VectorDB-Key: your-key-here" -F 'EmbeddingsMetadata={"embeddings_type": "open_ai", "chunk_size": 256, "chunk_overlap": 128}' -F 'SourceData=@./src/api/tests/fixtures/test_text.txt' -F 'VectorDBMetadata={"vector_db_type": "pinecone", "index_name": "test", "environment": "us-east-1-aws"}'  http://localhost:8000/embed
```

To check the status of the job,

```
curl -X GET -H "Authorization: INTERNAL_API_KEY" http://localhost:8000/jobs/<job_id>/status
```

### Vector Database Schema Standard
VectorFlow enforces a standardized schema for uploading data to a vector store:
```
id: int
source_data: string
embeddings: float array
```

The id can be used for deduplication and idempotency. Please note for Weaviate, the id is called `vectorflow_id`. We plan to support dynamically detect and/or configurable schemas down the road. 

# Contributing

We love feedback from the community. If you have an idea of how to make this project better, we encourage you to open an issue or join our Discord. Please tag `dgarnitz` and `danmeier2`.

Our roadmap is outlined in the section below and we would love help in building it out. Our open issues are a great place to start and can be viewed [here](https://github.com/dgarnitz/vectorflow/issues). If you want to work on something not listed there, we recommend you open an issue with a proposed approach in mind before submitting a PR.

When submitting a PR, please add units tests to cover the functionality you have added. Please re-run existing tests to ensure there are no regressive bugs. Run from the `src` directory. To run an individual test use:

```
python -m unittest module.tests.test_file.TestClass.test_method
```

To run all the tests in the file use: 
```
python -m unittest module.tests.test_file
``` 

We also recommend you add verification evidence, such as screenshots, that show that your code works in an end to end flow. 

Please tag `dgarnitz` on all PRs. 

# Roadmap

- [ ] Connectors to other vector databases
- [ ] Support for more files types such as `csv`, `word`, `xls`, etc
- [ ] Support for multi-file, directory data ingestion from sources such as Salesforce, Google Drive, etc
- [ ] Support open source embeddings models
- [ ] Retry mechanism
- [ ] Langchain & Llama Index integrations
- [ ] Support callbacks for writing object metadata to a separate store
- [ ] Dynamically configurable vector DB schemas
- [ ] Deduplication capabilities
