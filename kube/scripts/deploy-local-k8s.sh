#!/bin/bash

echo "Building images from src/ directory. This will take a few minutes"
cd src/
docker build --no-cache --file api/Dockerfile -t vectorflow_api:latest .
docker build --no-cache --file worker/Dockerfile -t vectorflow_worker:latest .
docker build --no-cache --file worker/Dockerfile.vdb-upload-worker -t vectorflow_vdb_upload_worker:latest .
docker build --no-cache --file extract/Dockerfile -t vectorflow_extractor:latest .
docker build --no-cache --file scripts/Dockerfile -t vectorflow-db-init:latest .
docker build --no-cache --file scripts/Dockerfile.minio -t vectorflow-minio-init:latest .
docker build --no-cache --file scripts/Dockerfile.local-qdrant -t vectorflow-qdrant-init:latest .
cd ..

echo "Loading images into minikube. This will take a few minutes"
minikube image load vectorflow_api
minikube image load vectorflow_worker
minikube image load vectorflow_extractor
minikube image load vectorflow_vdb_upload_worker
minikube image load vectorflow-db-init
minikube image load vectorflow-minio-init
minikube image load vectorflow-qdrant-init

echo "Creating namespace..."
kubectl apply -f kube/vectorflow-namespace.yaml

echo "Creating config map.."
kubectl apply -f kube/config-map.yaml

echo "Creating PVCS..."
kubectl apply -f kube/postgres-pvc.yaml
kubectl apply -f kube/minio-pvc.yaml

echo "Deploying initial Services"
kubectl apply -f kube/postgres-service.yaml
kubectl apply -f kube/rabbitmq-service.yaml
kubectl apply -f kube/minio-service.yaml
kubectl apply -f kube/qdrant-service.yaml

echo "Deploying initial Deployments..."
kubectl apply -f kube/postgres-deployment.yaml
kubectl apply -f kube/rabbitmq-deployment.yaml
kubectl apply -f kube/minio-deployment.yaml
kubectl apply -f kube/qdrant-deployment.yaml

echo "Waiting for deployments to be ready..."
kubectl wait -n vectorflow --for=condition=available --timeout=120s deployment/postgres
kubectl wait -n vectorflow --for=condition=available --timeout=120s deployment/rabbitmq
kubectl wait -n vectorflow --for=condition=available --timeout=120s deployment/minio
kubectl wait -n vectorflow --for=condition=available --timeout=120s deployment/qdrant

echo "Deploying resources with init containers..."
kubectl apply -f kube/db-init.yaml
kubectl apply -f kube/qdrant-init.yaml
kubectl apply -f kube/minio-init.yaml

echo "Deploying remaining resources..."
kubectl apply -f kube/api-deployment.yaml
kubectl apply -f kube/extractor-deployment.yaml
kubectl apply -f kube/worker-deployment.yaml
kubectl apply -f kube/vdb-upload-worker-deployment.yaml
kubectl apply -f kube/api-service.yaml

echo "Deployment process completed."
