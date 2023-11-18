#!/bin/bash

# Prerequisite checks
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed."
    exit 1
fi

# Try python3 first, then fall back to python
PYTHON_CMD="python3"
if ! command -v $PYTHON_CMD &> /dev/null; then
    PYTHON_CMD="python"
    if ! command -v $PYTHON_CMD &> /dev/null; then
        echo "Error: Neither python3 nor python command found."
        exit 1
    fi
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if [[ "$PYTHON_VERSION" != "3.9" ]]; then
    echo "WARNING: Python 3.9 is required for development and running locally. VectorFlow will run successfully in Docker. We recommend installing pyenv, downloading and setting the local Python to 3.9.9 Found version $PYTHON_VERSION"
fi

echo "Spinning up local VectorFlow. This may take a few minutes."

# Setup env_scripts and .env file
mkdir -p env_scripts
cd env_scripts || exit
touch env_vars.env

# Populate .env file
cat <<EOL > env_vars.env
INTERNAL_API_KEY=test123
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=vectorflow
POSTGRES_HOST=postgres
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_HOST=rabbitmq
EXTRACTION_QUEUE=extraction
EMBEDDING_QUEUE=embeddings
VDB_UPLOAD_QUEUE=vdb-upload
LOCAL_VECTOR_DB=qdrant
API_STORAGE_DIRECTORY=/tmp
MINIO_ACCESS_KEY=minio99
MINIO_SECRET_KEY=minio123
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=vectorflow
EOL

# Populate env_vars.sh file
cat <<EOL > env_vars.sh
#!/bin/bash
export INTERNAL_API_KEY=test123
export POSTGRES_USERNAME=postgres
export POSTGRES_PASSWORD=password
export POSTGRES_DB=vectorflow
export POSTGRES_HOST=postgres
export RABBITMQ_USERNAME=guest
export RABBITMQ_PASSWORD=guest
export RABBITMQ_HOST=rabbitmq
export EXTRACTION_QUEUE=extraction
export EMBEDDING_QUEUE=embeddings
export RETRY_QUEUE=retry
export VDB_UPLOAD_QUEUE=vdb-upload
export LOCAL_VECTOR_DB=qdrant
export API_STORAGE_DIRECTORY=/tmp
export MINIO_ACCESS_KEY=minio99
export MINIO_SECRET_KEY=minio123
export MINIO_ENDPOINT=minio:9000
export MINIO_BUCKET=vectorflow

# Optional keys for external services
export OPEN_AI_KEY=your_open_ai_key
export QDRANT_KEY=your_qdrant_key
export MILVUS_KEY=your_milvus_key
export PINECONE_KEY=your_pinecone_key
export WEAVIATE_KEY=your_weaviate_key
EOL

echo "Environment variables set. Pulling required Docker images."

# Download dependencies
docker pull rabbitmq
docker pull postgres
docker pull qdrant/qdrant
docker pull minio/minio

echo "Building and running VectorFlow via docker-compose"

# Build and start the application
docker-compose build --no-cache
docker-compose up -d

echo "Setup complete."
