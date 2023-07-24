from enum import Enum

class EmbeddingsMetadata:
    def __init__(self, embeddings_type, chunk_size = 256, chunk_overlap = 128, docker_image=None):
        self.embeddings_type = embeddings_type
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.docker_image = docker_image
        self.api_key = None

    def to_dict(self):
        return {
            'embeddings_type': self.embeddings_type.name if isinstance(self.embeddings_type, Enum) else self.embeddings_type,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'docker_image': self.docker_image,
        }