# Docker Deployment Guide

This guide covers deploying the Gmail Manager application using Docker Compose.

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- At least 2GB RAM available
- Ports 5173 (frontend), 8000 (backend), 5432 (postgres) available

## Quick Start

### 1. Setup Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.docker .env
```

Edit `.env` and configure:
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` (from Google Cloud Console)
- `GROQ_API_KEY` and/or `GEMINI_API_KEY` (AI providers)
- `SAFE_BROWSING_API_KEY` (Google Safe Browsing)
- `DB_ENCRYPTION_KEY` and `JWT_SECRET_KEY` (generate secure random strings)

**Generate secure keys:**
```bash
python -c "import secrets; print('DB_ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### 2. Build and Start Services

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

### 3. Verify Deployment

**Check service status:**
```bash
docker-compose ps
```

**Expected output:**
```
NAME                IMAGE                    STATUS
gmail-backend       gmail-manager-backend    Up (healthy)
gmail-frontend      gmail-manager-frontend   Up
gmail-postgres      postgres:15              Up (healthy)
```

**Test backend health:**
```bash
curl http://localhost:8000/health
```

**Access frontend:**
Open http://localhost:5173 in your browser

### 4. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f postgres
docker-compose logs -f frontend
```

### 5. Stop Services

```bash
# Stop services (keeps data)
docker-compose stop

# Stop and remove containers (keeps volumes)
docker-compose down

# Remove everything including volumes (⚠️ destroys data)
docker-compose down -v
```

## Architecture

```
┌─────────────────┐
│   Frontend      │
│  (Vite + React) │
│   Port: 5173    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Backend      │
│  (FastAPI)      │
│   Port: 8000    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │
│   Port: 5432    │
└─────────────────┘
```

## Services

### PostgreSQL (postgres)
- **Image:** postgres:15
- **Port:** 5432
- **Volume:** `postgres_data` (persistent database storage)
- **Health Check:** `pg_isready` every 10s
- **Initial Schema:** Auto-loaded from `backend/postgres_schema.sql`

### Backend (backend)
- **Build:** `backend/Dockerfile`
- **Port:** 8000
- **Depends On:** postgres (waits for health check)
- **Health Check:** `/health` endpoint every 30s
- **Logs:** Mounted to `./logs` directory

### Frontend (frontend)
- **Build:** `frontend/Dockerfile`
- **Port:** 5173
- **Depends On:** backend
- **API Proxy:** Connects to backend at http://backend:8000

## Data Persistence

**PostgreSQL Data:**
- Volume: `postgres_data`
- Location: Managed by Docker
- Survives container restarts
- Removed only with `docker-compose down -v`

**Application Logs:**
- Mounted: `./logs/` → `/app/logs`
- Persists on host filesystem
- Survives container removal

## Development Workflow

### Hot Reload (Development)

For development with hot reload, override the docker-compose.yml:

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  frontend:
    command: npm run dev -- --host 0.0.0.0
    volumes:
      - ./frontend/src:/app/src:delegated
      - ./frontend/public:/app/public:delegated
```

Run with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker-compose build backend
docker-compose up -d backend

# Rebuild all services
docker-compose up -d --build
```

### Database Operations

**Access PostgreSQL:**
```bash
docker-compose exec postgres psql -U postgres -d gmail_manager
```

**Backup database:**
```bash
docker-compose exec postgres pg_dump -U postgres gmail_manager > backup.sql
```

**Restore database:**
```bash
cat backup.sql | docker-compose exec -T postgres psql -U postgres gmail_manager
```

**Reset database:**
```bash
docker-compose down -v
docker-compose up -d postgres
```

## Troubleshooting

### Backend won't start
- Check logs: `docker-compose logs backend`
- Verify environment variables in `.env`
- Ensure postgres is healthy: `docker-compose ps postgres`

### Frontend can't reach backend
- Verify backend health: `curl http://localhost:8000/health`
- Check network: `docker network inspect gmail-manager_gmail-network`
- Verify VITE_API_BASE in frontend environment

### PostgreSQL connection errors
- Check DATABASE_URL matches postgres service name
- Verify postgres is running: `docker-compose ps postgres`
- Check postgres logs: `docker-compose logs postgres`

### Port conflicts
If ports are already in use:
```yaml
# Change ports in docker-compose.yml
services:
  frontend:
    ports:
      - "3000:5173"  # Host:Container
  backend:
    ports:
      - "8080:8000"
```

## Production Deployment

For production, consider:

1. **Use secrets management** — Don't commit `.env` file
2. **Enable HTTPS** — Use Nginx/Traefik reverse proxy
3. **Set resource limits:**
   ```yaml
   services:
     backend:
       deploy:
         resources:
           limits:
             cpus: '1.0'
             memory: 1G
   ```
4. **Use production PostgreSQL** — Managed database service
5. **Enable monitoring** — Add Prometheus/Grafana
6. **Automated backups** — Schedule pg_dump cron jobs

## Environment Variables Reference

See `.env.docker` for complete list with descriptions.

**Required:**
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GROQ_API_KEY` or `GEMINI_API_KEY`
- `DB_ENCRYPTION_KEY`, `JWT_SECRET_KEY`
- `SAFE_BROWSING_API_KEY`

**Optional:**
- `REDIS_URL` (caching)
- `COHERE_API_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY` (additional AI providers)

## Support

For issues, check:
1. Service logs: `docker-compose logs`
2. Health checks: `docker-compose ps`
3. Network connectivity: `docker network inspect gmail-manager_gmail-network`
