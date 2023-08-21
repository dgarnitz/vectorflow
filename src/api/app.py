import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import requests
import magic
import json
import fitz
from io import BytesIO
import services.database.batch_service as batch_service
import services.database.job_service as job_service
from flask import Flask, request, jsonify
from flask_cors import CORS
from models.batch import Batch
from api.auth import Auth
from api.pipeline import Pipeline
from services.database.database import get_db
from api.vectorflow_request import VectorflowRequest

auth = Auth()
pipeline = Pipeline()
app = Flask(__name__)
CORS(app) 

@app.route("/embed", methods=['POST'])
def embed():
    vectorflow_request = VectorflowRequest(request)
    if not vectorflow_request.vectorflow_key or not auth.validate_credentials(vectorflow_request.vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
 
    if not vectorflow_request.embeddings_metadata or not vectorflow_request.vector_db_metadata or not vectorflow_request.vector_db_key:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if 'SourceData' not in request.files:
        return jsonify({'message': 'No file part in the request'}), 400

    file = request.files['SourceData']
    
    # empty filename means no file was selected
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    
    if file and (file.filename.endswith('.txt') or file.filename.endswith('.pdf')):
        batch_count, job_id = process_file(file, vectorflow_request)
        return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job_id}), 200
    else:
        return jsonify({'message': 'Uploaded file is not a TXT or PDF file'}), 400

@app.route('/jobs/<int:job_id>/status', methods=['GET'])
def get_job_status(job_id):
    vectorflow_key = request.headers.get('Authorization')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    with get_db() as db:
        job = job_service.get_job(db, job_id)
        if job:
            return jsonify({'JobStatus': job.job_status.value}), 200
        else:
            return jsonify({'error': "Job not found"}), 404


#: NOTE: This endpoint is for debugging and testing only. 
@app.route("/dequeue")
def dequeue():
    vectorflow_key = request.headers.get('Authorization')
    if not vectorflow_key or not auth.validate_credentials(vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    pipeline.connect()
    if pipeline.get_queue_size() == 0:
        pipeline.disconnect()
        return jsonify({'error': 'No jobs in queue'}), 404
    else:
        body = pipeline.get_from_queue()
        pipeline.disconnect()

        data = json.loads(body)
        batch_id, source_data = data

        return jsonify({'batch_id': batch_id, 'source_data': source_data}), 200
    
@app.route("/s3", methods=['POST'])
def s3_presigned_url():
    vectorflow_request = VectorflowRequest(request)
    if not vectorflow_request.vectorflow_key or not auth.validate_credentials(vectorflow_request.vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
 
    pre_signed_url = request.form.get('PreSignedURL')
    if not vectorflow_request.embeddings_metadata or not vectorflow_request.vector_db_metadata or not vectorflow_request.vector_db_key or not pre_signed_url:
        return jsonify({'error': 'Missing required fields'}), 400
    
    response = requests.get(pre_signed_url)
    if response.status_code == 200:
        file_magic = magic.Magic(mime=True)
        mime_type = file_magic.from_buffer(response.content)

        if mime_type == 'text/plain':
            file_content = response.text
            with get_db() as db:
                job = job_service.create_job(db, vectorflow_request.webhook_url)
            batch_count = create_batches(file_content, job.id, vectorflow_request)
            return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job.id}), 200
        
        elif mime_type == 'application/pdf':
            pdf_data = BytesIO(response.content)
            with fitz.open(stream=pdf_data, filetype='pdf') as doc:
                file_content = ""
                for page in doc:
                    file_content += page.get_text()

            with get_db() as db:
                job = job_service.create_job(db, vectorflow_request.webhook_url)
            batch_count = create_batches(file_content, job.id, vectorflow_request)
            return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job.id}), 200
        
        else:
            return jsonify({'message': 'Uploaded file is not a TXT or PDF file'}), 400
    else:
        print('Failed to download file:', response.status_code, response.reason)

def process_file(file, vectorflow_request):
    if file.filename.endswith('.txt'):
        file_content = file.read().decode('utf-8')
    else:
        pdf_data = BytesIO(file.read())
        with fitz.open(stream=pdf_data, filetype='pdf') as doc:
            file_content = ""
            for page in doc:
                file_content += page.get_text()

    with get_db() as db:
        job = job_service.create_job(db, vectorflow_request.webhook_url)
    batch_count = create_batches(file_content, job.id, vectorflow_request)
    return batch_count, job.id

def create_batches(file_content, job_id, vectorflow_request):
    chunks = [chunk for chunk in split_file(file_content, vectorflow_request.lines_per_batch)]
    
    with get_db() as db:
        batches = [Batch(job_id=job_id, embeddings_metadata=vectorflow_request.embeddings_metadata, vector_db_metadata=vectorflow_request.vector_db_metadata) for _ in chunks]
        batches = batch_service.create_batches(db, batches)
        job = job_service.update_job_total_batches(db, job_id, len(batches))

        for batch, chunk in zip(batches, chunks):
            data = (batch.id, chunk, vectorflow_request.vector_db_key, vectorflow_request.embedding_api_key)
            json_data = json.dumps(data)

            pipeline.connect()
            pipeline.add_to_queue(json_data)
            pipeline.disconnect()

    return job.total_batches if job else None
    
def split_file(file_content, lines_per_chunk=1000):
    lines = file_content.splitlines()
    for i in range(0, len(lines), lines_per_chunk):
        yield lines[i:i+lines_per_chunk]


if __name__ == '__main__':
   app.run(host='0.0.0.0', debug=True)