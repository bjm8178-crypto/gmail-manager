# Design Proposal: Sender-Based Label Cache (`SENDER_LABEL_CACHE`)

> **Status:** Proposal / Design Note Only (Do NOT implement without explicit user approval)  
> **Target Flag:** `SENDER_LABEL_CACHE=0` (default OFF)  
> **Author:** Senior Backend Engineer  

---

## 1. Executive Summary

In high-volume email workflows, a majority of recurring transactional and notification emails originate from consistent, trusted automated senders (e.g., GitHub notifications, Jira updates, banking transaction alerts, newsletters). 

Currently, the pipeline incurs a full AI cascade call for every single email to determine the classification label, even when local ML scores are near zero and previous classifications for the sender have been 100% consistent.

This proposal outlines an opt-in, highly guarded **Sender-Based Label Cache** that skips the AI classification cascade for verified, consistent senders, drastically cutting LLM API costs and execution latency.

---

## 2. Gate Criteria & Cache Eligibility Rules

An incoming email is eligible to bypass the AI cascade **if and only if** ALL of the following conditions are met simultaneously:

1. **Consecutive Consistency:** The sender's last $\ge 3$ consecutive labeled emails (for the same `user_id` and normalized sender address) were classified with the exact same `label_id`.
2. **ML Security Clearance:** The local ML inference score (`v2_score` or `scam_score`) is strictly below the auto-clear threshold ($\le 15$).
3. **URL Scan Cleanliness:** URL security scanning status is either:
   - `not_applicable` (email contains 0 URLs), or
   - `completed` with zero threats detected (`url_threat_confirmed = False` and `urls_checked > 0`).
4. **Zero Attachments:** The email contains **no file attachments** (`attachments_info` is empty).
5. **10% Probabilistic AI Re-Check:** Even when all criteria 1–4 match, 10% of matching emails ($p = 0.10$) are randomly selected for a full AI cascade run. This serves as a continuous shadow audit to detect drift or compromised sender accounts.
6. **Feature Flag Active:** `SENDER_LABEL_CACHE=1` must be explicitly enabled in the environment.

---

## 3. Architecture & Data Model

### 3.1 Normalized Sender Extraction
Emails often arrive with complex display names:
- `"GitHub Notifications" <notifications@github.com>` $\to$ `notifications@github.com`
- `Support Team <support+promo@example.com>` $\to$ `support+promo@example.com`

Senders must be extracted via standard RFC 5322 parsing (`email.utils.parseaddr`), lowercased, and trimmed.

### 3.2 Proposed Schema

```sql
CREATE TABLE IF NOT EXISTS sender_label_cache (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    normalized_sender VARCHAR(320) NOT NULL,
    label_id INTEGER NOT NULL REFERENCES custom_labels(label_id) ON DELETE CASCADE,
    consecutive_count INTEGER NOT NULL DEFAULT 1,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (user_id, normalized_sender)
);

CREATE INDEX idx_sender_label_cache_lookup 
ON sender_label_cache (user_id, normalized_sender);
```

### 3.3 Cache Lifecycle & Eviction
- **TTL:** 14 to 30 days. Inactive senders naturally expire.
- **Cache Hit:** If cached `label_id` exists, `consecutive_count >= 3`, criteria 2–4 pass, and the 10% dice roll does not trigger re-check:
  - Assign `label_id` directly.
  - Set `routing_decision = "sender_cache"`.
  - Set `provider_used = "sender_cache"`.
  - Bump `last_seen_at`.
- **Cache Reset / Invalidation:** If an email from the sender receives a different label or fails security checks, the consecutive count drops to 1 with the new label, immediately invalidating the cache bypass.

---

## 4. Security & Spoofing Risk Analysis

> [!CAUTION]
> Email sender addresses (`From:` header) are trivially spoofed via SMTP if authentication protocols are not strictly enforced. Trusting sender headers blindly is a severe phishing vulnerability.

### 4.1 Spoofing Attack Vectors & Mitigations
1. **Header Forgery (`From:` spoofing):**
   - *Risk:* An attacker sends phishing emails using `From: service@paypal.com`. If the cache trusts `service@paypal.com`, the malicious email could bypass AI classification and receive a trusted label.
   - *Mandatory Mitigation:* **Authentication Header Verification.** The cache check MUST inspect Gmail's parsed `Authentication-Results` or headers (`SPF`, `DKIM`, and `DMARC`). If `spf != pass` or `dkim != pass`, or if DMARC fails/quarantines, the email is **ineligible** for the sender cache and must undergo full AI/ML analysis.

2. **Compromised Sender Inbox (Account Takeover):**
   - *Risk:* A trusted vendor or coworker's email account is compromised, and the attacker sends malicious links or payloads.
   - *Mitigation:* The cache is gated behind mandatory URL scanning and zero-attachment checks. If any URL is suspicious or attachments exist, the cache is bypassed. Furthermore, the 10% random re-check continuously probes the sender.

---

## 5. Accuracy & Drift Risks

1. **Multi-Intent Senders:**
   - *Risk:* A single automated domain (e.g., `updates@amazon.com`) may send shipping updates ("Orders"), promotional discount codes ("Promotions"), and password reset requests ("Security").
   - *Impact:* Consecutive 3 shipping orders might cause an incoming password reset to be erroneously labeled "Orders".
   - *Mitigation:* Senders with high variance in historical labeling across a 30-day window can be blacklisted from caching. Cache eligibility can require sender domain label purity $\ge 95\%$.

2. **User Preference Changes:**
   - *Risk:* The user creates a new label or decides they want certain emails categorized differently.
   - *Mitigation:* Immediate invalidation API hook on manual label changes (see Section 6).

---

## 6. Invalidation API

To ensure users maintain absolute control:
- **Automatic Invalidation:** Whenever a user manually changes an email's label via `PUT /emails/{id}/label` or applies a manual override, any cached entry for `(user_id, sender)` is immediately evicted:
  ```sql
  DELETE FROM sender_label_cache 
  WHERE user_id = %s AND normalized_sender = %s;
  ```
- **Label Deletion Cascade:** Foreign key `ON DELETE CASCADE` automatically invalidates entries if a custom label is deleted.
- **Admin Invalidation Endpoint:** `POST /api/sender-cache/clear` to flush user cache on demand.

---

## 7. Next Steps & Approval Gate

- [x] Design note completed and documented.
- [ ] Review by lead maintainer / user approval.
- [ ] Implementation behind `SENDER_LABEL_CACHE=0`.
