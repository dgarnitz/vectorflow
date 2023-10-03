import unittest
from shared.chunk_strategy import ChunkStrategy
import worker.worker as worker
import worker.config as config
from models.batch import Batch
from models.embeddings_metadata import EmbeddingsMetadata
from models.job import Job
from shared.batch_status import BatchStatus
from shared.embeddings_type import EmbeddingsType
from shared.job_status import JobStatus
from unittest.mock import patch

class TestWorker(unittest.TestCase):
    @patch('worker.worker.chunk_data')
    @patch('worker.worker.upload_to_vector_db')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_batch_status')
    def test_process_batch_success(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_openai_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_safe_db_operation,
        mock_update_job_status,
        mock_update_batch_status,
        mock_upload_to_vector_db,
        mock_chunk_data):
        # arrange
        source_data = "source_data"
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI))
        text_embeddings_list = [("test", [0.1, 0.2, 0.3])]
        chunked_data = ["test"]
        mock_chunk_data.return_value = chunked_data
        mock_embed_openai_batch.return_value = text_embeddings_list
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act
        worker.process_batch(batch.id, source_data)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch, chunked_data)
        mock_upload_to_vector_db.assert_called_with(batch.id, text_embeddings_list)

    @patch('worker.worker.chunk_data')
    @patch('worker.worker.upload_to_vector_db')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_hugging_face_batch')
    @patch('worker.worker.update_batch_status')
    def test_process_batch_hugging_face_embeddings_success(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_hugging_face_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_safe_db_operation,
        mock_update_job_status,
        mock_update_batch_status,
        mock_upload_to_vector_db,
        mock_chunk_data):
        # arrange
        source_data = "source_data"
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, 
                      embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.HUGGING_FACE, 
                                                             hugging_face_model_name="test_model_name"))
        chunked_data = ["test"]
        mock_chunk_data.return_value = chunked_data
        text_embeddings_list = [("test", [0.1, 0.2, 0.3])]
        mock_embed_hugging_face_batch.return_value = text_embeddings_list
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act
        worker.process_batch(batch.id, source_data)

        # assert
        mock_embed_hugging_face_batch.assert_called_once_with(batch, chunked_data)

    @patch('worker.worker.chunk_data')
    @patch('worker.worker.upload_to_vector_db')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_batch_status')
    def test_process_batch_failure_no_vectors(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_openai_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_safe_db_operation,
        mock_update_job_status,
        mock_update_batch_status,
        mock_upload_to_vector_db,
        mock_chunk_data):
        # arrange
        source_data = "source_data"
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI))
        chunked_data = ["test"]
        mock_chunk_data.return_value = chunked_data
        mock_embed_openai_batch.return_value = None
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act
        worker.process_batch(batch.id, source_data)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch, chunked_data)
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.FAILED, batch.id)
        mock_upload_to_vector_db.assert_not_called()

    @patch('worker.worker.chunk_data')
    @patch('worker.worker.upload_to_vector_db')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_batch_status')
    def test_process_batch_failure_openai(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_openai_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_safe_db_operation,
        mock_update_job_status,
        mock_update_batch_status,
        mock_upload_to_vector_db,
        mock_chunk_data):
        # arrange
        source_data = "source_data"
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI))
        chunked_data = ["test"]
        mock_chunk_data.return_value = chunked_data

        mock_embed_openai_batch.side_effect = Exception("Mock Exception")

        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act
        worker.process_batch(batch.id, source_data)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch, chunked_data)
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.FAILED, batch.id)
        mock_upload_to_vector_db.assert_not_called()

    @patch('worker.worker.validate_chunks')
    @patch('worker.worker.upload_to_vector_db')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_batch_status')
    def test_process_batch_failure_validate_chunks(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_openai_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_safe_db_operation,
        mock_update_job_status,
        mock_update_batch_status,
        mock_upload_to_vector_db,
        mock_validate_chunks):
        # arrange
        source_data = "source_data" * 100
        job = Job(id=1, chunk_validation_url="test_validation_url", job_status=JobStatus.NOT_STARTED)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, 
                      embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI,
                                                             chunk_size=256,
                                                             chunk_overlap=128,
                                                             chunk_strategy=ChunkStrategy.EXACT))
        
        mock_validate_chunks.return_value = []

        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act & assert
        with self.assertRaises(Exception) as context:
            worker.process_batch(batch.id, source_data)
        
        # you can add an additional check for the exception message if necessary
        self.assertEqual(str(context.exception), "Failed to chunk data")

        # assert
        mock_embed_openai_batch.assert_not_called()
        mock_upload_to_vector_db.assert_not_called()
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.FAILED, batch.id)
    
    def test_chunk_data_exact(self):
        # arrange
        # 384 characters, should be 3 chunks, since the last chunk will be partial
        data = ["thisistest"] * 38
        data.append("test") 

        # act
        chunks = worker.chunk_data_exact(data, 256, 128)

        # assert
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[2]), 128)

    def test_chunk_paragraph(self):
        data = ["This is an example paragraph.\n\n"] * 4
        
        chunks = worker.chunk_data_by_paragraph(data, chunk_size=35, overlap=0)

        self.assertEqual(len(chunks), 4)

    def test_chunk_paragraph_overlap(self):
        data = ["This is an example paragraph.\n\n"] * 2

        chunks = worker.chunk_data_by_paragraph(data, chunk_size=35, overlap=15)

        expected_overlap = 'This is an exam'
        self.assertEqual(chunks[0][:15], expected_overlap)

    def test_chunk_paragraph_bound(self):
        data = ["This is \n\n a very early paragraph."]

        chunks = worker.chunk_data_by_paragraph(data, chunk_size=35, overlap=0, bound=0.75)

        self.assertEqual(len(chunks), 1)

    def test_chunk_sentence(self):
        data = ["I am a sentence. I am a sentence but with a question? I am still a sentence! Can I consider myself a sentence..."]
        
        chunks = worker.chunk_by_sentence(data, chunk_size=50, overlap=0)

        self.assertEqual(len(chunks), 4)

    def test_chunk_sentence_too_big(self):
        data = ["I am a sentence. I am a sentence but with a question? I am still a sentence! Can I consider myself a sentence... Blahblah Blahblah Blahblah Blahblah Blahblah Blahblah ."]
        
        chunks = worker.chunk_by_sentence(data, chunk_size=50, overlap=0)

        self.assertEqual(len(chunks), 6)


    def test_create_openai_batches(self):
        # arrange
        batches = ["test"] * config.MAX_OPENAI_EMBEDDING_BATCH_SIZE * 4

        # act
        openai_batches = worker.create_upload_batches(batches, config.MAX_OPENAI_EMBEDDING_BATCH_SIZE)

        # assert
        self.assertEqual(len(openai_batches), 4)

if __name__ == '__main__':
    unittest.main()
