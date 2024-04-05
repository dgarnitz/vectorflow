from enum import Enum

from shared.vectorflow_request import VectorflowRequest
from shared.embeddings_type import EmbeddingsType


class Validations(Enum):
    CRED = 'CRED'
    METADATA = 'METADATA'
    METADATA2 = 'METADATA2'
    EMBEDDING_TYPE = 'EMBEDDING_TYPE'
    WEBHOOK = 'WEBHOOK'
    SOURCE_DATA = 'SOURCE_DATA'
    HAS_FILES = 'HAS_FILES'
    PRE_SIGNED = 'PRE_SIGNED'


class RequestValidator:
    def __init__(self, request, auth):
        self.request = request
        self.auth = auth
        self.vfr = VectorflowRequest._from_flask_request(request)

    DISPATCH_ERROR_MAP = {
        Validations.CRED: ('Invalid credentials', 401),
        Validations.METADATA: ('Missing required fields', 400),
        Validations.METADATA2: ('Missing required fields', 400),
        Validations.EMBEDDING_TYPE: ('Hugging face embeddings models require a "hugging_face_model_name" in the "embeddings_metadata"', 400),
        Validations.WEBHOOK: ('Webhook URL provided but no webhook key', 400),
        Validations.SOURCE_DATA: ('No file part in the request', 400),
        Validations.HAS_FILES: ('No file part in the request', 400),
        Validations.PRE_SIGNED: ('Missing required fields', 400),
    }

    def validate(self, validatees: list[str] | tuple[str]):
        VRF_VALIDATION_MAP = {
            Validations.CRED: self.vfr.vectorflow_key and self.auth.validate_credentials(self.vfr.vectorflow_key),
            Validations.METADATA: self.vfr.embeddings_metadata and self.vfr.vector_db_metadata and (self.vfr.vector_db_key or os.getenv('LOCAL_VECTOR_DB')),
            Validations.METADATA2: self.vfr.vector_db_metadata and (self.vfr.vector_db_key or os.getenv('LOCAL_VECTOR_DB')),
            Validations.EMBEDDING_TYPE: self.vfr.embeddings_metadata.embeddings_type == EmbeddingsType.HUGGING_FACE and self.embeddings_metadata.hugging_face_model_name,
            Validations.WEBHOOK: not self.vfr.webhook_url or self.vfr.webhook_key,
            Validations.SOURCE_DATA: 'SourceData' in self.request.files,
            Validations.HAS_FILES: hasattr(self.request, "files") and self.request.files,
            Validations.PRE_SIGNED: self.request.form.get('PreSignedURL'),
        }
        return next((v for v in validatees if not VRF_VALIDATION_MAP[v]), None)
        
    @staticmethod
    def dispatch_on_invalid(validation, serialize): 
        error_message, status_code = RequestValidator.DISPATCH_ERROR_MAP[validation]
        return serialize({'error': error_message}), status_code