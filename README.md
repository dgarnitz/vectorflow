<div align="center">
    <a href="https://www.getvectorflow.com/">
        <h1>VectorFlow</h1>
    </a>
    <h3>Open source, high-throughput, fault-tolerant vector embedding pipeline</h3>
    <span>Simple API endpoint that ingests large volumes of raw data, processes, and stores or returns the vectors quickly and reliably</span>
    <br></br>   
</div>
<h4 align="center">
  <a href="https://discord.gg/9VZ3ujWE">Join our Discord</a> |
  <a href="https://infisical.com/docs/documentation/getting-started/introduction">Docs</a> |
  <a href="https://www.infisical.com">Website</a>
    <a href="https://www.infisical.com">Feature Request</a>
    <a href="https://www.infisical.com">Get in touch</a>
</h4>

<div align="center">

[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/aQOlOT14DaA/0.jpg)](https://www.youtube.com/watch?v=aQOlOT14DaA)

</div>



# Introduction
VectorFlow is an open source, high throughput, fault tolerant vector embedding pipeline. With a simple API request, you can send raw data that will be embedded and stored in any vector database or returned back to you. 

This current version is an MVP and should not be used in production yet. Right now the system only supports uploading single TXT files at a time, up to 2GB.

# Run it Locally
## Docker-Compose 
The best way to run VectorFlow is via `docker compose`. Do the following commands
```
mkdir env_scripts
docker-compose build --no-cache
docker-compose up -d
```

Inside `env_scripts` add a file calles `env_vars.env` with the environment variables mentioned below. 

## Environment Variables
The following must all be set. Replace placeholders with real values:
```
INTERNAL_API_KEY=your-choice
OPEN_AI_KEY=put-your-key
PINECONE_KEY=put-your-key
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=your-choice
POSTGRES_DB=your-choice
POSTGRES_HOST=postgres
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_HOST=rabbitmq
RABBITMQ_QUEUE=your-choice
```

Right now we are only supporting pinecone and openai but this will change shortly, so we will be adding more environment variables.

## Using VectorFlow
To use VectorFlow in a live system, make an HTTP request to your API's URL at port 8000 - for example, `localhost:8000` from your development machine, or `vectorflow_api:8000` from within another docker container. 

### Request & Response Payload
All requests require an HTTP Header with `VectorFlowKey` key which is the same as your `INTERNAL_API_KEY` env var that you defined before (see above). 

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
    'LinesPerChunk=4096'
    'EmbeddingsMetadata={
        "embeddings_type": "open_ai", 
        "chunk_size": 512, 
        "chunk_overlap": 128
    }'
    'VectorDBMetadata={
        "vector_db_type": "pinecone", 
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
The following request will embed a TXT document with OpenAI's ADA model and upload the results to a Pinecone index called `Test`
```
curl -X POST -H 'Content-Type: multipart/form-data' -H "VectorFlowKey: INTERNAL_API_KEY" -F 'EmbeddingsMetadata={"embeddings_type": "open_ai", "chunk_size": 256, "chunk_overlap": 128}' -F 'SourceData=@./test_text.txt' -F 'VectorDBMetadata={"vector_db_type": "pinecone", "index_name": "test", "environment": "us-east-1-aws"}'  http://localhost:8000/embed
```

# Contributing
We love feedback from the community. If you have an idea of how to make this project better, we encourage you to open an issue or join our Discord. Please tag `dgarnitz` and `danmeier2`.

Our roadmap is outlined in the section below and we would love help in building it out. We recommend you open an issue with a proposed approach in mind before submitting a PR.

Please tag `dgarnitz` on all PRs. 

# Roadmap
- [ ] Connectors to other vector databases
- [ ] Support for more files types such as `csv`, `word`, `xls`, etc
- [ ] Support for multi-file, directory data ingestion from sources such as S3, Google docs, etc
- [ ] Support open source embeddings models
- [ ] Alembic for database migrations
- [ ] Retry mechanism
- [ ] DLQ mechanism
- [ ] Langchain & Llama Index integrations
- [ ] Support callbacks for writing object metadata to a separate store 

