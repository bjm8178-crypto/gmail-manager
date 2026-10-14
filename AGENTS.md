# Gmail Intelligence Manager

Capstone web app. Classifies emails from live Gmail inboxes (Gmail API) with a rule-based classifier plus a cascading AI pipeline, scans URLs/attachments, and applies labels. Backend FastAPI, frontend React + Vite.

## Deployment (don't assume anything else)
- Backend: Render (`render.yaml`, runs `cd backend && uvicorn main:app`)
- Database: Supabase Postgres (Postgres only, no SQLite)
- Frontend: Cloudflare (`frontend`, `npm run build`); `infra/cloudflare-worker.js` proxies `/api/*` to the backend
- Ignore Vercel, Railway, Docker, Electron: not part of the deployed system

## Where things live (`backend/`)
- `main.py`: routes, startup, middleware (large: grep, don't read whole)
- `gmail.py`: Gmail API, label application, sync, analysis pipeline
- `database.py`: all SQL (psycopg2 pool), retry queue, ownership checks (`user_id` required)
- `ai_router.py`: cascading AI providers (Groq, Gemini, Cohere, others), key loading
- `ml_inference.py`, `predict.py`, `v2_routing.py`, `decision_policy.py`, `quarantine_policy.py`: classification and routing
- `scheduler.py`: background jobs
- `auth.py`, `jwt_auth.py`, `csrf.py`, `security.py`, `encryption.py`, `audit.py`: security. Be careful here and keep tests passing
- `attachment_scanner.py`: attachment and Safe Browsing URL scanning
- Frontend: `frontend/src/pages/Inbox.jsx` is the main screen

## Testing (important)
- Python 3.11. Tests are in `backend/tests/` and `backend/pytest.ini`.
- Run only the test file for the code you changed:
  `cd backend && pytest tests/test_<name>.py -q --no-cov`
- Never run the full suite, `tests/integration/`, or `test_performance_baseline.py` unless asked. They load the real `.env` and can hit the real database and AI keys.
- Do not run anything with `isolated_runner.py`.
- Test files by area: `test_database_*` (database.py), `test_ai_router_*` (ai_router.py), `test_label_*` and `test_bulk_label` (labels), `test_retry_*` and `test_exact_retry_ids` (retry queue), `test_auth_*` and `test_csrf_*` (auth), `test_scheduler` (scheduler).
- When adding a feature, add or extend one test in the matching existing file. Don't create new test files.

## Don't touch or read
- `backend/.env`, `.env.docker`, `backend/tokens/`
- `backend/scam_classifier_v2.pkl` (live model, binary)
- `docs/archive/`, `CHANGELOG.md` (unless asked), `node_modules/`, `htmlcov/`, `logs/`

## Doing a fix
1. Locate the code with grep. Read only the relevant function.
2. Make the smallest change that fixes it, keeping the existing style.
3. Run the one related test file. If none covers it, say so; don't write a big new test.
4. Report in at most 5 lines.

## Doing a new feature
- Backend: route in `main.py`, logic in the matching module, SQL only in `database.py`.
- Frontend: reuse existing components in `frontend/src/`. Don't add dependencies without asking.
- Any DB schema change needs a migration in `backend/migrations/` plus `postgres_schema.sql`; tell me before you do it.