from enum import Enum

class ChunkStrategy(Enum):
    EXACT = 'exact'
    EXACT_BY_CHARACTERS = 'exact_by_characters'
    PARAGRAPH = 'paragraph'
    PARAGRAPH_BY_CHARACTERS = 'paragraph_by_characters'
    SENTENCE = 'sentence'
    SENTENCE_BY_CHARACTERS = 'sentence_by_characters'
    CUSTOM = 'custom'