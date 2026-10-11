# Hybrid ML + AI Cascade — Risk Assessment & Implementation Plan

**Goal:** insert a locally-trained ML layer in front of the existing AI cascade (NVIDIA → Gemini → Cohere) so that only genuinely uncertain emails reach the AI, while scam-detection safety is never weakened.

---

## PART 1 — Risk Assessment (read this before writing any code)

Each risk is rated by **impact** (what breaks) and paired with the specific mitigation that gets built into the plan in Part 2.

### A. Data risks

| # | Risk | Why it happens | Impact | Mitigation |
|---|------|-----------------|--------|------------|
| A1 | **Not enough training data at launch** | `analyzed_emails` may only have a few hundred/thousand rows depending on how long the tool's been used | Model overfits, unreliable on edge cases | Enforce a **minimum row count gate** (e.g. 500+ per label) before the local model is allowed to serve *any* production traffic. Below that, run in shadow mode only (Part 2, Phase 6). |
| A2 | **Class imbalance** | Most email is legitimate; scam emails are a small minority | A naive model can hit 95%+ "accuracy" by always predicting "safe" and miss every scam | Never optimize for accuracy. Track **precision/recall per class**, especially recall on high-scam-score emails. Use `class_weight='balanced'` in scikit-learn, and/or oversample the minority class. |
| A3 | **Label noise inherited from the AI cascade** | The AI cascade itself is imperfect — the local model will learn its mistakes too, including any provider-specific quirks (NVIDIA vs Gemini vs Cohere may disagree) | Model reproduces existing AI blind spots confidently | Track which AI provider produced each historical label (you already log `provider_used` in timing logs — persist it). Down-weight or exclude labels from providers with lower historical agreement rates once you have data to compare them. |
| A4 | **Feedback loop bias (the subtle one)** | Once the local model handles most "easy" emails, only the *hard* ones keep going to the AI cascade and generating new training data. The model never gets corrected on the confident predictions it handles alone. | The model can drift and become **confidently wrong** on a whole category of email, and nothing in the normal flow would catch it | Mandatory **random audit sampling**: even when the local model is confident enough to skip AI, route a small random percentage (e.g. 3–5%) to the AI cascade anyway, purely to keep measuring true accuracy on the "easy" bucket. This is not optional — without it you lose your only signal that the shortcut is still correct. |

### B. Feature engineering risks

| # | Risk | Why it happens | Impact | Mitigation |
|---|------|-----------------|--------|------------|
| B1 | **Feature leakage** | Accidentally including a feature derived from the *AI's own output* (e.g. training on `label_id` as an input feature to predict `label_id`) | Model looks perfect in testing, fails completely on new emails | Explicit feature/target separation checklist before every training run — inputs are only: subject, sender, body/snippet, structural signals (URLs, headers, SPF/DKIM), historical sender stats. Never the AI's label or score as an input. |
| B2 | **Sender spoofing defeats sender-reputation features** | Scammers spoof trusted display names/domains | A high-reputation "sender" feature could mask a spoofed scam email | Sender reputation is only ever a *supporting* signal, never sufficient alone to auto-clear an email as safe. Structural/text signals must independently agree. |
| B3 | **TF-IDF vocabulary drift** | New scam campaigns use new phrasing not in the training vocabulary | Model's text features go "blind" on genuinely novel attacks | This is exactly why confidence calibration + escalation to AI matters (Part 1C) — novel phrasing should produce low confidence, triggering AI fallback rather than a false "safe." Validate this assumption explicitly during evaluation (Phase 3). |

### C. Model / confidence risks

| # | Risk | Why it happens | Impact | Mitigation |
|---|------|-----------------|--------|------------|
| C1 | **Raw confidence scores are not trustworthy** | `predict_proba()` from an uncalibrated classifier does not mean what it looks like it means — a "0.9" is not actually 90% likely to be correct | Threshold-based routing silently mis-fires, either escalating too much (no savings) or too little (safety risk) | Mandatory **calibration step** using `CalibratedClassifierCV` (isotonic regression) on a held-out slice before any threshold is chosen. Threshold must be picked by measuring actual error rate at each confidence level on your own data — never picked by intuition. |
| C2 | **Asymmetric cost of errors** | A false "safe" on a real scam is far worse than an unnecessary AI call on a real newsletter | A single global confidence threshold treats both error types as equally bad | Use **two different thresholds**: a strict, high-confidence bar to auto-clear something as low-risk, and a much more permissive bar (near-automatic escalation) for anything with even weak scam signals. When in doubt, escalate — never auto-suppress on uncertainty. |
| C3 | **Model degrades silently over time (concept drift)** | Scam tactics evolve; "normal" email patterns shift | Cascade quietly gets worse without anyone noticing until a real incident happens | Continuous disagreement tracking between local model and AI cascade (every escalated case is also a drift-detection sample). Alert / auto-flag when disagreement rate crosses a set threshold. Scheduled retrain is a backstop, not the primary trigger. |

### D. Integration / systems risks (specific to this codebase)

| # | Risk | Why it happens | Impact | Mitigation |
|---|------|-----------------|--------|------------|
| D1 | **Model file lost on redeploy** | Railway's default filesystem is ephemeral — a redeploy wipes anything not in a persisted volume or the DB | Trained model silently disappears, service falls back to... nothing, or crashes | Store the serialized model as `bytea` in Postgres (you already have Postgres provisioned), or attach a Railway volume. Load at startup from DB, not from a local file written during a previous deploy. |
| D2 | **Blocking model load/inference on the event loop** | `main.py` is `async` FastAPI; loading a joblib model or running `sklearn` inference is synchronous CPU work | If called directly in an `async def` without `asyncio.to_thread`, it blocks the whole event loop for every concurrent request — same class of bug as the earlier DB pool issue | Load the model **once** at startup (module-level singleton), and wrap `predict()` calls in `asyncio.to_thread()` inside `_analyze_one`, same pattern already used for Gmail API calls. |
| D3 | **Retraining job blocks production traffic** | Training even a small TF-IDF + LogisticRegression model is CPU-bound and can take real time on Railway's shared CPU | If run inline in a request handler, it stalls the single-worker FastAPI process for everyone | Run retraining as a **separate background task or a dedicated script triggered manually / via cron**, never inline in a request. Write the new model version to the DB only after it passes validation — never overwrite the live model mid-training. |
| D4 | **Concurrent model swap causes a race** | If a retrain finishes while requests are actively calling `predict()` on the old in-memory model object | Inconsistent predictions mid-swap, or a crash if the object is replaced non-atomically | Load the new model into a new variable, validate it, then do a single atomic reference swap (Python attribute assignment is atomic under the GIL) — never mutate the existing model object in place. |
| D5 | **PyInstaller/Electron bundling breaks with scikit-learn** | The desktop build (`pyinstaller --onefile`) can miss scikit-learn's compiled extensions or hidden imports, especially for algorithms with joblib-serialized objects | Desktop app fails to start or crashes only in the packaged build, not in dev | Test the full `pyinstaller` build early (Phase 7) with a dummy sklearn model bundled in, before writing the real training pipeline. Add explicit `--hidden-import` flags for `sklearn`, `scipy`, `joblib` as needed; budget extra time for this — it's a known pain point. |
| D6 | **This adds a second source of truth for "why was this email labeled X"** | Now there are two code paths (ML and AI) that can produce a label | Debugging becomes harder ("why did this get flagged?") without clear provenance | Every row in `analyzed_emails` must record **which system produced the result** (`source: 'ml'` vs `source: 'ai'` vs `source: 'ai_ml_disagreed'`) and, for ML-sourced rows, the confidence score. This is non-negotiable for both debugging and for auditing safety later. |

### E. Safety-specific risks (this is a security product — treat this section as highest priority)

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| E1 | **Local model auto-clears a real scam as safe** | User is exposed to phishing/fraud the tool was built to catch | The ML layer is only ever allowed to **skip AI on the "definitely safe" side**. It must never be allowed to independently suppress a quarantine action or auto-clear a high-risk score — any non-trivial risk signal (unknown sender + URLs + urgency language, etc.) always escalates to AI regardless of ML confidence. |
| E2 | **Adversarial emails crafted to game the local model** | Attackers who know (or guess) you're using a lightweight local classifier could craft emails that dodge its specific text patterns while still being obviously suspicious structurally | Structural signals (SPF/DKIM fail, mismatched sender domain, URL count/reputation) are weighted independently of text-based features — an email can't "talk its way past" the model on text alone if the structural signals disagree. |
| E3 | **No human-visible audit trail for ML-only decisions** | If something goes wrong, there's no way to explain after the fact why an email wasn't flagged | Log confidence + feature summary (not full body, to control storage) for every ML-only decision so any case can be reviewed later. |

---

## PART 2 — Step-by-Step Implementation

Each phase lists **what to build**, **the risks from Part 1 it directly addresses**, and **a checkpoint before moving on**.

### Phase 0 — Data audit (do this before writing any training code)
- Query `analyzed_emails` grouped by `label_id` and by `scam_score` bucket to check for class imbalance (A2).
- Check row counts per label against the minimum-data gate (A1).
- Spot-check ~30 random rows manually against their AI-assigned label/score to sanity-check label quality (A3).
- **Checkpoint:** you have a documented count per class and a go/no-go on whether there's enough data yet. If not, let the AI cascade keep running as-is for a few more weeks before proceeding — this whole project depends on this data being decent.

### Phase 1 — Schema changes
Add to `analyzed_emails` (or a new companion table):
- `source` (`'ai'` | `'ml'` | `'ml_audit_escalated'`)
- `ml_confidence` (nullable float)
- `provider_used` (persist what's already computed in timing logs today, for A3)

New table `ml_models`:
- `model_id`, `version`, `trained_at`, `training_row_count`, `validation_precision`, `validation_recall`, `calibration_error`, `model_blob` (bytea) or `storage_ref`, `is_active` (bool)

New table `ml_disagreements` (drift signal, C3):
- `email_id`, `ml_prediction`, `ml_confidence`, `ai_prediction`, `agreed` (bool), `logged_at`

**Addresses:** D1, D6, C3, E3
**Checkpoint:** migrations run cleanly on both dev SQLite and prod Postgres (reuse the existing dual-syntax pattern from `database.py`).

### Phase 2 — Feature extraction module
- New `backend/features.py`: pure functions, no DB/network calls, so it's trivially unit-testable.
- Inputs: subject, sender, body/snippet, URL count, List-Unsubscribe presence, SPF/DKIM pass/fail, sender's historical stats (joined separately, not computed inline).
- Explicitly document what is *not* a feature (B1) — no AI-produced label/score as input, ever.
- **Checkpoint:** run this over 50 real historical emails and manually verify the output feature vectors look sane (no leakage, no nulls where you didn't expect them).

### Phase 3 — Offline training + calibration script
- `backend/train_ml_model.py`, run manually/offline first (not wired into the live app yet).
- Split data: train / calibration / held-out validation (e.g. 70/15/15).
- Train the base classifier(s) with `class_weight='balanced'` (A2).
- Wrap with `CalibratedClassifierCV` (C1) using the calibration split.
- Evaluate on the held-out validation split: **precision/recall per class**, not accuracy (A2), plus expected calibration error (C1).
- Save results into the `ml_models` table as a candidate (`is_active = false`).
- **Checkpoint:** candidate model must beat a defined minimum bar (you set this — e.g. recall ≥ 0.95 on high-scam-score class) before it's even eligible to be activated. If it doesn't, more data or better features are needed — do not lower the bar to make the number work.

### Phase 4 — Threshold selection
- Using the held-out validation set, plot calibrated-confidence vs actual-error-rate.
- Pick **two thresholds** (C2): a strict "auto-clear as safe" threshold, and a much looser "any risk signal → escalate" rule that isn't confidence-gated at all — it's rule-based (E1).
- Document the chosen thresholds and the validation numbers that justified them, stored alongside the model version in `ml_models`.
- **Checkpoint:** you can point to a specific number (e.g. "false-negative rate on scam ≥ 0.85 confidence bucket is 0.4%") that justifies the threshold, not a guess.

### Phase 5 — Shadow mode (no production impact yet)
- Wire the model into `_analyze_one`, but **only log** what it would have predicted — the AI cascade still runs for every email, unchanged.
- Populate `ml_disagreements` for every email during this period.
- Run for a defined window (e.g. 1–2 weeks or N thousand emails, whichever comes first).
- **Checkpoint:** review agreement rate and confirm it matches what Phase 3/4 predicted. If shadow-mode agreement is meaningfully worse than validation numbers, stop and investigate before going further — this is your last safety net before the model touches real decisions.

### Phase 6 — Live routing with escalation (Part 1 D2, E1 baked in)
- Model loaded once at startup as a singleton; `predict()` wrapped in `asyncio.to_thread()`.
- Routing logic in `_analyze_one`:
  1. Any structural risk signal present → always go to AI cascade, skip ML entirely (E1).
  2. Otherwise, run ML model. If calibrated confidence ≥ strict threshold → use ML result, log `source='ml'`.
  3. Random ~3–5% audit sample even on confident ML results → escalate to AI anyway, log agreement (A4).
  4. Everything else → AI cascade as today, log `source='ai'`.
- **Checkpoint:** run on a small subset of real traffic first if possible (e.g. gate behind a feature flag / percentage rollout), watch `ml_disagreements` closely before expanding to 100%.

### Phase 7 — Desktop build compatibility check
- Before this goes further, do a throwaway `pyinstaller --onefile` build with a dummy sklearn model bundled in and confirm the packaged Electron app actually starts (D5).
- Add any needed `--hidden-import` flags now, not after the real pipeline is built around it.

### Phase 8 — Retraining automation
- Standalone script or scheduled job (not inline in request handling — D3).
- Pulls all data since last training run, retrains, validates against the same bar as Phase 3.
- New model only becomes `is_active = true` if it beats the currently active model's validation numbers — otherwise it's discarded and logged, not deployed (D4 — atomic swap only after validation passes).
- Retrain trigger: either a schedule (e.g. weekly) **or** disagreement-rate threshold crossed (C3) — whichever comes first.

### Phase 9 — Ongoing monitoring
- Dashboard or simple periodic report: agreement rate trend, precision/recall trend across model versions, audit-sample results.
- Alert (even just a log line you check, to start) if disagreement rate spikes.

---

## What "done" looks like
- The AI cascade is still the safety backstop for anything genuinely uncertain or risky — it never gets bypassed.
- Every decision has a clear, queryable provenance (`source`, `ml_confidence`, model version).
- You have a documented, data-justified threshold — not a guessed one.
- A retrain can happen without touching live traffic, and a bad retrain can't silently replace a good model.
- You have a continuous, cheap way (audit sampling + disagreement logging) to know if the model is still correct, not just a one-time validation number from months ago.
