import os
from enum import Enum
from shared.vectorflow_request import VectorflowRequest
from shared.embeddings_type import EmbeddingsType
from typing import Union

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

    def __init__(self, request, auth):
        self.request = request
        self.auth = auth
        self.vectorflow_request = VectorflowRequest._from_flask_request(request)

    def validate(self, validations_to_check: Union[list[str], tuple[str]]):
        VRF_VALIDATION_MAP = {
            Validations.CRED: self.vectorflow_request.vectorflow_key and self.auth.validate_credentials(self.vectorflow_request.vectorflow_key),
            Validations.METADATA: self.vectorflow_request.embeddings_metadata and self.vectorflow_request.vector_db_metadata and (self.vectorflow_request.vector_db_key or os.getenv('LOCAL_VECTOR_DB')),
            Validations.METADATA2: self.vectorflow_request.vector_db_metadata and (self.vectorflow_request.vector_db_key or os.getenv('LOCAL_VECTOR_DB')),
            Validations.EMBEDDING_TYPE: self.vectorflow_request.embeddings_metadata.embeddings_type in [EmbeddingsType.OPEN_AI], 
            Validations.WEBHOOK: not self.vectorflow_request.webhook_url or self.vectorflow_request.webhook_key,
            Validations.SOURCE_DATA: 'SourceData' in self.request.files,
            Validations.HAS_FILES: hasattr(self.request, "files") and self.request.files,
            Validations.PRE_SIGNED: self.request.form.get('PreSignedURL'),
        }
        return next((validation for validation in validations_to_check if not VRF_VALIDATION_MAP[validation]), None)
        
    @staticmethod
    def dispatch_on_invalid(validation, serialize): 
        # key error 
        error_message, status_code = RequestValidator.DISPATCH_ERROR_MAP[validation]
        return serialize({'error': error_message}), status_code