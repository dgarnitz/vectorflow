from enum import Enum

class EmbeddingsTypeClient(Enum):
    OPEN_AI = 'open_ai'
    COHERE = 'cohere'
    SELF_HOSTED = 'self_hosted'
    HUGGING_FACE = 'hugging_face'
    IMAGE = 'image'