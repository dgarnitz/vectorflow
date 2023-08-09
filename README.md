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
This current version is an MVP and should not be used in production yet.

VectorFlow is an open source, high throughput, fault tolerant vector embedding pipeline. With a simple API request, you can send raw data that will be embedded and stored in any vector database or returned back to you. 

## Request & Response Payload
All requests require an HTTP Header with `VectorFlowKey` key and a your `INTERNAL_API_KEY` env var as the value. 

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
# Getting Started
## Run VectorFlow Locally
The api and the worker each have their own virtual environments which you must set up - `python -m venv venv  `. Install the `requirements.txt` for each app into the venv. Run both from the `src` directory.

The api can be run locally with `python api/app.py`. 

The worker can be run with `python worker/worker.py`. 

## Environment Variables
The following must all be set:
```
INTERNAL_API_KEY
OPEN_AI_KEY
PINECONE_KEY
POSTGRES_USERNAME
POSTGRES_PASSWORD
POSTGRES_DB
POSTGRES_HOST=postgres
RABBITMQ_USERNAME
RABBITMQ_PASSWORD
RABBITMQ_HOST
RABBITMQ_QUEUE
```

## Database 
The database can also be run locally. We recommend using postgres but SQL Alchemy allows it to work with any flavor of SQL. 
```
docker pull postgres
docker run --network=vectorflow --name postgres -e POSTGRES_PASSWORD=yourpassword -e POSTGRES_DB=vectorflow -p 5432:5432 -d postgres
```

Then run the `create_database.py` script to create the tables. 

## Rabbit MQ
This project uses RabbitMQ as its message broker. We recommend running it through Docker. Run the following to set up.

```
docker pull rabbitmq
docker run -d --network vectorflow --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:management

```

You can check the RabbitMQ management console at `http://localhost:15672/`', which is useful for monitoring and debugging.

## Docker
You must have Docker installed locally. First create a `docker network` for the images to run on so the workers can communicate with the api. 
```
docker network create vectorflow
```

Then build the docker images with these commands:
```
docker build --file api/Dockerfile -t vectorflow_api:latest .
docker build --file worker/Dockerfile -t vectorflow_worker:latest . 
```
Create an `.env` file with the environment variables - you will pass this file into the containers when they run. For example:
```
POSTGRES_DB=vectorflow
```

Run the containers locally with these commands:
```
docker run -d -p 8000:8000 --network vectorflow --name=vectorflow_api --env-file=path/to/.env vectorflow_api:latest 

docker run --network=vectorflow --name=vectorflow_worker -d --env-file=path/to.env vectorflow_worker:latest
```

# How to Deploy
We recommend deploying using the Docker images available in our [public repo.](https://hub.docker.com/repository/docker/dgarnitz/vectorflow/general). The api runs with `gunicorn` and needs a port open to accept active connections.  

# How to Test
Api tests are run from the `api` directory (`vectorflow/src/api`) and can be run with:
```
python -m unittest tests.test_app
python -m unittest tests.test_app.TestApp.test_method_you_wish_to_test
```

Worker tests are run from the `src` directory with the `worker` prefix, for example:
```
python -m unittest src.worker.tests.test_worker
```

# Contributing
We love feedback from the community. If you have an idea of how to make this project better, we encourage you to open an issue or join our Discord. Please tag `dgarnitz` and `danmeier2`.

Our roadmap is outlined in the section below and we would love help in building it out. We recommend you open an issue with a proposed approach in mind before submitting a PR.

Please tag `dgarnitz` on all PRs. 

# Roadmap
- [ ] Connectors to other vector databases such as Weaviate, Milvus, Chroma, Deeplake and Vespa
- [ ] Support for more files types such as `csv`, `word`, `xls`, etc
- [ ] Support for multi-file, directory data ingestion from sources such as S3, Google docs, etc
- [ ] SQL support with SQL Alchemy & Alembic for persistent storage of job & batch information
- [ ] Turn shared objects in Api into package
- [ ] Add stand alone Queue, like SQS or RabbitMQ, with interface to make it technology agnostic
- [ ] Retry mechanism
- [ ] DLQ mechanism
- [ ] Cron job to detect failed and hanging jobs
- [ ] Support for key & secret management
- [ ] Langchain & Llama Index integrations
- [ ] Support for object metadata store and application logic
- [ ] 

# Acknowledgements

[//]: contributor-faces
