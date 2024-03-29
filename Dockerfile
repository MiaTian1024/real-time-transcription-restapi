# Specifies the base image for the container. 
FROM --platform=linux/amd64 ubuntu:22.04

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Updates the package lists for Ubuntu 
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    curl

# Set the working directory in the container
WORKDIR /site

# Copy the current directory contents into the container at /site
COPY app/ ./app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install system dependencies for Azure Speech SDK
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    libssl-dev \
    libasound2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# RUN wget http://ports.ubuntu.com/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_arm64.deb
# RUN dpkg -i libssl1.1_1.1.1f-1ubuntu2_arm64.deb
RUN wget http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.0g-2ubuntu4_amd64.deb
RUN dpkg -i libssl1.1_1.1.0g-2ubuntu4_amd64.deb

# Expose the port that the FastAPI app will run on
EXPOSE 80

# Run app.py when the container launches
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]