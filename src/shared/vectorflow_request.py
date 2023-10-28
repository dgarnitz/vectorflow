from models.embeddings_metadata import EmbeddingsMetadata
from models.vector_db_metadata import VectorDBMetadata

class VectorflowRequest:
    @staticmethod
    def _from_flask_request(request):
        vectorflow_request = VectorflowRequest()
        vectorflow_request.vectorflow_key = request.headers.get('Authorization')
        vectorflow_request.vector_db_key = request.headers.get('X-VectorDB-Key')
        vectorflow_request.embedding_api_key = request.headers.get('X-EmbeddingAPI-Key')
        vectorflow_request.webhook_url = request.form.get('WebhookURL')
        vectorflow_request.vector_db_metadata = VectorDBMetadata._from_request(request)
        vectorflow_request.embeddings_metadata = EmbeddingsMetadata._from_request(request)
        vectorflow_request.lines_per_batch = int(request.form.get('LinesPerBatch')) if request.form.get('LinesPerBatch') else 1000
        vectorflow_request.webhook_key = request.headers.get('X-Webhook-Key')
        vectorflow_request.document_id = request.form.get('DocumentID')
        vectorflow_request.chunk_validation_url = request.form.get('ChunkValidationURL')
        return vectorflow_request

    def serialize(self):
        return {
            "vectorflow_key": self.vectorflow_key,
            "vector_db_key": self.vector_db_key,
            "embedding_api_key": self.embedding_api_key,
            "webhook_url": self.webhook_url,
            "vector_db_metadata": self.vector_db_metadata.serialize() if hasattr(self.vector_db_metadata, 'serialize') else None,
            "embeddings_metadata": self.embeddings_metadata.serialize() if hasattr(self.embeddings_metadata, 'serialize') else None,
            "lines_per_batch": self.lines_per_batch,
            "webhook_key": self.webhook_key,
            "document_id": self.document_id,
            "chunk_validation_url": self.chunk_validation_url
        }
    
    @staticmethod
    def _from_dict(data_dict):
        vectorflow_request = VectorflowRequest()
        
        # TODO: refactor this error handling. Python's ternary operator will still try to evaluate the else clause even if the if clause is true
        vectorflow_request.vectorflow_key = data_dict['vectorflow_key'] if 'vectorflow_key' in data_dict else None
        vectorflow_request.vector_db_key = data_dict['vector_db_key'] if 'vector_db_key' in data_dict else None
        vectorflow_request.embedding_api_key = data_dict['embedding_api_key'] if 'embedding_api_key' in data_dict else None
        vectorflow_request.webhook_url = data_dict['webhook_url'] if 'webhook_url' in data_dict else None
        vectorflow_request.vector_db_metadata = VectorDBMetadata._from_dict(data_dict['vector_db_metadata']) if 'vector_db_metadata' in data_dict else None
        vectorflow_request.embeddings_metadata = EmbeddingsMetadata._from_dict(data_dict['embeddings_metadata']) if 'embeddings_metadata' in data_dict else None
        vectorflow_request.lines_per_batch = int(data_dict['LinesPerBatch']) if 'LinesPerBatch' in data_dict else 1000
        vectorflow_request.webhook_key = data_dict['webhook_key'] if 'webhook_key' in data_dict else None
        vectorflow_request.document_id = data_dict["document_id"] if "document_id" in data_dict else None
        vectorflow_request.chunk_validation_url = data_dict["chunk_validation_url"] if "chunk_validation_url" in data_dict else None
        return vectorflow_request
