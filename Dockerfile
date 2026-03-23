FROM python:3.12-slim

# Use 3.12 inside container (stable, all libs work perfectly)
WORKDIR /app

# Install OpenSSL for TLS cert generation
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app/ ./app/
COPY certs/ ./certs/

# Generate self-signed TLS certificate if not present
RUN openssl req -x509 -newkey rsa:4096 \
    -keyout certs/key.pem \
    -out certs/cert.pem \
    -days 365 -nodes \
    -subj "/CN=localhost"

EXPOSE 8443

CMD ["python", "app/main.py"]