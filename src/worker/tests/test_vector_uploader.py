import unittest
import worker.worker as worker
from unittest.mock import patch
from models.batch import Batch
from models.job import Job
from models.vector_db_metadata import VectorDBMetadata
from shared.batch_status import BatchStatus
from shared.job_status import JobStatus
from worker.vector_uploader import VectorUploader

class TestVectorUploader(unittest.TestCase):
    def setUp(self):
         self.uploader = VectorUploader()

    @patch('worker.worker.upload_to_vector_db')
    @patch('sqlalchemy.orm.session.Session.refresh')
    @patch('services.database.batch_service.update_batch_status_with_successful_minibatch')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.vector_uploader.VectorUploader.write_embeddings_to_vector_db')
    @patch('worker.vector_uploader.VectorUploader.update_batch_and_job_status')
    def test_process_upload_batch_success(
        self, 
        mock_update_batch_and_job_status, 
        mock_write_embeddings_to_vector_db, 
        mock_get_batch, 
        mock_get_job, 
        mock_safe_db_operation,
        mock_update_job_status,
        mock_update_batch_status_with_successful_minibatch,
        mock_db_refresh,
        mock_upload_to_vector_db):
        # arrange
        text_embedding_list = [("this is a test", [1.0, 2.0, 3.0, 4.0, 5.0])]
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED)
        batch = Batch(id=1, 
                      job_id=1, 
                      batch_status=BatchStatus.PROCESSING, 
                      vector_db_metadata=VectorDBMetadata())
        mock_write_embeddings_to_vector_db.return_value = 1
        mock_update_batch_status_with_successful_minibatch.return_value = BatchStatus.COMPLETED
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act
        self.uploader.upload_batch(batch, text_embedding_list)

        # assert
        mock_write_embeddings_to_vector_db.assert_called_once_with(text_embedding_list, batch.vector_db_metadata, batch.id, batch.job_id)
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.COMPLETED, batch.id)

    @patch('worker.worker.upload_to_vector_db')
    @patch('sqlalchemy.orm.session.Session.refresh')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.vector_uploader.VectorUploader.write_embeddings_to_vector_db')
    @patch('worker.vector_uploader.VectorUploader.update_batch_and_job_status')
    def test_process_upload_batch_failure(
        self, 
        mock_update_batch_and_job_status, 
        mock_write_embeddings_to_vector_db, 
        mock_get_batch, 
        mock_get_job, 
        mock_safe_db_operation,
        mock_update_job_status,
        mock_update_batch_status,
        mock_db_refresh,
        mock_upload_to_vector_db):
        # arrange
        text_embedding_list = [("this is a test", [1.0, 2.0, 3.0, 4.0, 5.0])]
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED)
        batch = Batch(id=1, 
                      job_id=1, 
                      batch_status=BatchStatus.PROCESSING, 
                      vector_db_metadata=VectorDBMetadata())
        mock_write_embeddings_to_vector_db.return_value = 0
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act
        self.uploader.upload_batch(batch, text_embedding_list)

        # assert
        mock_write_embeddings_to_vector_db.assert_called_once_with(text_embedding_list, batch.vector_db_metadata, batch.id, batch.job_id)
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.FAILED, batch.id)
    
    def test_create_pinecone_source_chunk_dict(self):
            # arrange
            data = "thisistest" * 116 + "test"
            chunks = worker.chunk_data_exact(data, 256, 128)
            text_embeddings_dict = [(chunk, [1.0, 2.0, 3.0, 4.0, 5.0]) for chunk in chunks]
            batch_id = 1
            job_id = 1
            source_filename = "test_filename"

            # act
            upsert_list = self.uploader.create_pinecone_source_chunk_dict(text_embeddings_dict, batch_id, job_id, source_filename)

            # assert
            self.assertEqual(len(upsert_list), 3)
            self.assertEqual(upsert_list[0]['metadata']['source_text'], chunks[0])
            self.assertEqual(upsert_list[0]['values'], [1.0, 2.0, 3.0, 4.0, 5.0])
            self.assertEqual(upsert_list[0]['metadata']['source_document'], source_filename)