from models.vector_db_metadata import VectorDBMetadata
from shared.utils import str_to_bool

class ImageSearchRequest:
    @staticmethod
    def _from_request(request):
        image_search_request = ImageSearchRequest()
        image_search_request.vectorflow_key = request.headers.get('Authorization')
        image_search_request.vector_db_key = request.headers.get('X-VectorDB-Key')
        image_search_request.webhook_url = request.form.get('WebhookURL')
        image_search_request.return_vectors = str_to_bool(request.form.get('ReturnVectors', False))
        image_search_request.top_k = int(request.form.get('TopK')) if request.form.get('TopK') else 10
        image_search_request.vector_db_metadata = VectorDBMetadata._from_request(request)
        return image_search_request

    @staticmethod
    def _from_dict(image_search_dict):
        image_search_request = ImageSearchRequest()
        image_search_request.vector_db_key = image_search_dict['vector_db_key']
        image_search_request.webhook_url = image_search_dict['webhook_url']
        image_search_request.return_vectors = str_to_bool(image_search_dict.get('return_vectors', False))
        image_search_request.top_k = int(image_search_dict['top_k'])
        image_search_request.vector_db_metadata = VectorDBMetadata._from_dict(image_search_dict['vector_db_metadata'])
        return image_search_request
    
    def serialize(self):
        return {
            'vector_db_key': self.vector_db_key,
            'webhook_url': self.webhook_url,
            'return_vectors': self.return_vectors,
            'top_k': self.top_k,
            'vector_db_metadata': self.vector_db_metadata.serialize()
        }
    
