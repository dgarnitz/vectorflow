import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import requests
# magic requires lib magic to be installed on the system. If running on mac and an error occurs, run `brew install libmagic`
import magic
import json
import fitz
import base64
import logging
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
from shared.embeddings_type import EmbeddingsType
from docx import Document

auth = Auth()
pipeline = Pipeline()
app = Flask(__name__)
CORS(app) 

@app.route("/embed", methods=['POST'])
def embed():
    # TODO: add validator service
    vectorflow_request = VectorflowRequest(request)
    if not vectorflow_request.vectorflow_key or not auth.validate_credentials(vectorflow_request.vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
 
    if not vectorflow_request.embeddings_metadata or not vectorflow_request.vector_db_metadata or not vectorflow_request.vector_db_key:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if vectorflow_request.embeddings_metadata.embeddings_type == EmbeddingsType.HUGGING_FACE and not vectorflow_request.embeddings_metadata.hugging_face_model_name:
        return jsonify({'error': 'Hugging face embeddings models require a "hugging_face_model_name" in the "embeddings_metadata"'}), 400
    
    if 'SourceData' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['SourceData']
    
    # TODO: Remove this once the application is reworked to support large files
    # Get the file size - Go to the end of the file, get the current position, and reset the file to the beginning
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > 25 * 1024 * 1024:
        return jsonify({'error': 'File is too large. VectorFlow currently only supports 25 MB files or less. Larger file support coming soon.'}), 413
    
    # empty filename means no file was selected
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and (file.filename.endswith('.txt') or file.filename.endswith('.pdf') or file.filename.endswith('.docx')):
        batch_count, job_id = process_file(file, vectorflow_request)
        return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job_id}), 200
    else:
        return jsonify({'error': 'Uploaded file is not a TXT, PDF or DOCX file'}), 400

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
    
@app.route("/s3", methods=['POST'])
def s3_presigned_url():
    # TODO: add validator service
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
                job = job_service.create_job(db, vectorflow_request.webhook_url, None)
            batch_count = create_batches(file_content, job.id, vectorflow_request)
            return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job.id}), 200
        
        elif mime_type == 'application/pdf':
            pdf_data = BytesIO(response.content)
            with fitz.open(stream=pdf_data, filetype='pdf') as doc:
                file_content = ""
                for page in doc:
                    file_content += page.get_text()

            with get_db() as db:
                job = job_service.create_job(db, vectorflow_request.webhook_url, None)
            batch_count = create_batches(file_content, job.id, vectorflow_request)
            return jsonify({'message': f"Successfully added {batch_count} batches to the queue", 'JobID': job.id}), 200
        
        else:
            return jsonify({'error': 'Uploaded file is not a TXT or PDF file'}), 400
    else:
        print('Failed to download file:', response.status_code, response.reason)

def process_file(file, vectorflow_request):
    if file.filename.endswith('.txt'):
        file_content = file.read().decode('utf-8')
    
    elif file.filename.endswith('.docx'):
        doc = Document(file)
        file_content = "\n".join([paragraph.text for paragraph in doc.paragraphs])

    else:
        pdf_data = BytesIO(file.read())
        with fitz.open(stream=pdf_data, filetype='pdf') as doc:
            file_content = ""
            for page in doc:
                file_content += page.get_text()

    with get_db() as db:
        job = job_service.create_job(db, vectorflow_request.webhook_url, file.filename)
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

            pipeline.connect(queue=os.getenv('EMBEDDING_QUEUE'))
            pipeline.add_to_queue(json_data, queue=os.getenv('EMBEDDING_QUEUE'))
            pipeline.disconnect()

    return job.total_batches if job else None
    
def split_file(file_content, lines_per_chunk=1000):
    lines = file_content.splitlines()
    for i in range(0, len(lines), lines_per_chunk):
        yield lines[i:i+lines_per_chunk]

@app.route("/images", methods=['POST'])
def upload_image():
    # TODO: add validator service
    vectorflow_request = VectorflowRequest(request)
    if not vectorflow_request.vectorflow_key or not auth.validate_credentials(vectorflow_request.vectorflow_key):
        return jsonify({'error': 'Invalid credentials'}), 401
 
    if not vectorflow_request.vector_db_metadata or not vectorflow_request.vector_db_key:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if 'SourceData' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['SourceData']

    # TODO: Remove this once the application is reworked to support large files
    # Get the file size - Go to the end of the file, get the current position, and reset the file to the beginning
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > 2 * 1024 * 1024:
        return jsonify({'error': 'File is too large. VectorFlow currently only supports 2 MB files or less for images. Larger file support coming soon.'}), 413
    
    # empty filename means no file was selected
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and (file.filename.endswith('.jpg') or file.filename.endswith('.jpeg') or file.filename.endswith('.png')):
        try:
            job_id = process_image(file, vectorflow_request)
            return jsonify({'message': f"Successfully added {file.filename} batches to the queue", 'JobID': job_id}), 200
        
        except Exception as e:
            logging.error(f"Attempt to upload file {file.filename} failed due to error: {e}")
            return jsonify({'error': f"Attempt to upload file {file.filename} failed due to error: {e}"}), 400
    else:
        return jsonify({'error': 'Uploaded file is not a JPG, JPEG, or PNG file'}), 400
    
def process_image(file, vectorflow_request):
    # Create job
    with get_db() as db:
        job = job_service.create_job_with_vdb_metadata(db, vectorflow_request, file.filename)

    # Convert image to bytes
    img_bytes_io = BytesIO()
    file.save(img_bytes_io)
    image_bytes = img_bytes_io.getvalue()

    # Encode image bytes to Base64 string to allowed for serializaton to JSON
    encoded_image_string = base64.b64encode(image_bytes).decode("utf-8")

    # Convert to JSON - this format can be read agnostic of the technology on the other side
    message_body = {
        'image_bytes': encoded_image_string,
        'vector_db_key': vectorflow_request.vector_db_key,
        'job_id': job.id,
    }
    json_data = json.dumps(message_body)

    pipeline.connect(queue=os.getenv('IMAGE_QUEUE'))
    pipeline.add_to_queue(json_data, queue=os.getenv('IMAGE_QUEUE'))
    pipeline.disconnect()
    
    return job.id

if __name__ == '__main__':
   app.run(host='0.0.0.0', debug=True)