import unittest
from shared.batch_status import BatchStatus
import worker.worker as worker
from unittest.mock import patch

class TestWorker(unittest.TestCase):
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_job_status')
    def test_process_batch_success(self, mock_update_job_status, mock_embed_openai_batch):
        # arrange
        batch = {"embeddings_metadata": {"embeddings_type": "open_ai"}, "job_id": "test_job_id", "batch_id": "test_batch_id"}
        mock_embed_openai_batch.return_value = 1

        # act
        worker.process_batch(batch)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch)
        mock_update_job_status.assert_called_with(batch['job_id'], BatchStatus.COMPLETED, batch['batch_id'])

    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_job_status')
    def test_process_batch_failure_no_vectors(self, mock_update_job_status, mock_embed_openai_batch):
        # arrange
        batch = {"embeddings_metadata": {"embeddings_type": "open_ai"}, "job_id": "test_job_id", "batch_id": "test_batch_id"}
        mock_embed_openai_batch.return_value = 0

        # act
        worker.process_batch(batch)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch)
        mock_update_job_status.assert_called_with(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])

    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_job_status')
    def test_process_batch_failure_openai(self, mock_update_job_status, mock_embed_openai_batch):
        # arrange
        batch = {"embeddings_metadata": {"embeddings_type": "open_ai"}, "job_id": "test_job_id", "batch_id": "test_batch_id"}
        mock_embed_openai_batch.side_effect = Exception("Simulated Exception")

        # act
        worker.process_batch(batch)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch)
        mock_update_job_status.assert_called_with(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])

    def test_chunk_data(self):
        # arrange
        # 384 characters, should be 3 chunks, since the last chunk will be partial
        data = ["thisistest"] * 38
        data.append("test") 

        # act
        chunks = worker.chunk_data(data, 256, 128)

        # assert
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[2]), 128)

    def test_create_source_chunk_dict(self):
        # arrange
        data = "thisistest" * 38 + "test"
        chunks = worker.chunk_data(data, 256, 128)
        text_embeddings_dict = [(chunk, [1.0, 2.0, 3.0, 4.0, 5.0]) for chunk in chunks]
        batch_id = 1
        job_id = 1

        # act
        upsert_list = worker.create_pinecone_source_chunk_dict(text_embeddings_dict, batch_id, job_id)

        # assert
        self.assertEqual(len(upsert_list), 3)
        self.assertEqual(upsert_list[0]['metadata']['source_text'], chunks[0])
        self.assertEqual(upsert_list[0]['id'], "1_1_0")
        self.assertEqual(upsert_list[0]['values'], [1.0, 2.0, 3.0, 4.0, 5.0])

if __name__ == '__main__':
    unittest.main()
