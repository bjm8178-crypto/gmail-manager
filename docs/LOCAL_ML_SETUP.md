# Local ML Setup Guide

## Overview

This guide documents how to start the PostgreSQL database locally and verify the ML model infrastructure **without training, running the full stack, or making live predictions**. It covers:

1. Starting the PostgreSQL service only
2. Setting the database connection string
3. Applying the schema
4. Checking for active ML models
5. Understanding model activation and readiness checks

## Prerequisites

- Docker and Docker Compose installed
- Python 3.14 installed at `C:/Python314/python.exe`
- Repository cloned to local machine

## 1. Start PostgreSQL Service Only

The `docker-compose.yml` defines three services: `postgres`, `backend`, and `frontend`. To start **only the database**:

```bash
docker-compose up -d postgres
```

This starts:
- PostgreSQL 15 container named `gmail-postgres`
- Database: `gmail_manager`
- User: `postgres`
- Port: `5432` (mapped to host)
- Auto-initialization: runs `backend/postgres_schema.sql` on first start

Verify the service is healthy:

```bash
docker-compose ps postgres
```

Expected output should show `State: Up (healthy)`.

## 2. Set DATABASE_URL (Local Development)

The application requires `DATABASE_URL` to connect to PostgreSQL. **SQLite is disabled** in this repository.

### Format

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

### Example (Placeholder Credentials)

**For local development with the docker-compose postgres service:**

```bash
# In backend/.env or your shell environment
DATABASE_URL=postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager
```

**Replace `YOUR_LOCAL_PASSWORD` with the actual password set in `docker-compose.yml` under `postgres.environment.POSTGRES_PASSWORD`.**

**Security note:** Never commit real passwords. The docker-compose file contains a password environment variable that should be set securely or overridden via `.env`.

### Verification

Test the connection with psql or a Python script:

```bash
# Using psql (if installed)
psql "postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager" -c "\dt"

# Using Python
C:/Python314/python.exe -c "import os; os.environ['DATABASE_URL']='postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager'; from database import _get_connection; conn=_get_connection(); print('✓ Connected'); conn.close()"
```

## 3. Apply Schema

The schema is automatically applied when the PostgreSQL container starts for the first time (via `docker-entrypoint-initdb.d/schema.sql`).

### Schema Source

`backend/postgres_schema.sql` defines 10 tables:
- Core tables: `users`, `custom_labels`, `scan_cursor`, `analyzed_emails`, `url_cache`, `retry_queue`, `dead_letter_queue`, `audit_log`
- **ML tables**: `ml_models`, `ml_disagreements`

### Manual Schema Application

If you need to reapply the schema to an existing database:

```bash
# Direct SQL execution
psql "postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager" -f backend/postgres_schema.sql
```

### Using Alembic Migration (Alternative)

The repository includes an Alembic migration at `backend/migrations/versions/0001_initial_schema.py` that wraps `postgres_schema.sql`.

To apply via Alembic:

```bash
cd backend
export DATABASE_URL="postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager"
C:/Python314/python.exe -m alembic upgrade head
```

**Note:** Alembic requires `DATABASE_URL` or `ALEMBIC_DATABASE_URL` to be set (see `backend/migrations/env.py`).

## 4. Check for Active ML Models

### Query Active Model

Connect to the database and check the `ml_models` table:

```sql
SELECT model_id, version, trained_at, is_active, validation_recall
FROM ml_models
WHERE is_active = 1
ORDER BY trained_at DESC
LIMIT 1;
```

**Expected result on a fresh database:** No rows (empty result).

A model must be trained and explicitly activated before `is_active = 1` appears.

### Using Python Script

List all models and their metrics:

```bash
cd backend
export DATABASE_URL="postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager"
C:/Python314/python.exe activate_model.py
```

**Expected output on fresh database:**
```
================================================================================
AVAILABLE ML MODELS
================================================================================
No models found. Run train_ml_model.py first.
================================================================================
```

## 5. Model Activation Process

### Overview

The ML workflow has distinct phases:

1. **Data Collection**: AI cascade analyzes emails and stores results in `analyzed_emails`
2. **Readiness Check**: `ml_readiness_check.py` verifies sufficient training data exists
3. **Training**: `train_ml_model.py` creates a model and stores it in `ml_models` (not documented here)
4. **Activation**: `activate_model.py` marks a trained model as active
5. **Runtime**: `ml_inference.py` loads the active model at FastAPI startup

### Check Training Readiness

Verify if enough labeled data exists to train a model:

```bash
cd backend
export DATABASE_URL="postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager"
C:/Python314/python.exe ml_readiness_check.py
```

**Requirements** (from `ml_readiness_check.py`):
- Minimum 500 total labeled rows (`MIN_TRAINING_ROWS`)
- Minimum 50 high-risk emails (scam_score ≥ 60) (`MIN_ROWS_PER_CLASS`)
- Minimum 50 low-risk emails (scam_score < 60) (`MIN_ROWS_PER_CLASS`)

**Expected output on empty database:**
```
======================================================================
ML TRAINING READINESS CHECK
======================================================================

Current data status:
  Total labeled rows: 0 (need 500+)
  Low-risk rows:      0
  High-risk rows:     0 (need 50+)

----------------------------------------------------------------------
STATUS: NOT READY - Keep collecting data
[...]
```

**Exit codes:**
- `0`: Ready to train
- `1`: Not ready (insufficient data)
- `2`: Error during check

### Activate a Trained Model

After a model is trained (outside scope of this document), activate it:

```bash
cd backend
export DATABASE_URL="postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager"
C:/Python314/python.exe activate_model.py <model_id>
```

**What this does** (from `activate_model.py`):
1. Verifies the model exists in `ml_models`
2. Checks minimum recall threshold (≥ 0.90)
3. Atomically deactivates all other models
4. Sets `is_active = 1` for the target model

**Requirements:**
- Model must have `validation_recall >= 0.90` to activate
- Only one model can be active at a time

**Output example:**
```
✓ Model 1 activated successfully
  Recall: 0.953, Calibration error: 0.0234

Restart the FastAPI server to load the new model.
```

## 6. Archived Model Metadata

The repository contains a pre-trained model reference at `backend/archive/model_metadata_v3.json`.

**Metadata summary:**
- Model version: v3
- Type: Random Forest
- Training date: 2026-09-11
- Total training samples: 202,882 (204,434 after dedup)
- Features: URL count, IP URLs, exclamation marks, urgency, body length, uppercase ratio, writing style, TF-IDF
- Test accuracy: 94.75%
- High-risk recall: 95.01%

**Important:** This JSON file is metadata only. The actual model binary (`.pkl`) is **not** present in the repository archive.

### Importing Archived Models

**No importer script currently exists.** The documented Python files (`ml_readiness_check.py`, `ml_inference.py`, `activate_model.py`) do not include functionality to import archived model binaries into the `ml_models` table.

**If you need to import an archived model:**
- A script like `backend/import_archived_model.py` would need to be written
- It would need to:
  1. Load the pickled model binary from disk
  2. Compute SHA-256 hash of the blob
  3. Insert into `ml_models` with metadata and hash
  4. NOT set `is_active = 1` (use `activate_model.py` after import)

**This is a proposed workflow, not an existing command.**

## 7. Runtime Model Loading

When the FastAPI backend starts (`backend/main.py`), it calls `ml_inference.load_active_model()` during the lifespan startup phase.

**What happens** (from `ml_inference.py`):
1. Queries `ml_models` for the row where `is_active = 1`
2. If no active model exists: logs "No active model found. Running AI-only mode." and continues startup
3. If active model exists:
   - Verifies SHA-256 hash of `model_blob` against `model_hash` (if present)
   - Unpickles the model (safe: blob only written by trusted `train_ml_model.py`)
   - Caches in module-level `_MODEL_CACHE`
   - Logs version and recall metric

**No active model = not an error.** The application runs in AI-only mode until a model is trained and activated.

## 8. Common Verification Commands

```bash
# Check if postgres is running
docker-compose ps postgres

# Check if ml_models table exists
psql "postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager" -c "\d ml_models"

# Count rows in analyzed_emails (training data source)
psql "postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager" -c "SELECT COUNT(*) FROM analyzed_emails WHERE label_id IS NOT NULL AND scam_score IS NOT NULL;"

# Check for active models
psql "postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager" -c "SELECT version, is_active, validation_recall FROM ml_models;"

# Run readiness check
cd backend && DATABASE_URL="postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/gmail_manager" C:/Python314/python.exe ml_readiness_check.py
```

## 9. Limitations and Caveats

### What This Guide Does NOT Cover

- **Training**: How to run `train_ml_model.py` (requires sufficient data + feature engineering setup)
- **Live Predictions**: Calling the prediction API or running the full backend
- **Data Collection**: Setting up Gmail OAuth, AI providers, or running email analysis
- **Archived Model Import**: No existing script to load `archive/*.pkl` files into database
- **Production Deployment**: Railway-specific configuration, secrets management, or CI/CD

### Security Notes

- Never log, commit, or expose `DATABASE_URL` values containing real passwords
- The `model_blob` in `ml_models` is a pickled scikit-learn artifact—only trust models trained by this repository's code
- Hash verification (`model_hash`) prevents tampering; models trained before hash support (pre-H4) log a warning

### Database Dependencies

- `ml_inference.py` imports from `database.py`, `features.py`, and `logger_setup.py`
- `activate_model.py` and `ml_readiness_check.py` use `database._get_connection()`, `_release_connection()`, `_execute()`
- All scripts assume PostgreSQL (SQLite is explicitly disabled in `database.py`)

## 10. Next Steps

After verifying local database connectivity:

1. **To train a model**: Collect labeled email data via the AI cascade, verify readiness, then run `train_ml_model.py` (not covered in this guide)
2. **To test the full stack**: Start all services with `docker-compose up -d` and configure OAuth + AI provider credentials
3. **To inspect a trained model**: Use `activate_model.py` (no arguments) to list all models and their metrics

---

**Document Status**: Grounded in repository source files as of 2026-10-08. Commands verified against `docker-compose.yml`, `postgres_schema.sql`, `ml_readiness_check.py`, `ml_inference.py`, `activate_model.py`, and `archive/model_metadata_v3.json`.
