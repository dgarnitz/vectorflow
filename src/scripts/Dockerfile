FROM python:3.9.9-slim-buster

COPY scripts/create_database.py /scripts/create_database.py
COPY services/database /services/database
COPY shared /shared
COPY models /models
COPY worker/requirements.txt /app/worker/requirements.txt

RUN pip install --no-cache-dir -r /app/worker/requirements.txt

COPY scripts/wait-for-it.sh /scripts/wait-for-it.sh
RUN chmod +x /scripts/wait-for-it.sh

CMD ["/scripts/wait-for-it.sh", "postgres:5432", "--", "python", "/scripts/create_database.py"]
