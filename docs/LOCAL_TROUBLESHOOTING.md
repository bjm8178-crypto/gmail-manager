# Local Troubleshooting Guide

## Required Before the Backend Will Start

The backend **will not start** without these environment variables configured in `backend/.env`:

| Variable | Purpose | How to get it |
|----------|---------|---------------|
| `DATABASE_URL` | PostgreSQL connection string | See [LOCAL_ML_SETUP.md](LOCAL_ML_SETUP.md) for local PostgreSQL setup |
| `SECRET_KEY` | Session encryption | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DB_ENCRYPTION_KEY` | OAuth token encryption | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_CLIENT_ID` | Google OAuth | [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials |
| `GOOGLE_CLIENT_SECRET` | Google OAuth | Same as above |
| `GOOGLE_REDIRECT_URI` | OAuth callback | `http://localhost:8000/auth/callback` for local dev |

**Without these variables configured, the backend will fail during startup initialization.**

---

## Common Result-Card Issues

### "Analysis: Partial"

**What it means:** Email analysis completed but one or more subsystems (URL scanning, AI categorization) were unavailable.

**Root causes:**

1. **URL scanner unavailable** (`backend/gmail.py:1010–1022`)
   - `GOOGLE_SAFE_BROWSING_KEY` missing, placeholder, or quota exhausted
   - HTTP 429 rate limit exceeded
   - Network timeout or HTTP 5xx error
   - Check: `backend/security.py:scan_url()` returns `scan_failed=True`

2. **AI categorization returned label not in database** (`backend/gmail.py:1090–1098`)
   - AI provider returned valid response but label doesn't match available labels
   - User hasn't created standard labels yet (Work, Finance, Newsletter, etc.)
   - Check: Look for `[PIPELINE] AI label unavailable` warning in logs

**Fix:**
- For URL scanning: Add valid `GOOGLE_SAFE_BROWSING_KEY` to `backend/.env`
- For labels: Create Gmail labels via Settings page or manually prefix with `GM/`

---

### "Category: Unavailable"

**What it means:** AI categorization failed to assign a label.

**Root causes:**

1. **No configured AI providers** (`backend/main.py:_log_startup_configuration_warnings()`)
   - None of Groq, Gemini, or Cohere have valid API keys
   - All keys are placeholders (`your_key_here`, `replace_me`, etc.)
   - Check: Run `python backend/scripts/check_providers.py` to test providers

2. **AI cascade completely failed** (`backend/gmail.py:1075–1088`, `backend/ai_router.py:795–828`)
   - All providers returned errors or invalid JSON
   - No local ML model active as fallback
   - Check: `routed.get("category_status")` != "completed"

3. **Returned label doesn't match available labels** (`backend/gmail.py:1090–1098`)
   - AI returned label like "Shopping" but only "Work", "Finance" exist in database
   - Case-insensitive match failed
   - Check: Look for `[PIPELINE] AI label unavailable` warning with returned label

**Fix:**
- Add valid API keys for Groq (`GROQ_API_KEY`, `GROQ_API_KEY_1`, ...) or Gemini (`GEMINI_API_KEY`)
- Verify keys work: `python backend/scripts/check_providers.py`
- Ensure standard labels exist in database (created via Settings page or Gmail directly)
- For local ML fallback: See [LOCAL_ML_SETUP.md](LOCAL_ML_SETUP.md)

---

### "URL evidence: Unavailable · 0/9 checked"

**What it means:** URL security scanning did not complete for any links in the email.

**Root causes:**

1. **Safe Browsing not configured** (`backend/security.py:scan_url()` lines 165–171)
   - `GOOGLE_SAFE_BROWSING_KEY` missing or equals `"your_key_here"`
   - Returns `{"scan_failed": True, "verdict": "unavailable", "reason": "safe_browsing_not_configured"}`

2. **Rate limit exceeded** (`backend/security.py:scan_url()` lines 202–206)
   - HTTP 429 from Safe Browsing API
   - Free tier: 10,000 lookups/day
   - Returns `reason: "safe_browsing_rate_limited"`

3. **Network timeout** (`backend/security.py:scan_url()` lines 218–229)
   - Request exceeds httpx client timeout (30 seconds)
   - Returns `reason: "safe_browsing_timeout"`

4. **HTTP errors** (`backend/security.py:scan_url()` lines 207–217, 230–237)
   - HTTP 400 (bad request), 500+ (server error), or other status codes
   - Returns `reason: "safe_browsing_http_error"` or `"safe_browsing_bad_request"`

**Check logs:**
- Look for `[PIPELINE] URL scan unavailable for email <id>: <reason>` warnings (`backend/gmail.py:1020`)
- Reasons map directly to failure modes above

**Fix:**
- Add valid `GOOGLE_SAFE_BROWSING_KEY` to `backend/.env`
- Verify key works: `curl -X POST "https://safebrowsing.googleapis.com/v4/threatMatches:find?key=YOUR_KEY" -H "Content-Type: application/json" -d '{"client":{"clientId":"test","clientVersion":"1.0.0"},"threatInfo":{"threatTypes":["MALWARE"],"platformTypes":["ANY_PLATFORM"],"threatEntryTypes":["URL"],"threatEntries":[{"url":"http://malware.testing.google.test/testing/malware/"}]}}'`
- For rate limits: wait for quota reset or upgrade to paid tier

---

### "Gmail sync: Not reported"

**What it means:** Backend could not fetch emails from Gmail API.

**Root causes:**

1. **OAuth token missing or expired** (`backend/auth.py`)
   - User not logged in via Google OAuth
   - Token refresh failed
   - Check: Ensure `credentials.json` and `token.json` exist in `backend/`

2. **Gmail API quota exceeded**
   - Free tier: 1 billion quota units/day (each email fetch = ~5–10 units)
   - Check: [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Dashboard

3. **Network error or Gmail API downtime**
   - Transient HTTP errors from `googleapis.com`
   - Check backend logs for `[GMAIL]` error messages

**Fix:**
- Re-authenticate via `/auth/login` endpoint
- Check Gmail API quotas in Google Cloud Console
- Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct

---

### "Not fully assessed"

**What it means:** Generic catch-all for incomplete analysis.

**Root causes:**
- Combination of URL scanning unavailable + AI categorization unavailable
- Analysis pipeline raised an exception before completion
- Check: `analysis_status` field in database or API response

**Fix:**
- Review all subsystem fixes above (URL scanner, AI providers, OAuth)
- Check backend logs for Python exceptions during analysis

---

## Diagnostic Tools

### 1. Check AI Provider Health

Run the provider health check script to test all configured AI providers:

```bash
cd backend
python scripts/check_providers.py
```

**Expected output:**
```
Cohere: PASS
LLM7: PASS
Groq: FAIL — ProviderError: Groq API keys not configured
Gemini: FAIL — TimeoutError: exceeded 10s
...
```

**What each result means:**
- `PASS` — Provider returned valid response
- `FAIL — ProviderError` — Missing or invalid API key
- `FAIL — TimeoutError` — Request exceeded 10-second timeout
- `FAIL — HTTPStatusError` — HTTP error from provider

**Fix:** Add or rotate API keys for any `FAIL` providers in `backend/.env`

### 2. Check ML Model Status

Verify whether an active ML model is loaded:

```bash
cd backend
python ml_readiness_check.py
```

**Exit codes:**
- `0` — Active model exists and meets minimum thresholds
- `1` — No active model (AI-only fallback mode)
- `2` — Active model exists but fails quality thresholds

**See [LOCAL_ML_SETUP.md](LOCAL_ML_SETUP.md) for detailed ML setup instructions.**

### 3. Review Startup Warnings

Start the backend and check logs for configuration warnings:

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level warning
```

**Look for `[STARTUP WARNING]` messages:**
- `GOOGLE_SAFE_BROWSING_KEY is missing or a placeholder` → URL scanning unavailable
- `No usable Groq, Gemini, or Cohere API key is configured` → AI categorization will fail or use fallbacks
- `SECRET_KEY is missing` → Backend won't start
- `DB_ENCRYPTION_KEY is missing` → Backend won't start
- `No active row exists in ml_models` → ML fallback unavailable

**Fix:** Add missing keys to `backend/.env` based on warnings

### 4. Test Database Connection

Verify PostgreSQL is running and accessible:

```bash
# From docker-compose
docker-compose ps postgres

# Direct connection test
psql $DATABASE_URL -c "SELECT 1;"
```

**If connection fails:**
- Ensure PostgreSQL is running: `docker-compose up -d postgres`
- Verify `DATABASE_URL` format: `postgresql://user:password@localhost:5432/dbname`
- Check PostgreSQL logs: `docker-compose logs postgres`

---

## Quick Reference: File Locations

| Subsystem | Key Files | Function/Class |
|-----------|-----------|----------------|
| URL Scanning | `backend/security.py` | `scan_url()` (line 160+) |
| AI Categorization | `backend/gmail.py`<br>`backend/ai_router.py` | `_analyze_one()` (line 973+)<br>`analyze()` (line 795+) |
| AI Provider Status | `backend/ai_router.py` | `get_provider_status()` (line 138+) |
| ML Model Loading | `backend/ml_inference.py` | `load_active_model()` (line 27+) |
| Startup Warnings | `backend/main.py` | `_log_startup_configuration_warnings()` (line 81+) |
| Label Matching | `backend/gmail.py` | Label match logic (line 1090+) |
| Database Init | `backend/database.py` | `init_db()` (line 50+) |

---

## Additional Resources

- **ML Model Setup:** [LOCAL_ML_SETUP.md](LOCAL_ML_SETUP.md)
- **Provider Health Check:** `backend/scripts/check_providers.py`
- **Architecture Overview:** `docs/architecture.md`
- **Deployment Guide:** `docs/deployment.md`
- **Main README:** `../README.md`

---

## Support

If issues persist after following this guide:

1. Check backend logs for Python exceptions
2. Run `python backend/scripts/check_providers.py` to diagnose AI provider issues
3. Verify all required environment variables are set (see top of this document)
4. Review [LOCAL_ML_SETUP.md](LOCAL_ML_SETUP.md) for ML model troubleshooting
