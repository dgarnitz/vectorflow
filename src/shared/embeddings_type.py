from enum import Enum

class EmbeddingsType(Enum):
    OPEN_AI = 'open_ai'
    COHERE = 'cohere'
    ANTHROPIC = 'anthropic'
    SELF_HOSTED = 'self_hosted'