from models.embeddings_metadata import EmbeddingsMetadata
from models.vector_db_metadata import VectorDBMetadata


class VectorflowRequest:
    def __init__(self, request):
        self.vectorflow_key = request.headers.get('Authorization')
        self.vector_db_key = request.headers.get('X-VectorDB-Key')
        self.embedding_api_key = request.headers.get('X-EmbeddingAPI-Key')
        self.webhook_url = request.form.get('WebhookURL')
        self.vector_db_metadata = VectorDBMetadata._from_request(request)
        self.embeddings_metadata = EmbeddingsMetadata._from_request(request)
        self.lines_per_batch = int(request.form.get('LinesPerBatch')) if request.form.get('LinesPerBatch') else 1000
        self.webhook_key = request.headers.get('X-Webhook-Key')
        self.document_id = request.form.get('DocumentID')
        self.chunk_validation_url = request.form.get('ChunkValidationURL')