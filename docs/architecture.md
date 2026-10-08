# Gmail Manager Architecture

**Version:** 1.1.0  
**Date:** 2026-10-06  
**Status:** Production Ready  

---

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Architecture](#component-architecture)
4. [Data Flow](#data-flow)
5. [Security Architecture](#security-architecture)
6. [Database Schema](#database-schema)
7. [API Design](#api-design)
8. [Deployment Architecture](#deployment-architecture)
9. [Technology Stack](#technology-stack)

---

## System Overview

Gmail Manager is an AI-powered email intelligence platform that provides:

- **Smart Auto-Labeling** — Categorizes emails automatically (Work, Finance, Newsletter, etc.)
- **Scam Detection** — ML-powered phishing detection with risk scoring (0-100)
- **URL Security Scanning** — Google Safe Browsing API integration
- **Email Rewriting** — AI-powered email transformation with presets
- **Quarantine Management** — Automatic isolation of suspicious emails

### Key Characteristics

| Characteristic | Value |
|---------------|-------|
| **Architecture Style** | Microservices (Frontend + Backend) |
| **Authentication** | OAuth 2.0 (Google) |
| **Database** | PostgreSQL (production), SQLite (test) |
| **AI Providers** | Groq (primary), Gemini (secondary), Cohere (tertiary) |
| **Deployment** | Railway (backend), Vercel (frontend) |
| **Performance** | p95 latency <200ms, memory <512MB |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│                   (React SPA + Vite)                            │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTPS
                 │ (Vercel CDN)
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Vercel)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ React Application                                         │  │
│  │ • Routing (React Router)                                  │  │
│  │ • State Management (Context API)                          │  │
│  │ • Theme Management (Light/Dark)                           │  │
│  │ • SSE Client (Real-time progress)                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTPS + CORS
                 │ (JWT cookies)
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (Railway)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ FastAPI Application                                       │  │
│  │ ┌────────────────────────────────────────────────────┐   │  │
│  │ │ API Layer                                           │   │  │
│  │ │ • 18+ REST endpoints                                │   │  │
│  │ │ • OAuth 2.0 authentication                          │   │  │
│  │ │ • Request validation (Pydantic)                     │   │  │
│  │ │ • Rate limiting                                     │   │  │
│  │ │ • CORS + CSRF protection                            │   │  │
│  │ └────────────────────────────────────────────────────┘   │  │
│  │                                                             │  │
│  │ ┌────────────────────────────────────────────────────┐   │  │
│  │ │ Business Logic Layer                                │   │  │
│  │ │ • Email analysis pipeline                           │   │  │
│  │ │ • AI cascade router (Groq → Gemini → Cohere)       │   │  │
│  │ │ • Scam detection ML inference                       │   │  │
│  │ │ • URL security scanner                              │   │  │
│  │ │ • Email rewriter                                    │   │  │
│  │ └────────────────────────────────────────────────────┘   │  │
│  │                                                             │  │
│  │ ┌────────────────────────────────────────────────────┐   │  │
│  │ │ Data Access Layer                                   │   │  │
│  │ │ • Database abstraction (PostgreSQL/SQLite)          │   │  │
│  │ │ • Connection pooling (10-50 connections)            │   │  │
│  │ │ • Query encryption (row-level)                      │   │  │
│  │ │ • Migration system                                  │   │  │
│  │ └────────────────────────────────────────────────────┘   │  │
│  │                                                             │  │
│  │ ┌────────────────────────────────────────────────────┐   │  │
│  │ │ Background Services                                 │   │  │
│  │ │ • APScheduler (periodic tasks)                      │   │  │
│  │ │ • Async job queue                                   │   │  │
│  │ │ • Email analysis worker                             │   │  │
│  │ └────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────┬────────────────┬─────────────────┬────────────────────────┘
     │                │                 │
     │ SQL            │ HTTPS           │ HTTPS
     ▼                ▼                 ▼
┌─────────┐  ┌────────────────┐  ┌────────────────┐
│PostgreSQL│  │ Gmail API      │  │ AI Providers   │
│ Database │  │ (Google)       │  │ • Groq (9 keys)│
│          │  │ • Fetch emails │  │ • Gemini       │
│          │  │ • Send replies │  │ • Cohere       │
│          │  │ • Modify labels│  │                │
└──────────┘  └────────────────┘  └────────────────┘
```

---

## Component Architecture

### Frontend Components

```
frontend/
├── src/
│   ├── App.jsx                    # Root component + routing
│   ├── main.jsx                   # React entry point
│   ├── index.css                  # Global styles + design system
│   │
│   ├── pages/                     # Page-level components
│   │   ├── Login.jsx              # OAuth login flow
│   │   ├── Inbox.jsx              # Email list + analysis
│   │   ├── ScamAlerts.jsx         # Filtered scam view
│   │   ├── Quarantine.jsx         # Quarantined emails
│   │   ├── Rewriter.jsx           # AI email rewriter
│   │   ├── Settings.jsx           # User settings
│   │   └── LandingPage.jsx        # Marketing page
│   │
│   ├── components/                # Reusable UI components
│   │   ├── Sidebar.jsx            # Navigation sidebar
│   │   ├── EmailCard.jsx          # Email display card
│   │   ├── ScamBadge.jsx          # Risk score badge
│   │   ├── ProgressBar.jsx        # Analysis progress
│   │   ├── ToastNotification.jsx  # Toast messages
│   │   └── ConfirmModal.jsx       # Confirmation dialog
│   │
│   └── context/                   # React Context providers
│       ├── ThemeContext.jsx       # Light/dark theme state
│       └── AnalysisContext.jsx    # SSE progress state
```

### Backend Components

```
backend/
├── main.py                        # FastAPI app entry + endpoints
├── auth.py                        # OAuth 2.0 flow + JWT
├── gmail.py                       # Gmail API integration
├── ai_router.py                   # AI provider cascade
├── ml_inference.py                # ML model inference
├── security.py                    # OAuth tokens + CSRF
├── encryption.py                  # Fernet encryption
├── database.py                    # Database abstraction
├── scheduler.py                   # Background jobs
├── logger_setup.py                # Logging configuration
├── features.py                    # Feature flags
├── schemas.py                     # Pydantic models
├── csrf.py                        # CSRF protection
└── security_headers.py            # Security headers middleware
```

---

## Data Flow

### 1. User Authentication Flow

```
User → Login Page → OAuth Redirect → Google OAuth → Callback Handler
  ↓
Backend receives auth code
  ↓
Exchange code for tokens (access + refresh)
  ↓
Encrypt tokens with Fernet (AES-128-CBC)
  ↓
Store encrypted tokens in database
  ↓
Generate JWT, set as httpOnly secure cookie
  ↓
Redirect to Inbox
```

### 2. Email Analysis Flow

```
User → Inbox Page → Click "Analyze Emails"
  ↓
POST /api/analyze (with count: 1-500)
  ↓
Backend validates request + user authentication
  ↓
Fetch emails from Gmail API (batch operation)
  ↓
For each email:
  ├─ Extract content + metadata
  ├─ AI cascade: Groq → Gemini → Cohere
  │    ├─ Label classification (Work, Finance, etc.)
  │    └─ Scam indicators extraction
  ├─ ML inference: Scam detection (0-100 score)
  ├─ URL scanning: Google Safe Browsing API
  └─ Store results in database (encrypted by user_id)
  ↓
SSE progress updates → Frontend (real-time)
  ↓
Analysis complete → Refresh email list
```

### 3. Email Rewriting Flow

```
User → Rewriter Page → Enter email + prompt
  ↓
POST /api/rewrite
  ↓
Validate input (max 10k+ words supported)
  ↓
AI cascade router selects provider
  ↓
Generate rewritten version
  ↓
Return to frontend → Display side-by-side
```

### 4. Quarantine Flow

```
Email with scam_score ≥ 70
  ↓
Automatic quarantine flag set
  ↓
User views Quarantine page
  ↓
Options:
  ├─ Mark Safe → Remove quarantine flag
  └─ Delete → Trash email via Gmail API
```

---

## Security Architecture

### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────┐
│ Security Layers                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Layer 1: OAuth 2.0 (Google)                                 │
│   • Authorization Code Flow                                 │
│   • Scope: gmail.readonly, gmail.modify, gmail.send         │
│   • Token refresh before expiry                             │
│                                                              │
│ Layer 2: JWT Cookies                                        │
│   • httpOnly, secure, SameSite=Lax                          │
│   • 24-hour expiry                                          │
│   • Never exposed in URLs or response bodies                │
│                                                              │
│ Layer 3: CSRF Protection                                    │
│   • Double-submit cookie pattern                            │
│   • Token validation on POST/PUT/DELETE                     │
│   • Exempt paths: /health, /auth/*                          │
│                                                              │
│ Layer 4: Encryption at Rest                                 │
│   • Fernet (AES-128-CBC + HMAC)                             │
│   • OAuth tokens encrypted before storage                   │
│   • Versioned format: {version}:{ciphertext}                │
│   • Key rotation supported                                  │
│                                                              │
│ Layer 5: Database Isolation                                 │
│   • Row-level encryption by user_id                         │
│   • Universal user_id filtering in _execute()               │
│   • Prevents cross-user data leakage                        │
│                                                              │
│ Layer 6: Input Validation                                   │
│   • Pydantic schemas validate all inputs                    │
│   • Parameterized SQL queries (no string concat)            │
│   • Request sanitization                                    │
│                                                              │
│ Layer 7: Secret Management                                  │
│   • SecretRedactionFilter on all logs                       │
│   • 5+ patterns: Bearer, API keys, JWT, emails              │
│   • Environment-based config (never hardcoded)              │
│                                                              │
│ Layer 8: Security Headers                                   │
│   • X-Content-Type-Options: nosniff                         │
│   • X-Frame-Options: DENY                                   │
│   • X-XSS-Protection: 1; mode=block                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Security Audit Results

**Status:** ✅ All 17 security tests passing

| Control | Status | Coverage |
|---------|--------|----------|
| OAuth encryption | ✅ Pass | 3 tests |
| JWT cookies | ✅ Pass | 2 tests |
| API key redaction | ✅ Pass | 3 tests |
| CSRF protection | ✅ Pass | 2 tests |
| SQL injection | ✅ Pass | 2 tests |
| Security headers | ✅ Pass | 2 tests |
| Cross-user access | ✅ Pass | 2 tests |
| **Total** | ✅ **17/17** | **100%** |

---

## Database Schema

### Entity-Relationship Diagram

```
┌──────────────────┐
│ users            │
├──────────────────┤
│ id (PK)          │─────┐
│ email            │     │
│ encrypted_tokens │     │ 1:N
│ created_at       │     │
└──────────────────┘     │
                         │
                         ▼
                ┌──────────────────┐
                │ emails           │
                ├──────────────────┤
                │ id (PK)          │
                │ user_id (FK)     │◄───── Indexed
                │ gmail_id         │
                │ subject          │
                │ sender           │
                │ body             │
                │ analyzed         │◄───── Indexed
                │ scam_score       │◄───── Indexed
                │ label_id         │
                │ quarantine       │
                │ created_at       │◄───── Indexed
                └──────────────────┘

┌──────────────────┐
│ feature_flags    │
├──────────────────┤
│ id (PK)          │
│ name             │◄───── Unique
│ enabled          │
│ description      │
│ updated_at       │
└──────────────────┘

┌──────────────────┐
│ ml_models        │
├──────────────────┤
│ id (PK)          │
│ name             │
│ version          │
│ file_path        │
│ metrics          │
│ is_active        │
│ created_at       │
└──────────────────┘

┌──────────────────┐
│ schema_version   │
├──────────────────┤
│ version (PK)     │
│ applied_at       │
└──────────────────┘
```

### Key Indices

```sql
-- Performance-critical indices
CREATE INDEX idx_emails_user_id ON emails(user_id);
CREATE INDEX idx_emails_analyzed ON emails(analyzed);
CREATE INDEX idx_emails_scam_score ON emails(scam_score);
CREATE INDEX idx_emails_created_at ON emails(created_at);

-- Composite index for filtered queries
CREATE INDEX idx_emails_user_analyzed ON emails(user_id, analyzed);
```

### Query Performance

| Query Type | Average Time | Index Used |
|-----------|--------------|------------|
| User emails (all) | <10ms | idx_emails_user_id |
| Unanalyzed emails | <15ms | idx_emails_user_analyzed |
| Scam alerts (score ≥70) | <20ms | idx_emails_scam_score |
| Recent emails | <10ms | idx_emails_created_at |

---

## API Design

### REST API Endpoints

#### Authentication
- `GET /auth/login` — Initiate OAuth flow
- `GET /auth/callback` — OAuth callback handler
- `POST /auth/logout` — Clear session

#### Emails
- `GET /api/emails` — List user emails (paginated)
- `GET /api/emails/{email_id}` — Get email details
- `POST /api/analyze` — Analyze N emails (1-500)
- `PUT /api/emails/{email_id}/label` — Update label
- `DELETE /api/emails/{email_id}` — Delete email

#### Email Operations
- `POST /api/rewrite` — Rewrite email with AI
- `POST /api/reply` — Send threaded reply
- `GET /api/quarantine` — List quarantined emails
- `PUT /api/emails/{email_id}/quarantine` — Toggle quarantine

#### System
- `GET /health` — Multi-component health check
- `GET /api/ml/active-model-metadata` — ML model info
- `GET /api/features` — List feature flags
- `PUT /api/features/{name}` — Toggle feature

### Request/Response Format

**Standard Success Response:**
```json
{
  "success": true,
  "data": { ... },
  "timestamp": "2026-10-06T16:02:19.213Z"
}
```

**Standard Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": { ... }
  },
  "timestamp": "2026-10-06T16:02:19.213Z"
}
```

---

## Deployment Architecture

### Production Deployment (Railway + Vercel)

```
Internet
   │
   ├─────────────────────────────────────────┐
   │                                          │
   ▼                                          ▼
┌──────────────┐                    ┌──────────────┐
│   Vercel CDN  │                    │   Railway    │
│   (Frontend)  │                    │   (Backend)  │
├──────────────┤                    ├──────────────┤
│ • React SPA   │◄──── CORS ───────►│ • FastAPI    │
│ • Global CDN  │      HTTPS         │ • Gunicorn   │
│ • Auto-scale  │                    │ • Auto-scale │
│ • SSL cert    │                    │ • SSL cert   │
└──────────────┘                    └───────┬──────┘
                                            │
                                            │ Private Network
                                            ▼
                                    ┌──────────────┐
                                    │ PostgreSQL   │
                                    │ (Railway DB) │
                                    ├──────────────┤
                                    │ • Managed DB │
                                    │ • Auto-backup│
                                    │ • Connection │
                                    │   pooling    │
                                    └──────────────┘
```

### Environment Configuration

| Environment | Frontend (Vercel) | Backend (Railway) | Database |
|------------|-------------------|-------------------|----------|
| **Development** | localhost:5173 | localhost:8000 | SQLite (local) |
| **Test** | localhost:5173 | localhost:8000 | PostgreSQL (localhost:5433) |
| **Production** | *.vercel.app | *.railway.app | PostgreSQL (Railway managed) |

---

## Technology Stack

### Frontend
- **Framework:** React 18.3+
- **Build Tool:** Vite 5+
- **Routing:** React Router 6+
- **State:** React Context API
- **Styling:** Plain CSS (design system)
- **HTTP Client:** Fetch API
- **Real-time:** Server-Sent Events (SSE)

### Backend
- **Framework:** FastAPI 0.100+
- **Language:** Python 3.11+
- **ASGI Server:** Uvicorn (dev), Gunicorn (prod)
- **Database ORM:** Direct SQL (psycopg2, sqlite3)
- **Validation:** Pydantic 2+
- **Background Jobs:** APScheduler 3+
- **Logging:** Python logging + structlog

### Infrastructure
- **Frontend Hosting:** Vercel (CDN + auto-deploy)
- **Backend Hosting:** Railway (containers + auto-deploy)
- **Database:** PostgreSQL 15+ (Railway managed)
- **Version Control:** Git + GitHub
- **CI/CD:** GitHub Actions (future)

### External Services
- **Authentication:** Google OAuth 2.0
- **Email API:** Gmail API v1
- **AI Providers:**
  - Groq (openai/gpt-oss-20b) — Primary, 9 rotating keys
  - Google Gemini (gemini-2.0-flash) — Secondary
  - Cohere (command-r) — Tertiary
- **Security:** Google Safe Browsing API
- **ML Inference:** scikit-learn (Logistic Regression)

---

## Performance Characteristics

### Response Times (p95)
- **Health check:** <100ms
- **Email list:** <200ms
- **Single email fetch:** <300ms
- **Email analysis (AI):** 1-3s per email
- **Email rewrite:** 2-5s
- **ML inference:** <100ms

### Throughput
- **API requests:** 100-200 req/sec
- **Email analysis:** 5-10 emails/sec
- **Database queries:** 1000+ queries/sec

### Resource Usage
- **Memory (baseline):** 100-150 MB
- **Memory (under load):** 200-400 MB
- **Memory (limit):** <512 MB
- **CPU (idle):** <5%
- **CPU (analysis):** 20-40%

---

## Scalability Considerations

### Horizontal Scaling
- **Frontend:** Auto-scales via Vercel CDN (global)
- **Backend:** Railway auto-scaling (up to N instances)
- **Database:** Vertical scaling + read replicas (future)

### Bottlenecks
1. **Gmail API quota** — 250 units/user/second (external limit)
2. **AI provider rate limits** — Mitigated by 9 Groq keys + cascade
3. **Database connections** — Mitigated by connection pooling
4. **ML inference** — Could be offloaded to dedicated service

### Future Optimizations
- **Caching layer** — Redis for frequently accessed data
- **Message queue** — RabbitMQ/Redis for async jobs
- **Read replicas** — Separate read/write database instances
- **CDN for API** — CloudFlare/Fastly for API caching

---

## Monitoring & Observability

### Current Logging
- **Structured logs** — JSON format with correlation IDs
- **Log levels** — DEBUG (dev), INFO (prod)
- **Secret redaction** — 5+ patterns filtered
- **Log rotation** — Size + time-based

### Health Checks
- **Database connectivity** — Connection pool status
- **Scheduler status** — Background job health
- **ML model status** — Active model validation
- **Endpoint:** `GET /health`

### Future Monitoring (Recommended)
- **APM:** Datadog / New Relic / Sentry
- **Metrics:** Prometheus + Grafana
- **Tracing:** OpenTelemetry distributed tracing
- **Alerting:** PagerDuty / Opsgenie

---

## Disaster Recovery

### Backup Strategy
- **Database:** Railway auto-backups (daily)
- **Manual backup:** `pg_dump` before major changes
- **Retention:** 30 days (Railway default)

### Recovery Procedures
1. **Database failure:** Restore from latest backup
2. **Backend failure:** Railway auto-restart + rollback
3. **Frontend failure:** Vercel auto-rollback
4. **OAuth token corruption:** Users re-authenticate

### High Availability
- **Frontend:** 99.9% uptime (Vercel SLA)
- **Backend:** 99.5% uptime (Railway SLA)
- **Database:** 99.9% uptime (Railway managed)

---

## Security Compliance

### Standards
- **OWASP Top 10:** All controls implemented
- **OAuth 2.0:** RFC 6749 compliant
- **GDPR:** User data encryption + deletion support
- **WCAG 2.1:** Level AA compliance (frontend)

### Audit Trail
- **Security audit:** 17/17 tests passing
- **Penetration testing:** Recommended annually
- **Dependency scanning:** npm audit + pip audit
- **Code review:** Required for all changes

---

## Documentation

- **README.md** — Setup + quick start
- **CHANGELOG.md** — Version history + migration guides
- **architecture.md** — This document
- **deployment.md** — Deployment procedures
- **performance-baseline.md** — Performance metrics

---

**Last Updated:** 2026-10-06  
**Version:** 1.1.0  
**Status:** Production Ready
