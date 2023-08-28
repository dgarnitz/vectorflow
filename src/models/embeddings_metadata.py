import json
from sqlalchemy import Column, Integer, String, Enum
from services.database.database import Base
from shared.embeddings_type import EmbeddingsType

class EmbeddingsMetadata(Base):
    __tablename__ = 'embeddings_metadata'

    id = Column(Integer, primary_key=True)
    embeddings_type = Column(Enum(EmbeddingsType))
    chunk_size = Column(Integer)
    chunk_overlap = Column(Integer)
    docker_image = Column(String)

    def serialize(self):
        return {
            'embeddings_type': self.embeddings_type.name if self.embeddings_type else None,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'docker_image': self.docker_image,
        }
    
    @staticmethod
    def _from_request(request):
        embeddings_metadata_dict = json.loads(request.form.get('EmbeddingsMetadata'))
        embeddings_metadata = EmbeddingsMetadata(
            embeddings_type = EmbeddingsType[embeddings_metadata_dict['embeddings_type']], 
            chunk_size = embeddings_metadata_dict['chunk_size'],
            chunk_overlap = embeddings_metadata_dict['chunk_overlap'])
        return embeddings_metadata