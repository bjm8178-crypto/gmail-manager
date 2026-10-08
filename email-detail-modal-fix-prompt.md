# Fix Prompt: Email Card Click Should Open a Full Detail Modal

## Problem

In `frontend/src/components/EmailCard.jsx`, clicking an email card toggles
an inline accordion (`expanded` state) that only shows `decodedSnippet`
(a short preview). It does NOT show:
- Full sender (name + email address)
- Full subject (already visible above but not repeated in the detail view)
- Full email body (only a short `snippet` is shown, not `email.body`)
- Scam score / risk label (currently a separate always-visible badge
  below the card, not part of the detail view)
- Current Gmail label

The backend already returns everything needed — no backend changes
required. `GET /emails/analyzed` → `database.py::get_analyzed_emails()`
selects `ae.body` along with `sender`, `subject`, `scam_score`,
`scam_indicators`, `label_name`, etc. (see `database.py` lines ~805-825).
The frontend just never surfaces `email.body`.

## Goal

Clicking an email card should open a **modal/dialog** (not the current
inline accordion) containing, in one place:
1. Sender name + full email address
2. Subject (full, undecoded-entities-fixed)
3. Full email body (`email.body`, fall back to `email.snippet` if body
   is empty)
4. Scam score badge with risk level, indicators, and AI reason
   (reuse existing `ScamBadge` component/logic)
5. Current label (`email.label_name`)
6. Keep existing Reply functionality, moved inside the modal

## Where to make changes

All changes are frontend-only, in:
- `frontend/src/components/EmailCard.jsx` (main change)
- Optionally extract a new `frontend/src/components/EmailDetailModal.jsx`
  component (recommended, keeps `EmailCard.jsx` from growing further)

No changes needed in:
- `backend/database.py` (body/sender/subject/scam fields already selected)
- `backend/main.py` (`/emails/analyzed` endpoint already returns them)

## How to implement

1. **Create `EmailDetailModal.jsx`**
   - Props: `email`, `senderName`, `decodedSubject`, `onClose`,
     `indicators`, plus reply state/handlers (or lift reply logic into
     the modal entirely).
   - Render as a fixed-position overlay (`position: fixed; inset: 0;
     background: rgba(0,0,0,0.4); z-index: 50;`) with a centered panel
     (`max-width: 640px`, `max-height: 85vh`, `overflow-y: auto`,
     rounded corners, `var(--color-surface)` background to match
     existing design tokens).
   - Panel sections, top to bottom:
     - Header row: sender name + email address, close (×) button
     - Subject line (larger/bold)
     - Meta row: date, current label chip
     - `ScamBadge` (score, indicators, reason) — reuse existing
       component, always expanded inside the modal (no need for the
       separate toggle state used in the card)
     - Body: render `email.body || email.snippet || 'No content available'`
       with `whiteSpace: 'pre-wrap'`, `wordBreak: 'break-word'`
     - Reply section (existing textarea + Send/Cancel, moved from
       `EmailCard.jsx`)
   - Close on: × button click, clicking the overlay background (not
     the panel itself — stop propagation on the panel), and Escape key.

2. **Update `EmailCard.jsx`**
   - Replace the `expanded`/inline-accordion behavior: clicking the
     card body sets a new `modalOpen` state to `true` instead of
     toggling `expanded`.
   - Remove the "Expanded Content (Full Email Snippet)" block
     (lines ~361-449) — that content moves into the modal.
   - Keep the always-visible `ScamBadge` teaser below the card as-is
     (optional — could also remove it now that score is in the modal,
     your call), but stop passing `scamExpanded` toggle logic to it if
     you keep both, or drop it if the modal is now the single source
     for full scam details.
   - Render `<EmailDetailModal ... />` conditionally when `modalOpen`
     is true, passing `email`, `senderName`, `decodedSubject`,
     `indicators`, and an `onClose={() => setModalOpen(false)}`.
   - Move `replyOpen`, `replyBody`, `sending`, `handleSendReply` either
     into the modal component or keep in `EmailCard.jsx` and pass down
     as props — either works, moving them into the modal is cleaner.

3. **Sender email address**
   - `senderName` currently strips everything after `<` to get just
     the display name. Add a `senderEmail` extraction (regex match
     `/<(.+)>/` on `email.sender`, fallback to raw `email.sender` if no
     angle brackets) so the modal can show both name and address.

4. **Styling**
   - Reuse existing CSS variables already used throughout the file
     (`--color-surface`, `--color-border`, `--color-text-primary`,
     `--color-text-secondary`, `--color-primary`) so the modal matches
     the rest of the light design system — no new tokens needed.

## Acceptance criteria

- Clicking anywhere on an email card (outside the label dropdown and
  status badges, matching current click-target behavior) opens a
  modal showing sender name+email, full subject, full body text, scam
  score with indicators/reason, and current label.
- Modal closes via ×, background click, or Escape.
- Reply still works, now from inside the modal.
- No backend/API changes.
- No regressions to the label dropdown `onChange`/`onLabelChange`
  behavior or the "Analyzing.../Failed" status badges on the card face.
