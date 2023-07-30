# Use an official Python runtime as a parent image
FROM python:3.9.9-slim-buster

# Sets dumping log messages directly to stream instead of buffering
ENV PYTHONUNBUFFERED=1

# Set working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Copy requirements.txt and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the command to start gunicorn with 1 worker. NOTE you may have to alter the number of workers.
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8000", "app:app"]
