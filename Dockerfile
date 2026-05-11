FROM python:3.11-slim

LABEL maintainer="Peter Nasarah Dashe <peternasarah@gmail.com>"
LABEL description="Permi Security Scanner — AI-powered vulnerability scanner for Nigerian developers"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Permi
ARG PERMI_VERSION=latest
RUN if [ "$PERMI_VERSION" = "latest" ]; then \
        pip install --no-cache-dir permi; \
    else \
        pip install --no-cache-dir "permi==${PERMI_VERSION}"; \
    fi

# Copy the entrypoint script
COPY entrypoint.py /entrypoint.py
RUN chmod +x /entrypoint.py

ENTRYPOINT ["python", "/entrypoint.py"]
