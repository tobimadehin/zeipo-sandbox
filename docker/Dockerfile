FROM pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN apt update && apt-get install -y build-essential libpcre3-dev libboost-dev python3-dev wget tar

# Install SWIG 3.0.12 explicitly
RUN cd /tmp \
    && wget https://sourceforge.net/projects/swig/files/swig/swig-3.0.12/swig-3.0.12.tar.gz \
    && tar -xzf swig-3.0.12.tar.gz \
    && cd swig-3.0.12 \
    && ./configure --prefix=/usr/local \
    && make -j$(nproc) \
    && make install \
    && rm -rf /tmp/swig-3.0.12*
    

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command (can be overridden)
CMD ["python", "-m", "src.transcribe", "--help"]