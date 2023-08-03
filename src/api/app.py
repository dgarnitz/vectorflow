import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import json
import services.database.batch_service as batch_service
import services.database.job_service as job_service
from flask import Flask, request, jsonify
from flask_cors import CORS
from models.embeddings_metadata import EmbeddingsMetadata
from models.vector_db_metadata import VectorDBMetadata
from models.batch import Batch
from auth import Auth
from pipeline import Pipeline
from shared.job_status import JobStatus
from services.database.database import get_db
from shared.embeddings_type import EmbeddingsType
from shared.vector_db_type import VectorDBType

auth = Auth()
pipeline = Pipeline()
app = Flask(__name__)
CORS(app) 

@app.route("/embed", methods=['POST'])
def embed():
    vectorflow_key = request.headers.get('VectorFlowKey')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    webhook_url = request.form.get('WebhookURL')
    embeddings_metadata_dict = json.loads(request.form.get('EmbeddingsMetadata'))
    embeddings_metadata = EmbeddingsMetadata(
        embeddings_type = EmbeddingsType(embeddings_metadata_dict['embeddings_type']), 
        chunk_size = embeddings_metadata_dict['chunk_size'],
        chunk_overlap = embeddings_metadata_dict['chunk_overlap'])
    
    vector_db_metadata_dict = json.loads(request.form.get('VectorDBMetadata'))
    vector_db_metadata = VectorDBMetadata(
        vector_db_type = VectorDBType(vector_db_metadata_dict['vector_db_type']), 
        index_name = vector_db_metadata_dict['index_name'], 
        environment = vector_db_metadata_dict['environment'])
    
    lines_per_chunk = int(request.form.get('LinesPerChunk')) if request.form.get('LinesPerChunk') else 1000
 
    if not embeddings_metadata or not vector_db_metadata:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if 'SourceData' not in request.files:
        return jsonify({'message': 'No file part in the request'}), 400

    file = request.files['SourceData']
    
    # empty filename means no file was selected
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    
    # Check if the file has a .txt extension
    if file and file.filename.endswith('.txt'):
        file_content = file.read().decode('utf-8')

        with get_db() as db:
            job = job_service.create_job(db, webhook_url)
        batch_count = create_batches(file_content, job.id, embeddings_metadata, vector_db_metadata, lines_per_chunk)
        return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job.id}), 200
    else:
        return jsonify({'message': 'Uploaded file is not a TXT file'}), 400

@app.route('/jobs/<int:job_id>/status', methods=['GET'])
def get_job_status(job_id):
    vectorflow_key = request.headers.get('VectorFlowKey')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    with get_db() as db:
        job = job_service.get_job(db, job_id)
        if job:
            return jsonify({'JobStatus': job.job_status.value}), 200
        else:
            return jsonify({'error': "Job not found"}), 404


@app.route("/dequeue")
def dequeue():
    vectorflow_key = request.headers.get('VectorFlowKey')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    if pipeline.get_queue_size() == 0:
        return jsonify({'error': 'No jobs in queue'}), 404
    else:
        next_batch, source_data = pipeline.get_from_queue()
        return jsonify({'batch': next_batch, 'source_data': source_data}), 200

@app.route('/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    vectorflow_key = request.headers.get('VectorFlowKey')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    try:
        with get_db() as db:
            updated_batch_status = batch_service.update_batch_status(db, request.json['batch_id'], request.json['batch_status'])
            job = job_service.update_job_with_batch(db, job_id, updated_batch_status)
            if job.job_status == JobStatus.COMPLETED:
                return jsonify({'message': f'Job {job_id} completed successfully'}), 200
            elif job.job_status == JobStatus.IN_PROGRESS:
                return jsonify({'message': f'Job {job_id} is in progress'}), 202
            elif job.job_status == JobStatus.PARTIALLY_COMPLETED:
                return jsonify({'message': f'Job {job_id} partially completed'}), 206
            else:
                return jsonify({'message': f'Job {job_id} processed all batches and failed to complete any'}), 404
    except Exception as e:
        print(e)
        return jsonify({'message': f'Job {job_id} failed due to server error'}), 500

def create_batches(file_content, job_id, embeddings_metadata, vector_db_metadata, lines_per_chunk):
    batches = []
    for chunk in split_file(file_content, lines_per_chunk):
        batch = Batch(job_id=job_id, embeddings_metadata=embeddings_metadata, vector_db_metadata=vector_db_metadata)
        pipeline.add_to_queue((batch.serialize(), chunk))
        batches.append(batch)
    
    with get_db() as db:
        batch_count = batch_service.create_batches(db, batches)
        job = job_service.update_job_total_batches(db, job_id, batch_count)
    return job.total_batches if job else None
    
def split_file(file_content, lines_per_chunk=1000):
    lines = file_content.splitlines()
    for i in range(0, len(lines), lines_per_chunk):
        yield lines[i:i+lines_per_chunk]


if __name__ == '__main__':
   app.run(host='0.0.0.0', debug=True)