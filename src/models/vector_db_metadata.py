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