# --- Stage 1: Build & Dependencies ---
FROM python:3.10-slim-bullseye AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: Base Runtime ---
FROM python:3.10-slim-bullseye AS runtime-base

WORKDIR /app

# Install runtime dependencies (libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application source code
COPY . .

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# --- Stage 3: API Service ---
FROM runtime-base AS api
EXPOSE 8000
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Stage 4: Celery Worker ---
FROM runtime-base AS worker
CMD ["celery", "-A", "backend.src.core.celery", "worker", "-l", "info"]

# --- Stage 5: Celery Beat ---
FROM runtime-base AS beat
CMD ["celery", "-A", "backend.src.core.celery", "beat", "-l", "info"]

# --- Stage 6: Database Backup (Scheduled) ---
FROM runtime-base AS backup
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    awscli \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Add cron job (Every day at 2 AM)
# Note: We use a wrapper to ensure env vars are available to cron
RUN echo "0 2 * * * . /etc/environment; /bin/bash /app/backend/scripts/backup_db.sh >> /var/log/cron.log 2>&1" > /etc/cron.d/db-backup && \
    chmod 0644 /etc/cron.d/db-backup && \
    crontab /etc/cron.d/db-backup

# Create log file
RUN touch /var/log/cron.log

# Entrypoint script to export env vars and start cron
RUN echo "#!/bin/bash\n\
declare -p | grep -Ev 'BASHOPTS|BASH_VERSINFO|EUID|PPID|SHELLOPTS|UID' > /etc/environment\n\
cron -f" > /usr/local/bin/entrypoint-backup.sh && \
    chmod +x /usr/local/bin/entrypoint-backup.sh

CMD ["/usr/local/bin/entrypoint-backup.sh"]
