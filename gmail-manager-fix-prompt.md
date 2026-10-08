# Fix Prompt — Gmail Manager (jm5155/gmail-manager)

Repo structure for reference:
```
backend/  main.py, auth.py, gmail.py, ai_router.py, security.py, database.py
frontend/src/  App.jsx, index.css, pages/{Login,Inbox,ScamAlerts,Quarantine,Rewriter,Settings}.jsx
              components/{Sidebar,EmailCard,ScamBadge,ProgressBar,ToastNotification,ConfirmModal}.jsx
```
Current design tokens (frontend/src/index.css):
Primary `#2563EB` · Background `#0F172A` · Surface `#1E293B` · Border `#334155` ·
Text Primary `#F1F5F9` · Text Secondary `#94A3B8` · Success `#22C55E` · Warning `#F59E0B` · Danger `#EF4444`

Apply the five fixes below. Work file by file, and after each fix state which file(s) you changed and why.

---

## 1. Fix contrast on "NG" (failing) colors

**What to check:** run every text/background pairing in `index.css` and any inline styles in `ScamBadge.jsx`, `ToastNotification.jsx`, and status pills in `Settings.jsx` / `Inbox.jsx` against WCAG AA (4.5:1 for body text, 3:1 for large text/icons).

**Likely offenders given the current palette:**
- `Text Secondary #94A3B8` on `Surface #1E293B` — check ratio; on `Background #0F172A` it's borderline. This token is probably used for timestamps, secondary labels, empty states — audit every place it's used.
- `Warning #F59E0B` (amber) with white/light text on top, or amber text on `Surface` — amber-on-dark and white-on-amber are both common failure points.
- `Success #22C55E` and `Danger #EF4444` used as badge backgrounds — check whatever text color sits on top of them (often white or black text hardcoded rather than tokenized).
- Any placeholder text in inputs, and disabled-button states, which are frequently overlooked in dark themes.

**How to fix:**
1. Extract every `color` + `background-color` combination currently in use (grep `index.css` and all `.jsx` files for `style={{` and Tailwind/CSS-var color classes).
2. Run each pair through a contrast checker (WCAG AA). List every failing pair with its current ratio.
3. For failing pairs, lighten/darken the *foreground* text color first (don't change background brand colors casually) — e.g., bump `Text Secondary` from `#94A3B8` to something closer to `#A8B7C7`+ only if it still fails, and prefer defining explicit `--text-on-warning`, `--text-on-success`, `--text-on-danger` tokens rather than reusing `Text Primary`/`Text Secondary` on colored backgrounds.
4. Add the corrected values as new CSS variables in `index.css` (don't hardcode hex in components) and update all `.jsx` files that reference the old raw hex values.
5. **Watch for:** icons/SVGs that use `fill="currentColor"` vs a hardcoded fill — hardcoded fills won't inherit your contrast fix.

**Deliverable:** an updated `index.css` token block + a short before/after contrast table in your PR description or in `DESIGN_SYSTEM_AUDIT.md` (which already exists in the repo — update it, don't create a duplicate).

---

## 2. Hide the open-source GitHub link

**What to find:** the repo's README lists a live deployment at `gmail-manager-gamma.vercel.app`. Search the frontend for any link to `github.com/jm5155/gmail-manager` — check:
- `Sidebar.jsx` (footer/about links are commonly placed here)
- `Settings.jsx` (About/version section)
- `App.jsx` (global footer)
- `index.html` (meta tags / social preview links, if any)

**How to fix:**
1. `grep -ri "github.com/jm5155" frontend/src` and `grep -ri "github" frontend/src` to find every reference (including icon-only links, e.g., a GitHub logo `<a>` with no visible text).
2. Remove the `<a>`/button entirely rather than just hiding it with CSS (`display: none` still ships the URL in the bundle and is trivially discoverable in dev tools — if the goal is to not advertise the repo, delete the element and its import, e.g. `<Github />` icon import from `lucide-react` if unused elsewhere).
3. Check `README.md`'s "About" line (`gmail-manager-gamma.vercel.app`) isn't itself pulling repo info into any in-app "About" screen via a fetched README or package.json `repository` field rendered in the UI.
4. **Watch for:** `package.json` may have a `"repository"` or `"homepage"` field that some auto-generated "About" component reads at runtime — check `Settings.jsx` doesn't import `package.json` to display version/repo info.

**Deliverable:** no visible or DOM-present link to the GitHub repo anywhere in the running app.

---

## 3. Replace "Batch Analysis" with a custom email-count input

**Current behavior:** `POST /emails/analyze-bulk` (SSE) in `backend/main.py`, implemented against `backend/gmail.py`'s bulk analysis pipeline. The frontend trigger is almost certainly in `Inbox.jsx`, likely with a fixed batch size (check for a hardcoded constant like `BATCH_SIZE = 20` or similar, or a fixed dropdown of preset sizes).

**How to fix:**

Backend (`backend/main.py`, `backend/gmail.py`):
1. Find the `/emails/analyze-bulk` route handler. Add a required (or defaulted) request parameter, e.g. `count: int`, read from the POST body/query string.
2. In `gmail.py`'s bulk pipeline function, replace the hardcoded batch size with this `count` parameter. Trace it through to wherever it calls `users().messages().list()` — Gmail API's `maxResults` param should be driven by `count` too (capped, e.g. `min(count, 500)` per Gmail API limits, and paginate with `pageToken` if `count` exceeds one page of ~500).
3. Add input validation: reject/clamp `count <= 0` and unreasonably large values (define a sane server-side ceiling, e.g. 500 or 1000, and return a 400 with a clear message if exceeded — don't silently clamp without telling the frontend).
4. Confirm the SSE progress events (`ProgressBar.jsx` consumes these) report progress as `processed / count` rather than against the old fixed batch size — check the SSE payload shape in `main.py` includes total count so the frontend progress bar stays accurate.

Frontend (`Inbox.jsx`, `ProgressBar.jsx`):
1. Remove the existing "Batch Analysis" button/preset UI.
2. Add a numeric input (or stepper) labeled something like "Number of emails to analyze," with:
   - min value 1, sensible max matching the backend ceiling
   - a default (e.g., 20) pre-filled so users aren't forced to type every time
   - client-side validation matching the backend's rules, with an inline error state rather than a silent failure
3. Wire the input's value into the existing SSE call to `/emails/analyze-bulk` as `count`.
4. **Watch for:** if the current bulk pipeline fetches all matching emails first and *then* slices to a batch size in-memory, that's wasteful and won't scale — the fix should push `count` down to the Gmail API call itself (`maxResults`), not just slice the analysis loop.

**Deliverable:** user can type/select an arbitrary number of emails to analyze; that number is respected end-to-end (Gmail fetch → AI cascade → SSE progress → DB writes).

---

## 4. Fix email rewriter truncation at ~5000 words

**Where the bug lives:** `POST /ai/rewrite` in `main.py`, dispatched through `ai_router.py`'s cascade (NVIDIA → Gemini → Cohere). This is very likely a `max_tokens` (or equivalent) output cap set too low for the *output* generation call, not an input-side truncation — 5000 words ≈ 6500–7000 tokens, which exceeds many default/example `max_tokens` values (e.g., 1024, 2048, 4096) people copy from provider docs.

**How to fix:**
1. In `ai_router.py`, find each provider's call (NVIDIA `minimaxai/minimax-m2.7`, Gemini `gemini-2.0-flash`, Cohere `command-r`) used specifically for the `/ai/rewrite` path (it may share a function with the classification calls, which need much smaller outputs — don't just globally raise `max_tokens` for classification calls too, that wastes quota/cost).
2. For each provider, raise the output token/length parameter for the rewrite call specifically to comfortably exceed your target ceiling (leave headroom — e.g., support up to ~8000 words of output, not exactly 5000, since token-to-word ratio varies by content).
3. Check whether the *input* email body itself is being truncated before it reaches the model (some pipelines truncate the prompt for length/cost control) — if the source email is long, the truncation might be happening upstream, not on the output. Check `gmail.py`/wherever the email body is fetched and passed into `ai_router.py`'s rewrite function for something like `body[:5000]`.
4. Check the cascade's failover logic: if the primary provider (NVIDIA) hits its own truncation/finish-reason (e.g., `finish_reason == "length"`), does `ai_router.py` currently treat that as a success and return the cut-off text, or does it correctly detect truncation and either retry with a continuation prompt or fail over to the next provider? Right now it's almost certainly treating truncated output as a completed response — add an explicit check on the provider's finish/stop reason and only accept the response if it finished naturally (not by hitting the length cap).
5. If a single call genuinely can't cover very long emails even after raising the cap, implement continuation: detect `finish_reason == length`, send a follow-up "continue exactly where you left off" call with the partial output as context, and concatenate — rather than silently returning a cut-off result.
6. **Watch for:** the frontend (`Rewriter.jsx`) may also be truncating the *display* of the rewritten text (e.g., a `substring()`/`slice()` on render, or a CSS `max-height` with `overflow: hidden` and no scroll) — verify the cutoff is actually happening in the AI response and not just visually clipped in the UI before you touch backend token limits.

**Deliverable:** rewriting a long (multi-thousand-word) email body returns the full rewritten text, with no silent truncation anywhere in the pipeline (input, provider output, or display).

---

## 5. Add a bounding box around the rewritten text (matching the original's box)

**Where:** `Rewriter.jsx`. The "Original" email body is presumably already rendered inside a styled container (a card/box using `Surface`/`Border` tokens from `index.css`). The "Rewritten" output currently renders as plain text without that same container.

**How to fix:**
1. In `Rewriter.jsx`, find the JSX block rendering the original email body and note its wrapper element's class(es)/inline styles (likely something using `.card`, `border: 1px solid var(--border)`, `background: var(--surface)`, `border-radius: 12px` per the existing "Card Radius: 12px" token).
2. Wrap the rewritten output in an element using the **same class/token set** (don't hand-roll new styles that visually drift from the original box — reuse the existing card component/class for consistency, e.g. if there's already an `EmailCard.jsx` or a shared `.card` class, use that rather than duplicating CSS).
3. Keep both boxes visually aligned (same width, padding, and radius) so original vs. rewritten reads as a clear side-by-side or stacked comparison.
4. **Watch for:** if the rewritten text can now be very long (after fix #4), make sure the box has proper text wrapping and scroll behavior (`overflow-y: auto` with a `max-height`, or let it grow naturally) rather than overflowing the layout — test this specifically with a long rewritten email once #4 is fixed, since the two bugs interact.

**Deliverable:** the rewritten email is visually boxed identically to the original, with correct overflow handling for long text.

---

## General instructions for the agent

- Don't fix things in isolation — fixes #4 and #5 touch the same component/flow (`Rewriter.jsx` + `ai_router.py`), test them together with a genuinely long email.
- After each fix, run/describe a manual test case that would have caught the original bug (e.g., for #3: analyze a custom count of 7 and confirm exactly 7 are processed; for #4: rewrite a >5000-word email and confirm the full output is returned).
- Don't introduce new hardcoded hex colors or magic numbers — use the existing CSS variable tokens and named constants.
- Update `DESIGN_SYSTEM_AUDIT.md` and `QA_FIXES_SUMMARY.md` (both already exist in the repo) with what changed, since that's the project's existing convention for tracking this kind of work.
