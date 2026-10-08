# Gmail Manager Deployment Guide

**Version:** 1.1.0  
**Date:** 2026-10-06  
**Target:** Railway (Backend) + Vercel (Frontend)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Local Development](#local-development)
4. [Database Setup](#database-setup)
5. [Railway Deployment (Backend)](#railway-deployment-backend)
6. [Vercel Deployment (Frontend)](#vercel-deployment-frontend)
7. [Post-Deployment Verification](#post-deployment-verification)
8. [Troubleshooting](#troubleshooting)
9. [Monitoring & Maintenance](#monitoring--maintenance)
10. [Rollback Procedures](#rollback-procedures)

---

## Prerequisites

### Required Accounts
- ✅ **Google Cloud Console** — OAuth credentials + Gmail API
- ✅ **Railway** — Backend hosting + PostgreSQL
- ✅ **Vercel** — Frontend hosting + CDN
- ✅ **GitHub** — Version control + CI/CD
- ✅ **AI Provider accounts** — Groq, Gemini, Cohere

### Required Tools
```bash
# Verify installations
python --version    # Python 3.11+
node --version      # Node.js 18+
git --version       # Git 2.30+
railway --version   # Railway CLI (optional)
vercel --version    # Vercel CLI
```

### Install Missing Tools
```bash
# Railway CLI
npm install -g railway

# Vercel CLI
npm install -g vercel
```

---

## Environment Setup

### 1. Generate Encryption Keys

**DB_ENCRYPTION_KEY** (Fernet key for OAuth tokens):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Output example: `ABCD1234efgh5678IJKL9012mnop3456qrstUVWXyz78=`

**SECRET_KEY** (CSRF token signing):
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Output example: `XyZ_AbC123-DeF456_GhI789-JkL012_MnO345`

### 2. Google OAuth Credentials

1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable **Gmail API**:
   - Navigate to **APIs & Services** → **Library**
   - Search "Gmail API" → Click **Enable**
4. Create OAuth 2.0 credentials:
   - Navigate to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth client ID**
   - Application type: **Web application**
   - Name: `Gmail Manager`
   - Authorized redirect URIs:
     - Development: `http://localhost:8000/auth/callback`
     - Production: `https://your-backend.railway.app/auth/callback`
   - Click **Create**
5. Copy **Client ID** and **Client Secret**

### 3. AI Provider API Keys

| Provider | URL | Free Tier | Model |
|----------|-----|-----------|-------|
| **Groq** | [console.groq.com/keys](https://console.groq.com/keys) | 6,000 req/min | openai/gpt-oss-20b |
| **Gemini** | [aistudio.google.com](https://aistudio.google.com/) | 60 req/min | gemini-2.0-flash |
| **Cohere** | [dashboard.cohere.ai](https://dashboard.cohere.ai/) | 1,000 req/month | command-r |

**Groq setup (9 rotating keys for high throughput):**
1. Create 9 API keys in Groq Console
2. Format in `.env`: `GROQ_API_KEY_1=...`, `GROQ_API_KEY_2=...`, etc.

---

## Local Development

### 1. Clone Repository

```bash
git clone https://github.com/your-org/gmail-manager.git
cd gmail-manager
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (bash):
source venv/Scripts/activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

**Edit `backend/.env`:**
```bash
# Database (use SQLite for local dev)
SQLITE_DB_PATH=gmail_manager_dev.db

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Encryption Keys (generate as shown above)
DB_ENCRYPTION_KEY=your_32_byte_fernet_key_here
SECRET_KEY=your_csrf_secret_key_here

# AI Providers
GROQ_API_KEY_1=gsk_...
GROQ_API_KEY_2=gsk_...
# ... up to GROQ_API_KEY_9
GEMINI_API_KEY_1=AIza...
COHERE_API_KEY=your_cohere_key

# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

**Initialize database:**
```bash
python main.py
# Database schema auto-created on first run
```

### 3. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env
```

**Edit `frontend/.env`:**
```bash
VITE_API_BASE=http://localhost:8000
```

### 4. Run Development Servers

**Terminal 1 (Backend):**
```bash
cd backend
source venv/Scripts/activate  # Windows bash
python main.py
# Backend running on http://localhost:8000
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm run dev
# Frontend running on http://localhost:5173
```

**Access the app:** http://localhost:5173

---

## Database Setup

### Local Development (SQLite)

SQLite is auto-created on first run. No manual setup needed.

```bash
# Database file location
backend/gmail_manager_dev.db

# View schema
sqlite3 backend/gmail_manager_dev.db ".schema"

# Backup
cp backend/gmail_manager_dev.db backup_$(date +%Y%m%d).db
```

### Test Environment (PostgreSQL)

```bash
# Install PostgreSQL
# Windows: Download from postgresql.org
# macOS: brew install postgresql
# Linux: sudo apt install postgresql

# Start PostgreSQL service
# Windows: services.msc → postgresql-x64-15 → Start
# macOS: brew services start postgresql
# Linux: sudo systemctl start postgresql

# Create test database
psql -U postgres
CREATE DATABASE gmail_manager_test;
CREATE USER gmail_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE gmail_manager_test TO gmail_user;
\q

# Update backend/.env.test
DATABASE_URL=postgresql://gmail_user:secure_password@localhost:5432/gmail_manager_test
```

### Production (Railway PostgreSQL)

Railway automatically provisions PostgreSQL. Connection string provided as `DATABASE_URL`.

---

## Railway Deployment (Backend)

### 1. Create Railway Project

```bash
# Login to Railway
railway login

# Create new project
railway init
# Select: "Create a new project"
# Project name: gmail-manager-backend

# Link to existing project (if already created)
railway link
```

### 2. Provision PostgreSQL

**Via Railway Dashboard:**
1. Open project at [railway.app](https://railway.app/)
2. Click **New** → **Database** → **PostgreSQL**
3. Database auto-provisioned with `DATABASE_URL` variable

**Via CLI:**
```bash
railway add --plugin postgresql
```

### 3. Configure Environment Variables

**Via Railway Dashboard:**
1. Open project → **Variables** tab
2. Add each variable:

```bash
# Database (auto-set by Railway PostgreSQL plugin)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Connection pool (production)
DB_POOL_SIZE=20
DB_POOL_TIMEOUT=30

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=https://your-backend.railway.app/auth/callback

# Encryption Keys
DB_ENCRYPTION_KEY=your_production_fernet_key
SECRET_KEY=your_production_csrf_key

# AI Providers (all 9 Groq keys)
GROQ_API_KEY_1=gsk_...
GROQ_API_KEY_2=gsk_...
GROQ_API_KEY_3=gsk_...
GROQ_API_KEY_4=gsk_...
GROQ_API_KEY_5=gsk_...
GROQ_API_KEY_6=gsk_...
GROQ_API_KEY_7=gsk_...
GROQ_API_KEY_8=gsk_...
GROQ_API_KEY_9=gsk_...
GEMINI_API_KEY_1=AIza...
COHERE_API_KEY=your_cohere_key

# Google Safe Browsing
GOOGLE_SAFE_BROWSING_API_KEY=AIza...

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_SCHEDULER=true
```

**Via CLI:**
```bash
railway variables set DB_ENCRYPTION_KEY="your_key_here"
railway variables set SECRET_KEY="your_key_here"
# ... repeat for all variables
```

### 4. Deploy Backend

**Option A: GitHub Integration (Recommended)**

1. Push code to GitHub:
   ```bash
   git add .
   git commit -m "Production deployment"
   git push origin main
   ```

2. Link Railway to GitHub:
   - Railway Dashboard → **Settings** → **Deploy** → **Connect Repo**
   - Select repository: `your-org/gmail-manager`
   - Branch: `main`
   - Root directory: `backend`

3. Auto-deploy on push:
   - Every `git push origin main` triggers automatic deployment

**Option B: Railway CLI**

```bash
cd backend
railway up
# Deploys current directory to Railway
```

### 5. Verify Backend Deployment

```bash
# Get deployment URL
railway status
# Example: https://gmail-manager-backend-production.railway.app

# Test health endpoint
curl https://your-backend.railway.app/health

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "scheduler": "running",
#   "ml_model": "active"
# }
```

### 6. View Logs

**Via CLI:**
```bash
railway logs
```

**Via Dashboard:**
Railway Dashboard → **Deployments** → Click deployment → **Logs** tab

---

## Vercel Deployment (Frontend)

### 1. Login to Vercel

```bash
vercel login
# Follow browser authentication flow
```

### 2. Deploy Frontend

```bash
cd frontend

# First deployment (interactive)
vercel
# Project name: gmail-manager-frontend
# Framework preset: Vite
# Build command: npm run build
# Output directory: dist
# Root directory: frontend

# Production deployment
vercel --prod
```

### 3. Configure Environment Variables

**Via Vercel Dashboard:**

1. Open [vercel.com/dashboard](https://vercel.com/dashboard)
2. Select project → **Settings** → **Environment Variables**
3. Add variable:
   - **Key:** `VITE_API_BASE`
   - **Value:** `https://your-backend.railway.app`
   - **Environment:** Production

**Via CLI:**
```bash
vercel env add VITE_API_BASE production
# Paste: https://your-backend.railway.app
```

### 4. Redeploy with Environment Variables

```bash
vercel --prod
```

### 5. Verify Frontend Deployment

```bash
# Get deployment URL
vercel ls
# Example: https://gmail-manager-frontend.vercel.app

# Test in browser
open https://gmail-manager-frontend.vercel.app
```

---

## Post-Deployment Verification

### 1. Backend Health Check

```bash
curl https://your-backend.railway.app/health

# Expected:
{
  "status": "healthy",
  "database": "connected",
  "scheduler": "running",
  "ml_model": "active",
  "timestamp": "2026-10-06T16:07:07.578Z"
}
```

### 2. Frontend Accessibility

```bash
curl -I https://your-frontend.vercel.app

# Expected:
HTTP/2 200
content-type: text/html
...
```

### 3. OAuth Flow Test

1. Visit `https://your-frontend.vercel.app`
2. Click **Login with Google**
3. Authorize Gmail scopes
4. Should redirect to Inbox page
5. Verify JWT cookie set (check DevTools → Application → Cookies)

### 4. API Integration Test

**Test email fetch:**
```bash
# Get JWT token from browser cookies (httpOnly requires browser)
# Then test API endpoint:

curl -X GET https://your-backend.railway.app/api/emails \
  -H "Cookie: access_token=your_jwt_here" \
  -H "X-CSRF-Token: your_csrf_token_here"

# Expected: Email list response
```

### 5. Database Connection Test

```bash
# Railway CLI
railway connect postgres

# Run query
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM emails;

# Exit
\q
```

### 6. End-to-End Test Checklist

- [ ] User can log in with Google OAuth
- [ ] User can fetch email list from Gmail
- [ ] User can analyze emails (AI cascade works)
- [ ] User can view scam alerts (ML model works)
- [ ] User can rewrite emails (AI rewriter works)
- [ ] User can send replies via Gmail API
- [ ] User can toggle quarantine status
- [ ] User can log out (session cleared)

---

## Troubleshooting

### Backend Issues

#### 1. Database Connection Failed

**Error:** `could not connect to server`

**Solutions:**
```bash
# Check DATABASE_URL is set
railway variables get DATABASE_URL

# Verify PostgreSQL is running
railway status

# Check database logs
railway logs --service postgres

# Restart database
railway restart --service postgres
```

#### 2. OAuth Redirect URI Mismatch

**Error:** `redirect_uri_mismatch`

**Solution:**
1. Check `GOOGLE_REDIRECT_URI` matches Google Console
2. Google Console → Credentials → Edit OAuth Client
3. Add: `https://your-backend.railway.app/auth/callback`
4. Wait 5 minutes for changes to propagate

#### 3. Encryption Key Error

**Error:** `Invalid encryption key`

**Solution:**
```bash
# Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Update Railway variable
railway variables set DB_ENCRYPTION_KEY="new_key_here"

# Redeploy
railway up
```

#### 4. AI Provider Rate Limit

**Error:** `Rate limit exceeded`

**Solution:**
- AI cascade automatically fails over to next provider
- Check logs for which provider hit limit:
  ```bash
  railway logs | grep "rate limit"
  ```
- Add more API keys or wait for reset

#### 5. Connection Pool Exhaustion

**Error:** `could not obtain lock on row` or timeouts

**Solution:**
```bash
# Increase pool size
railway variables set DB_POOL_SIZE=50

# Redeploy
railway up
```

### Frontend Issues

#### 1. API Base URL Wrong

**Error:** Network requests fail / CORS errors

**Solution:**
```bash
# Verify environment variable
vercel env ls

# Update if wrong
vercel env rm VITE_API_BASE production
vercel env add VITE_API_BASE production
# Enter: https://your-backend.railway.app

# Redeploy
vercel --prod
```

#### 2. Build Fails

**Error:** `Build failed`

**Solution:**
```bash
# Test build locally
cd frontend
npm run build

# Check build logs
vercel logs

# Fix errors, then redeploy
vercel --prod
```

#### 3. White Screen / Blank Page

**Solution:**
1. Check browser console for errors (F12)
2. Verify `VITE_API_BASE` is set correctly
3. Check network tab for failed requests
4. Rebuild and redeploy:
   ```bash
   vercel --prod --force
   ```

### Database Issues

#### 1. Schema Not Initialized

**Error:** `relation "users" does not exist`

**Solution:**
```bash
# Backend auto-initializes schema on first run
# Force initialization:
railway run python -c "from database import init_db; init_db()"
```

#### 2. Migration Failed

**Error:** `Schema migration failed`

**Solution:**
```bash
# Connect to database
railway connect postgres

# Check schema_version
SELECT * FROM schema_version;

# Manual rollback if needed
DROP TABLE schema_version;
\q

# Redeploy backend (will reinitialize)
railway up
```

---

## Monitoring & Maintenance

### 1. Monitor Logs

**Railway (Backend):**
```bash
# Live logs
railway logs --follow

# Filter by error level
railway logs | grep ERROR

# Last 100 lines
railway logs --tail 100
```

**Vercel (Frontend):**
```bash
# View recent deployments
vercel ls

# Logs for specific deployment
vercel logs <deployment-url>
```

### 2. Database Backups

**Automatic (Railway):**
- Railway PostgreSQL auto-backs up daily
- 30-day retention

**Manual:**
```bash
# Backup database
railway connect postgres
pg_dump > backup_$(date +%Y%m%d).sql
\q

# Restore from backup
railway connect postgres < backup_20261006.sql
```

### 3. Health Monitoring

**Setup monitoring endpoint:**
```bash
# Check health every 5 minutes
curl https://your-backend.railway.app/health
```

**Recommended tools:**
- **UptimeRobot** — Free, 5-minute checks
- **Pingdom** — Detailed monitoring
- **Datadog** — APM + metrics

### 4. Performance Monitoring

**Key metrics to track:**
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Database connection pool usage
- Memory usage
- AI provider success rate

**Railway metrics:**
```bash
railway metrics
```

### 5. Security Updates

**Regular maintenance:**
```bash
# Update backend dependencies
cd backend
pip list --outdated
pip install --upgrade <package>

# Update frontend dependencies
cd frontend
npm outdated
npm update

# Security audit
npm audit
pip-audit
```

---

## Rollback Procedures

### 1. Rollback Backend (Railway)

**Via Dashboard:**
1. Railway Dashboard → **Deployments**
2. Find previous successful deployment
3. Click **⋮** → **Redeploy**

**Via CLI:**
```bash
# List deployments
railway deployments

# Rollback to specific deployment
railway rollback <deployment-id>
```

### 2. Rollback Frontend (Vercel)

**Via Dashboard:**
1. Vercel Dashboard → Project → **Deployments**
2. Find previous deployment
3. Click **⋮** → **Promote to Production**

**Via CLI:**
```bash
# List deployments
vercel ls

# Rollback (redeploy previous version)
vercel rollback <deployment-url>
```

### 3. Rollback Database (Railway PostgreSQL)

**Restore from backup:**
```bash
# List backups (Railway Dashboard → Database → Backups)
# Download backup
railway connect postgres < backup_20261006.sql
```

**Emergency reset:**
```bash
# Connect to database
railway connect postgres

# Drop all tables
DROP TABLE emails CASCADE;
DROP TABLE users CASCADE;
DROP TABLE feature_flags CASCADE;
DROP TABLE ml_models CASCADE;
DROP TABLE schema_version CASCADE;
\q

# Redeploy backend (reinitializes schema)
railway up
```

---

## Production Checklist

### Pre-Deployment
- [ ] All tests passing locally (`pytest backend/tests/`)
- [ ] Environment variables documented in `.env.example`
- [ ] Database backup created
- [ ] Encryption keys generated (production keys, not dev)
- [ ] OAuth redirect URIs updated in Google Console
- [ ] AI provider API keys validated
- [ ] Frontend build succeeds (`npm run build`)

### Deployment
- [ ] Backend deployed to Railway
- [ ] Frontend deployed to Vercel
- [ ] Environment variables set on both platforms
- [ ] Database schema initialized
- [ ] Health check returns `"status": "healthy"`

### Post-Deployment
- [ ] End-to-end test completed
- [ ] OAuth flow working
- [ ] Email fetch working
- [ ] AI cascade working (all 3 providers)
- [ ] ML model inference working
- [ ] Performance baseline met (<200ms p95)
- [ ] Monitoring configured (UptimeRobot/Datadog)
- [ ] Team notified of deployment

### Documentation
- [ ] Update README with production URLs
- [ ] Create runbook for common issues
- [ ] Document any configuration changes
- [ ] Update API documentation if endpoints changed

---

## Support & Resources

### Documentation
- **README.md** — Quick start guide
- **CHANGELOG.md** — Version history
- **architecture.md** — System design
- **performance-baseline.md** — Performance metrics

### External Documentation
- [Railway Documentation](https://docs.railway.app/)
- [Vercel Documentation](https://vercel.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Gmail API Documentation](https://developers.google.com/gmail/api)

### Contact
- **Issues:** GitHub Issues
- **Email:** support@gmail-manager.example.com
- **Status Page:** status.gmail-manager.example.com

---

**Last Updated:** 2026-10-06  
**Version:** 1.1.0  
**Deployment Status:** Production Ready ✅
