#!/bin/bash

echo "Creating namespace..."
kubectl apply -f kube/vectorflow-namespace.yaml

echo "Creating config map.."
kubectl apply -f kube/config-map.yaml

echo "Creating PVCS..."
kubectl apply -f kube/postgres-pvc.yaml
kubectl apply -f kube/minio-pvc.yaml

echo "Deploying initial Deployments..."
kubectl apply -f kube/postgres-deployment.yaml
kubectl apply -f kube/rabbitmq-deployment.yaml
kubectl apply -f kube/minio-deployment.yaml
kubectl apply -f kube/qdrant-deployment.yaml

echo "Deploying initial Services"
kubectl apply -f kube/postgres-service.yaml
kubectl apply -f kube/rabbitmq-service.yaml
kubectl apply -f kube/minio-service.yaml
kubectl apply -f kube/qdrant-service.yaml

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
