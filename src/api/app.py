import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from models.embeddings_metadata import EmbeddingsMetadata
from models.vector_db_metadata import VectorDBMetadata
from models.batch import Batch
from auth import Auth
from pipeline import Pipeline
from shared.job_status import JobStatus

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
        embeddings_metadata_dict['embeddings_type'], 
        embeddings_metadata_dict['chunk_size'],
        embeddings_metadata_dict['chunk_overlap'])
    
    vector_db_metadata_dict = json.loads(request.form.get('VectorDBMetadata'))
    vector_db_metadata = VectorDBMetadata(
        vector_db_metadata_dict['vector_db_type'], 
        vector_db_metadata_dict['index_name'], 
        vector_db_metadata_dict['environment'])
    
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
        file_content = file.read()
        job_id = pipeline.create_job(webhook_url)
        batch_count = create_batches(file_content, job_id, embeddings_metadata, vector_db_metadata, lines_per_chunk)
        return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job_id}), 200
    else:
        return jsonify({'message': 'Uploaded file is not a TXT file'}), 400

@app.route('/jobs/<int:job_id>/status', methods=['GET'])
def get_job_status(job_id):
    vectorflow_key = request.headers.get('VectorFlowKey')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    job_status = pipeline.get_job_status(job_id)
    if job_status:
        return jsonify({'JobStatus': job_status.value}), 200
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
        next_batch = pipeline.get_from_queue()
        return jsonify({'batch': next_batch.serialize()}), 200

@app.route('/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    vectorflow_key = request.headers.get('VectorFlowKey')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    try:
        job_status = pipeline.update_job_with_batch(job_id, request.json['batch_id'], request.json['batch_status'])
        if job_status == JobStatus.COMPLETED:
            return jsonify({'message': f'Job {job_id} completed successfully'}), 200
        elif job_status == JobStatus.IN_PROGRESS:
            return jsonify({'message': f'Job {job_id} is in progress'}), 202
        elif job_status == JobStatus.PARTIALLY_COMPLETED:
            return jsonify({'message': f'Job {job_id} partially completed'}), 206
        else:
            return jsonify({'message': f'Job {job_id} processed all batches and failed to complete any'}), 404
    except Exception as e:
        print(e)
        return jsonify({'message': f'Job {job_id} failed due to server error'}), 500

def create_batches(file_content, job_id, embeddings_metadata, vector_db_metadata, lines_per_chunk):
    batch_count = 0
    for i, chunk in enumerate(split_file(file_content, lines_per_chunk)):
        # TODO: this has to be altered because chunk needs to be a string  
        # TODO: this needs to be written to the DB by a data service
        batch = Batch(chunk, f"{job_id}-{i}", job_id, embeddings_metadata, vector_db_metadata)
        pipeline.add_to_queue(batch)
        pipeline.create_batch(batch)
        batch_count+=1
    pipeline.update_job_total_batches(job_id, batch_count)
    return batch_count
    
def split_file(file_content, lines_per_chunk=1000):
    lines = file_content.splitlines()
    #TODO: the has to be altered because chunk needs to be a string
    for i in range(0, len(lines), lines_per_chunk):
        yield lines[i:i+lines_per_chunk]


if __name__ == '__main__':
   app.run(host='0.0.0.0', debug=True)