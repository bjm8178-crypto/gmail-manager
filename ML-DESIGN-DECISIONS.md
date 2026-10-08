# ML Hybrid Pipeline - Design Decisions

## ML Model Scope: Risk-Only Classification

**Decision**: The ML model predicts binary risk (high_risk vs low_risk) only, NOT category labels (Marketing, Personal, Promotions, etc.).

### Rationale

1. **Simplicity**: Binary classification is more robust with limited training data (500+ rows) than multi-class classification (which would need 500+ rows per category).

2. **Safety-focused**: The primary goal is cost reduction by handling "obviously safe" emails locally. Scam detection is the critical safety feature.

3. **Data requirements**: Multi-class would need 500+ examples per category × N categories = much larger dataset before training.

### Tradeoff

**ML-routed emails get generic labels**:
- High-risk emails → "Spam" 
- Low-risk emails → Default label (typically "Safe" or first available label)

This means ML-handled emails lose rich categorization (Marketing, Personal, etc.) that the AI cascade provides.

### When This Matters

- If users rely on granular auto-labeling (Marketing, Promotions, etc.), the 40-60% of emails handled by ML will be labeled generically
- The AI cascade still provides full categorization for the 40-60% of emails it handles (uncertain cases, structural risks, audit samples)

### Future Enhancement Option

To add category prediction, the model would need:
1. Multi-class classifier trained on label_id (not just risk)
2. Minimum 500+ examples per label category
3. Higher confidence threshold (harder to be confident across N categories vs 2 risk levels)
4. More complex feature engineering (category signals differ from scam signals)

This is deferred to avoid delaying the cost-saving risk-only model until much more data accumulates.

---

## Bug Fixes Applied (2026-08-19)

### Bug 1: Incorrect scam_score threshold (float vs int)
- **Location**: `features.py:191`, `train_ml_model.py:72`
- **Issue**: `scam_score >= 0.6` treated scam_score as 0-1 float, but it's stored as 0-100 integer
- **Impact**: Nearly every nonzero-score email labeled as high_risk, corrupting training labels and sender reputation
- **Fix**: Changed to `scam_score >= 60` (integer threshold)

### Bug 2: ML model not loaded at startup
- **Location**: `main.py`
- **Issue**: `load_active_model()` imported but never called in startup handler
- **Impact**: `is_model_available()` always returns False, ML layer never activates even after training
- **Fix**: Added `load_active_model()` call in `@app.on_event("startup")`

### Cleanup: Removed dead code
- **File**: `ml_runtime.py` deleted (unused, no imports)
