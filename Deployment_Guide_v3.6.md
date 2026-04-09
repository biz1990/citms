# CITMS v3.6 - Comprehensive Deployment Guide

This document provides unified instructions for setting up the Centralized IT Management System (CITMS) v3.6 in both **Local Development** and **Production** environments.

---

## 🚀 Part 1: Quick Start (Local Development)

This method uses **Docker Compose** to orchestrate all services including PostgreSQL, Redis, and MinIO.

### 1.1 Prerequisites
- **Windows/Mac**: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ensure WSL2 is enabled on Windows).
- **Linux**: Docker & Docker Compose.
- **Node.js**: v20+ (for local frontend development).

### 1.2 Preparation
1.  **Clone Source**: `git clone <repository_url> && cd citms`
2.  **Environment Variables**:
    ```bash
    cp .env.example .env
    ```
    *Note: Default values in `.env.example` are pre-tuned for local Docker execution.*

### 1.3 Launch Services
```bash
# Start all infrastructure and backend containers
docker compose up -d db redis minio api worker beat event_consumer
```

### 1.4 Database Initialisation
Wait ~10 seconds for DB to be ready, then run:

```bash
# 1. Run Database Migrations
docker exec -it citms_api alembic upgrade head

# 2. Seed Initial Roles & Permissions
docker exec -it citms_api python backend/scripts/seed_initial_data.py

# 3. Create Super Admin Account
docker exec -it citms_api python backend/scripts/create_super_admin.py --email admin@local.com --password admin
```

### 1.5 Launch Frontend
```bash
cd frontend
npm install
npm run dev
```
- **App URL**: [http://localhost:5173](http://localhost:5173) (Login: `admin@local.com` / `admin`)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001)

---

## 🏛️ Part 2: Production Deployment (Ubuntu 22.04)

For high-availability production setups using system-native services.

### 2.1 Server Requirements
- **OS**: Ubuntu 22.04 LTS.
- **DB**: PostgreSQL 15+ (with `pg_cron`).
- **Cache**: Redis 7.0+.

### 2.2 Database Performance Setup
Enable `pg_cron` in `postgresql.conf`:
```bash
# Edit /etc/postgresql/15/main/postgresql.conf
shared_preload_libraries = 'pg_cron'
cron.database_name = 'citms_v3'
```
Restart: `sudo systemctl restart postgresql`

### 2.3 Backend Installation
```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m alembic upgrade head
# Run seed scripts as shown in Local section (Point python to .env)
```

---

## ✅ Part 3: v3.6 Verification Checklist

Ensure the remediation items from v3.6 are properly active:

### 3.1 GIN Index (Audit Log Performance)
Verify the index exists for fast JSONB searches:
```sql
SELECT * FROM pg_indexes WHERE indexname = 'ix_audit_logs_details_gin';
```

### 3.2 pg_cron (Inventory Analytics)
Confirm the automated Materialized View refresh is scheduled:
```sql
SELECT * FROM cron.job WHERE jobname = 'inventory-mv-refresh';
```

### 3.3 RustDesk Remote Preview
Verify `RUSTDESK_API_URL` and `RUSTDESK_API_TOKEN` are correctly set in `.env` to enable real-time dashboard previews.

---

## 🔧 Part 4: Troubleshooting

| Issue | Potential Solution |
| :--- | :--- |
| **Port 5432 already in use** | Stop any local Postgres service or change `POSTGRES_PORT` in `.env`. |
| **CORS Errors** | Ensure `BACKEND_CORS_ORIGINS` in `.env` includes your frontend URL. |
| **MinIO Upload Fails** | Create a bucket named `citms-attachments` in the MinIO console. |
| **Worker not processing tasks** | Check worker logs: `docker compose logs -f worker`. |

---
**Status:** CITMS v3.6 - READY FOR PRODUCTION
**Prepared by:** Antigravity Solution Architect
