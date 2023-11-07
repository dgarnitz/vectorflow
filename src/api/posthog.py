import os
import sys

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import json
import uuid
import logging
import datetime
from posthog import Posthog

logging.basicConfig(filename='./api-log.txt', level=logging.INFO)
logging.basicConfig(filename='./api-errors.txt', level=logging.ERROR)

posthog = Posthog('phc_i5oDgA9SAZzBIeEFVZcFxGUVIoWWcYPsBnZaJqd06yk', host='https://app.posthog.com') 

def get_user_id():
    config_file = os.path.join(os.getenv("API_STORAGE_DIRECTORY"), "config.json")

    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            data = json.load(f)
            if "user_id" in data:
                return data["user_id"]

    user_id = str(uuid.uuid4())
    with open(config_file, "w") as f:
        json.dump({"user_id": user_id}, f)
    return user_id

def send_telemetry(event_name, vectorflow_request, filename):
        user_id = get_user_id()
        current_time = datetime.datetime.now()
        properties = {
            "filename": filename,
            "vector_db_type": vectorflow_request.vector_db_metadata.vector_db_type,
            "embeddings_type": vectorflow_request.embeddings_metadata.embeddings_type,
            "chunk_size": vectorflow_request.embeddings_metadata.chunk_size,
            "chunk_overlap": vectorflow_request.embeddings_metadata.chunk_overlap,
            "chunk_strategy": vectorflow_request.embeddings_metadata.chunk_strategy,
            "time": current_time.strftime('%m/%d/%Y')
        }

        try:
            posthog.capture(user_id, event_name, properties)
        except Exception as e:
            logging.error('ERROR sending telemetric data to Posthog. See exception: %s', e)