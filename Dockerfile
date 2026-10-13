# Base Image
FROM mirror-docker.runflare.com/library/python:3.12-slim

# Runtime Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirror-pypi.runflare.com/simple \
    UVICORN_PORT=8000 \
    TZ=Asia/Tehran

WORKDIR /app

# Configure APT Mirrors
RUN sed -i 's/deb.debian.org/mirror-linux.runflare.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirror-linux.runflare.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/https/http/g' /etc/apt/sources.list.d/debian.sources

# Install System Dependencies
RUN apt-get update -o Acquire::Check-Valid-Until=false \
    && apt-get install -y --no-install-recommends ca-certificates curl nginx tzdata \
        -o Acquire::Check-Valid-Until=false \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set Timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy Application
COPY . .

# Configure Nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Expose Web Port
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1/health || exit 1

# Start Services
CMD ["sh", "-c", "uvicorn app.main:app --host 127.0.0.1 --port ${UVICORN_PORT:-8000} --timeout-keep-alive 120 --no-access-log & nginx -g 'daemon off;'"]
