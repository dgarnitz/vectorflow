import unittest
import worker.vdb_upload_worker as vdb_upload_worker
import worker.worker as worker

class TestVDBUploadWorker(unittest.TestCase):

    def test_create_pinecone_source_chunk_dict(self):
            # arrange
            data = "thisistest" * 38 + "test"
            chunks = worker.chunk_data_exact(data, 256, 128)
            text_embeddings_dict = [(chunk, [1.0, 2.0, 3.0, 4.0, 5.0]) for chunk in chunks]
            batch_id = 1
            job_id = 1

            # act
            upsert_list = vdb_upload_worker.create_pinecone_source_chunk_dict(text_embeddings_dict, batch_id, job_id)

            # assert
            self.assertEqual(len(upsert_list), 3)
            self.assertEqual(upsert_list[0]['metadata']['source_text'], chunks[0])
            self.assertEqual(upsert_list[0]['values'], [1.0, 2.0, 3.0, 4.0, 5.0])