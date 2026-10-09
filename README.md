# 📧 Gmail Manager — AI-Powered Email Intelligence

> Smart labeling, scam detection, security scanning, and email rewriting — all powered by a multi-AI cascade system.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Stack](https://img.shields.io/badge/stack-React%20%2B%20FastAPI-purple)
![Live](https://img.shields.io/badge/demo-live-success)

**🌐 Live Demo**: [gmail-manager-gamma.vercel.app](https://gmail-manager-gamma.vercel.app)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **🏷️ Auto Labels** | AI analyzes every email and applies colored Gmail labels (Work, Finance, Newsletter, etc.) |
| **🛡️ Scam Shield** | Detects phishing, scam indicators, and assigns 0-100 risk scores |
| **🔗 URL Scanner** | Checks every link against Google Safe Browsing API for malware/phishing |
| **🔒 Quarantine** | Automatically isolates suspicious emails with one-click safe/delete actions |
| **✏️ AI Rewriter** | Transform any email with presets (Professional, Shorten, Friendly) or custom instructions |
| **📊 Smart Filters** | Filter by sender, label, scam score — all server-side with debounced search |
| **🔄 AI Failover** | Cascade: Groq (9 keys) → Gemini → Cohere — automatic fallback on rate limits |
| **📧 Inline Reply** | Reply directly from the inbox — threaded replies sent via Gmail API |
| **📱 Responsive UI** | Light/dark theme toggle, mobile-optimized design |

---

## 🏗️ Architecture

```
gmail-manager/
├── backend/                    # Python FastAPI (Railway deployment)
│   ├── main.py                 # API entry point — 18+ endpoints
│   ├── auth.py                 # Google OAuth 2.0 flow + token persistence
│   ├── gmail.py                # Gmail API + bulk analysis pipeline
│   ├── ai_router.py            # AI cascade: Groq → Gemini → Cohere
│   ├── security.py             # URL scanner + Safe Browsing API
│   ├── database.py             # PostgreSQL database layer
│   ├── ml_inference.py         # ML model inference
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # API keys (never committed)
├── frontend/                   # React + Vite (Vercel deployment)
│   ├── src/
│   │   ├── App.jsx             # Root routing + sidebar layout
│   │   ├── main.jsx            # React entry point
│   │   ├── index.css           # Light design system (modern minimalism + neumorphism)
│   │   ├── pages/
│   │   │   ├── Login.jsx       # Google OAuth login
│   │   │   ├── Inbox.jsx       # Email list + custom-count bulk analysis (1-500)
│   │   │   ├── ScamAlerts.jsx  # Risk-filtered scam alerts
│   │   │   ├── Quarantine.jsx  # Quarantined email management
│   │   │   ├── Rewriter.jsx    # AI email rewriter (supports 10k+ words)
│   │   │   ├── Settings.jsx    # Provider status + labels + account
│   │   │   └── LandingPage.jsx # Marketing landing page
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── EmailCard.jsx
│   │   │   ├── ScamBadge.jsx
│   │   │   ├── ProgressBar.jsx
│   │   │   ├── ToastNotification.jsx
│   │   │   └── ConfirmModal.jsx
│   │   └── context/
│   │       ├── ThemeContext.jsx      # Light/dark theme
│   │       └── AnalysisContext.jsx   # SSE progress state
│   └── index.html
└── package.json
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **PostgreSQL** — via Docker or local installation
- **Google Cloud Console** project with Gmail API enabled

---

## 📚 Documentation

- **[Local Setup & Troubleshooting](docs/LOCAL_TROUBLESHOOTING.md)** — Common issues and diagnostic tools
- **[ML Model Setup](docs/LOCAL_ML_SETUP.md)** — PostgreSQL database and ML model configuration
- **[Architecture](docs/architecture.md)** — System design and data flow
- **[Deployment](docs/deployment.md)** — Production deployment guide

---

### Step 1: Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Navigate to **APIs & Services** → **Enabled APIs** → Enable **Gmail API**
4. Navigate to **APIs & Services** → **Credentials**
5. Click **Create Credentials** → **OAuth client ID**
6. Application type: **Web application**
7. Add authorized redirect URIs:
   - Development: `http://localhost:8000/auth/callback`
   - Production: `https://your-backend-domain.com/auth/callback`
8. Copy the **Client ID** and **Client Secret**

### Step 2: Get AI Provider API Keys

| Provider | Where to get it | Model used | Notes |
|----------|----------------|------------|-------|
| **Groq** (Primary) | [console.groq.com](https://console.groq.com/keys) | openai/gpt-oss-20b | 9 rotating keys for high throughput |
| **Google Gemini** (Secondary) | [aistudio.google.com](https://aistudio.google.com/) | gemini-2.0-flash | Up to 17 keys supported |
| **Cohere** (Tertiary) | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) | command-r | Fallback provider |
| **NVIDIA** (Reserved) | [build.nvidia.com](https://build.nvidia.com/) | llama-3.1-8b-instruct | Future use |

### Step 3: Get Google Safe Browsing Key (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **Safe Browsing API**
3. Create an API key under **Credentials**
4. Free tier: 10,000 lookups/day

### Step 4: Configure Environment

Create `backend/.env`:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Groq API Keys (Primary - 9 keys for rotation)
GROQ_API_KEY_1=your_groq_key_1_here
GROQ_API_KEY_2=your_groq_key_2_here
GROQ_API_KEY_3=your_groq_key_3_here
# ... add more as needed (up to GROQ_API_KEY_9)

# Gemini API keys (Google AI Studio) — https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_key_here
GEMINI_API_KEY_1=your_gemini_key_1_here
# ... up to GEMINI_API_KEY_17 (add more as needed)

# Cohere API key (optional, for rewriting only)
COHERE_API_KEY=your_cohere_key_here

# NVIDIA API key (optional, for classification only)
NVIDIA_API_KEY=your_nvidia_key_here

# Security (optional)
GOOGLE_SAFE_BROWSING_KEY=AIzaSy...

# ML Model Configuration (optional)
ML_CONFIDENCE_THRESHOLD=0.85
ML_AUDIT_SAMPLE_RATE=0.10
ML_MIN_RECALL_HIGH_RISK=0.90
```

Create `frontend/.env`:

```env
VITE_API_BASE=http://localhost:8000
```

### Step 5: Install Dependencies

```bash
# Backend (Python)
cd backend
pip install -r requirements.txt

# Frontend (Node.js)
cd ../frontend
npm install
```

### Step 6: Run in Development

Open **2 terminals**:

```bash
# Terminal 1 — Backend
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# → Runs on http://localhost:8000

# Terminal 2 — Frontend
cd frontend
npm run dev
# → Runs on http://localhost:5173
```

Then open **http://localhost:5173** in your browser.

---

## 🗄️ Database Migrations

Alembic manages versioned PostgreSQL schema changes. Run commands from `backend/` with `DATABASE_URL` loaded:

```bash
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini current
python -m alembic -c alembic.ini downgrade -1
```

The initial migration applies `postgres_schema.sql`. For isolated local verification, set `ALEMBIC_SEARCH_PATH` to a dedicated PostgreSQL schema before running `upgrade` or `downgrade`; do not run destructive downgrades against shared production data.

---

## 🌐 Deployment

### Backend (Railway)

1. Connect your GitHub repo to [Railway](https://railway.app/)
2. Add a PostgreSQL database service
3. Set environment variables in Railway dashboard
4. Configure build command: `pip install -r requirements.txt`
5. Configure start command: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`
6. Add predeploy command: `python ml_data_audit.py`

### Frontend (Vercel)

1. Connect your GitHub repo to [Vercel](https://vercel.com/)
2. Set root directory: `frontend`
3. Set environment variable: `VITE_API_BASE=https://your-railway-backend.railway.app`
4. Deploy

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/auth/login` | Trigger Google OAuth |
| GET | `/auth/callback` | OAuth callback |
| GET | `/auth/status` | Login status + user email |
| POST | `/auth/logout` | Logout + delete tokens |
| GET | `/emails` | Get analyzed emails |
| GET | `/emails/stats` | Analysis statistics |
| POST | `/emails/analyze-bulk?count=N` | Bulk analysis with custom count (1-500, streams SSE) |
| POST | `/emails/{id}/label` | Update email label |
| POST | `/emails/apply-all-pending` | Batch-apply pending labels to Gmail |
| GET | `/emails/pending-count` | Count unapplied label changes |
| POST | `/emails/batch-delete` | Batch delete by label or sender |
| POST | `/emails/{id}/reply` | Send threaded reply |
| POST | `/emails/retry-failed` | Retry failed AI analysis |
| POST | `/ai/rewrite` | AI email rewrite (supports 10k+ words) |
| GET | `/ai/status` | AI provider status |
| POST | `/security/scan-email` | Security URL scan |
| GET | `/quarantine` | List quarantined emails |
| POST | `/quarantine/{id}/safe` | Mark as safe |
| DELETE | `/quarantine/{id}` | Move to trash |
| GET | `/scam/alerts` | Get scam alerts |
| POST | `/scam/reanalyze/{id}` | Re-analyze scam score |
| GET | `/settings/labels` | Get custom labels |
| POST | `/settings/labels` | Create custom label |
| PUT | `/settings/labels/{id}` | Update label |
| DELETE | `/settings/labels/{id}` | Delete label |

---

## 🎨 Design System

**Theme**: Light Modern Minimalism + Soft Neumorphism

| Token | Light Mode | Dark Mode |
|-------|-----------|-----------|
| Background | `#F1F3F6` | `#1A1D24` |
| Surface | `#F8F9FB` | `#22262E` |
| Text Primary | `#20242C` | `#F5F6FA` |
| Text Secondary | `#687386` | `#C5C9D6` (WCAG AA) |
| Text Muted | `#9AA3B2` | `#9099AB` (WCAG AA) |
| Primary | `#5B5CE2` | `#8B8CFF` |
| Success | `#27AE72` | `#4ADE80` |
| Warning | `#E5A23C` | `#FBBF24` |
| Danger | `#E05A67` | `#FB7185` |
| Border | `#E1E5EB` | `#3A3F4B` |
| Font | Inter (Google Fonts) |
| Card Radius | 14px |
| Button Radius | 10px |
| Badge Radius | 999px (pill) |

**Neumorphic Shadows**: Soft dual-tone shadows (light/dark outset, inset) for depth without harsh borders.

---

## 🔐 Security

- All credentials stored locally in `backend/.env` — never transmitted to third parties
- OAuth tokens saved to `backend/token.json` — auto-refreshed
- URL safety results cached 24 hours in database
- Emails never leave your control — all AI analysis uses your own API keys
- PostgreSQL database (required for all environments)
- WCAG AA compliant contrast ratios for accessibility

---

## 🧪 Recent Updates (2026-09-10)

### Critical QA Fixes
1. **WCAG AA Contrast**: Improved text-secondary and text-muted contrast ratios for dark mode
2. **Privacy**: Removed public GitHub links from deployed app
3. **Custom Batch Size**: Replaced fixed dropdown with 1-500 numeric input for email analysis
4. **Rewriter Capacity**: Increased max_tokens from 1200 to 8192 — supports 10,000+ word emails
5. **Visual Consistency**: Added neumorphic bounding box to rewritten email output

---

## 📄 License

MIT License

---

## 🤝 Contributing

This is a live production deployment. For bug reports or feature requests, please open an issue.

---

**Built with ❤️ using React, FastAPI, and a multi-AI cascade architecture**
