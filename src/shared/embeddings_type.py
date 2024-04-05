from enum import Enum

class EmbeddingsType(Enum):
    OPEN_AI = 'open_ai'
    COHERE = 'cohere'
    JINA = 'jina'
    TITAN = 'titan'