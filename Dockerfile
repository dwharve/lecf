FROM python:3.9-slim

# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    certbot \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir certbot-dns-cloudflare

# Copy application code
COPY certificate_manager.py .
COPY setup_cloudflare.py .
COPY .env.example .

# Create directory for certificates and secrets
RUN mkdir -p /etc/letsencrypt /root/.secrets \
    && chmod 700 /root/.secrets

# Create a non-root user
RUN useradd -m -s /bin/bash certbot

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create entrypoint script
RUN echo '#!/bin/bash\n\
if [ ! -f /app/.env ]; then\n\
  echo "Error: .env file not found. Please mount it as a volume."\n\
  exit 1\n\
fi\n\
\n\
# Run setup script\n\
python /app/setup_cloudflare.py\n\
\n\
# Start the certificate manager\n\
exec python /app/certificate_manager.py\n\
' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (can be overridden)
CMD [] 