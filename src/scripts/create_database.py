import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from sqlalchemy import create_engine
from models.base import Base, engine
#from models import Batch, Job, EmbeddingsMetadata, VectorDBMetadata
import models.batch 
import models.job
import models.vector_db_metadata
import models.embeddings_metadata


def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()
