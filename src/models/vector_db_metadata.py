import json
from services.database.database import Base
from sqlalchemy import Column, Integer, String, Enum
from shared.vector_db_type import VectorDBType

class VectorDBMetadata(Base):
    __tablename__ = 'vector_db_metadata'

    id = Column(Integer, primary_key=True, autoincrement=True)
    vector_db_type = Column(Enum(VectorDBType))
    index_name = Column(String)
    environment = Column(String)

    def serialize(self):
        return {
            'vector_db_type': self.vector_db_type.name if self.vector_db_type else None,
            'index_name': self.index_name,
            'environment': self.environment,
        }
    
    @staticmethod
    def _from_request(request):
        vector_db_metadata_dict = json.loads(request.form.get('VectorDBMetadata'))
        vector_db_metadata = VectorDBMetadata(
            vector_db_type = VectorDBType[vector_db_metadata_dict['vector_db_type']], 
            index_name = vector_db_metadata_dict['index_name'], 
            environment = vector_db_metadata_dict['environment'])
        return vector_db_metadata