# Use an official Python runtime as a parent image
FROM --platform=linux/amd64 python:3.9-slim

# Set the working directory in the container
WORKDIR /site

# Copy the current directory contents into the container at /site
COPY app/ ./app
COPY requirements.txt .

# Install system dependencies for Azure Speech SDK
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    libssl-dev \
    libasound2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Expose the port that the FastAPI app will run on
EXPOSE 80

# Run app.py when the container launches
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]