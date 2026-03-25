FROM python:3.11-slim

WORKDIR /app

# Install docker CLI for container management
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://get.docker.com -o get-docker.sh \
    && sh get-docker.sh \
    && rm get-docker.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn httpx

COPY proxy.py .

EXPOSE 8080

CMD ["python", "proxy.py"]
