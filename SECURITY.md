# Security Guidelines

## 🔒 Secrets Management

### Never Commit These Files
- `.env` - Environment variables with API keys
- `backend/token.json` - OAuth tokens
- `backend/tokens/` - User OAuth tokens
- `backend/*.pkl` - ML models (may contain training data)
- `backend/gmail_manager.db` - User database
- Any file containing actual API keys or credentials

### Safe to Commit
- `.env.example` - Template with placeholder values
- Code files that read from environment variables
- Configuration files without hardcoded secrets

---

## 🛡️ Repository Security Checklist

### Before Every Commit
- [ ] Check for hardcoded API keys/secrets
- [ ] Ensure `.env` is in `.gitignore`
- [ ] Verify README.md has placeholder values only
- [ ] ML model files are not being committed (large binaries)
- [ ] No database files being committed

### Check Current Repository
```bash
# Search for potential secrets
git grep -i "api.key\|secret\|password" -- . ':(exclude).gitignore' ':(exclude)SECURITY.md'

# Check what will be committed
git status
git diff --cached

# Check .gitignore is working
git check-ignore -v backend/.env
```

---

## 🚨 If Secrets Were Exposed

### Immediate Actions
1. **Rotate all exposed credentials immediately**
   - Google OAuth: Delete and create new credentials
   - API keys: Regenerate all exposed keys
   - Database: Change passwords

2. **Remove from Git history**
   ```bash
   # Remove sensitive file from all history
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/file" \
     --prune-empty --tag-name-filter cat -- --all
   
   # Force push (⚠️ WARNING: rewrites history)
   git push origin --force --all
   ```

3. **Notify affected services**
   - Revoke compromised API keys
   - Monitor for unauthorized usage
   - Enable 2FA where possible

---

## 🔐 Environment Variable Setup

### Development (Local)
1. Copy template:
   ```bash
   cp .env.example .env
   ```

2. Fill in actual values in `.env`

3. Never commit `.env`

### Production (Railway)
1. Set environment variables in Railway dashboard
2. Never hardcode in code
3. Use Railway's secret management

### Frontend (Vercel)
1. Set in Vercel project settings > Environment Variables
2. Prefix public vars with `VITE_` only if they should be exposed to browser
3. Keep API keys server-side only

---

## 📋 Secure Coding Practices

### API Keys
```python
# ✅ GOOD - Read from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ❌ BAD - Hardcoded
GROQ_API_KEY = "gsk_1234567890abcdef"
```

### Database Credentials
```python
# ✅ GOOD - From environment
DATABASE_URL = os.getenv("DATABASE_URL")

# ❌ BAD - Hardcoded connection string
DATABASE_URL = "postgresql://user:password@host/db"
```

### OAuth Tokens
```python
# ✅ GOOD - Store in database or secure file
# Already implemented in auth.py

# ❌ BAD - Commit token.json to git
```

---

## 🔍 Pre-Commit Checks

### Automated Scanning (Optional)
Install `git-secrets`:
```bash
# Install
git secrets --install

# Scan for secrets
git secrets --scan

# Add patterns
git secrets --add 'gsk_[a-zA-Z0-9]+'  # Groq keys
git secrets --add 'AIzaSy[a-zA-Z0-9_-]+'  # Google API keys
```

### Manual Review
Before committing:
```bash
# Review changes
git diff

# Check for common secret patterns
git diff | grep -i "key\|secret\|password\|token"
```

---

## 📞 Reporting Security Issues

If you discover a security vulnerability:
1. **Do NOT open a public issue**
2. Email: [your-security-email@domain.com]
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

---

## ✅ Current Security Status

### Protected by .gitignore
- [x] Environment files (.env)
- [x] OAuth tokens (token.json, tokens/)
- [x] Database files (*.db)
- [x] ML models (*.pkl)
- [x] Log files (*.log)
- [x] Backup files (*.backup)

### Code Reviews
- [x] No hardcoded secrets in Python code
- [x] No hardcoded secrets in JavaScript code
- [x] README.md contains placeholders only
- [x] Environment variables properly documented

### Additional Measures
- [x] Railway environment variables encrypted at rest
- [x] Vercel environment variables encrypted at rest
- [x] Database uses connection pooling with encrypted connections
- [x] OAuth tokens stored securely in database
- [x] HTTPS enforced in production

---

Last Updated: 2026-09-18
