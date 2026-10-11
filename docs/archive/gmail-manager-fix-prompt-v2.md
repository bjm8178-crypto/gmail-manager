# Gmail Manager — Full Fix Prompt (v2)

Confirmed against the live repo (`jm5155/gmail-manager`, cloned and grepped directly — not guessed). Fix in this order: #1 first, since it's silently breaking styling across nearly every component and will make the light-mode contrast work in #2 harder to verify if left broken.

---

## 1. FIX BROKEN CSS VARIABLE WIRING (do this first — highest impact, currently live)

**WHERE:** `frontend/tailwind.config.js` vs `frontend/src/index.css`

**WHAT'S WRONG:** `tailwind.config.js` maps Tailwind utility classes to CSS variable names that `index.css` never defines. Confirmed missing (checked both `:root` and `[data-theme="dark"]` blocks):

```
--surface          --surface-light
--border-default   --border-subtle
--radius-pill
--space-xs  --space-sm  --space-md  --space-lg  --space-xl
```

`index.css` instead defines a *different* naming scheme: `--color-surface`, `--color-border`, `--spacing-md`, etc. (with a partial "LEGACY ALIASES" block that only covers some of them — `--surface`/`--surface-light`/`--border-default`/`--border-subtle`/`--radius-pill`/`--space-*` are aliased nowhere).

**WHY IT MATTERS:** any element styled with Tailwind's `bg-surface`, bare `border`, `rounded-pill`, or spacing utilities like `p-md`/`gap-lg` resolves to `var(--undefined-variable)` with no fallback. Per CSS spec, an invalid custom property reference makes the whole declaration invalid — the browser drops it silently (no console error). Result: **no background, no border, no border-radius, no padding** on that element, even though the JSX "looks correct." This is confirmed in use across nearly every file: `App.jsx`, `Sidebar.jsx`, `EmailCard.jsx`, `EmailDetailPanel.jsx`, `ConfirmModal.jsx`, `ProgressBar.jsx`, `ScamBadge.jsx`, `ToastNotification.jsx`, `AnimatedBackground.jsx`, `Inbox.jsx`, `Quarantine.jsx`, `Rewriter.jsx`, `ScamAlerts.jsx`, `Settings.jsx`, `Login.jsx`, `LandingPage.jsx`.

The same bug also exists **inside `index.css` itself**, independent of Tailwind: the `@layer base` classes `.badge-neutral`, `.neu-popover` (the scam-analysis expansion panel), `.modal-content`, `.settings-grid`, `.divider`, and the scrollbar thumb all reference `var(--surface-light)`, `var(--border-default)`, `var(--space-md)`, `var(--radius-pill)` — same missing variables.

**HOW TO FIX:**
1. Pick ONE naming scheme as the source of truth. Recommend keeping `index.css`'s existing `--color-*` / `--spacing-*` scheme since it's the larger, already-complete set (has full light + dark definitions).
2. In `index.css`, extend the "LEGACY ALIASES" block (both `:root` and `[data-theme="dark"]`) to add the missing aliases:
   ```css
   --surface: var(--color-surface);
   --surface-light: var(--color-surface-hover);
   --border-default: var(--color-border);
   --border-subtle: var(--color-border-light);
   --radius-pill: 999px;
   --space-xs: var(--spacing-xs);
   --space-sm: var(--spacing-sm);
   --space-md: var(--spacing-md);
   --space-lg: var(--spacing-lg);
   --space-xl: var(--spacing-xl);
   ```
3. Re-check `tailwind.config.js`'s full `theme.extend` block against the now-complete variable list — confirm every `var(--x)` referenced there has a real definition in both `:root` and `[data-theme="dark"]`.
4. **Test method:** after the fix, inspect `.badge-neutral`, the scam-analysis popover, `.modal-content`, and any element using Tailwind's `bg-surface`/`rounded-pill`/`p-md` classes in the browser dev tools — confirm `background`, `border`, `border-radius`, and `padding` now show computed (non-empty) values, in both light and dark mode.
5. **Watch for:** don't just add fallback values inline (`var(--surface, #fff)`) as a quick patch — that masks the wiring bug instead of fixing it, and the next dev to add a new component will hit the same silent failure. Fix the variable definitions themselves.

---

## 2. LIGHT MODE PALETTE — CONTRAST FIX

**WHERE:** `frontend/src/index.css`, `:root` block (light mode tokens, lines ~24–59).

**WHAT'S WRONG:** current light-mode tokens:
```
--color-text-secondary: #687386;   (body text, descriptions, metadata)
--color-text-muted:     #9AA3B2;   (placeholders, tertiary info)
--color-background:     #F1F3F6;
--color-surface:        #F8F9FB;
```
`--color-text-secondary` and `--color-text-muted` are too light against white/near-white surfaces — this is what makes timestamps, preview snippets, and subtext read as barely visible in the screenshot. Also note: **dark mode already has explicit `--color-text-on-success` / `-on-warning` / `-on-danger` / `-on-info` tokens for badge text contrast — light mode has no equivalent**, so light-mode badges just use the raw semantic color as text color, which is a weaker contrast pairing than dark mode gets.

**HOW TO FIX:** replace/extend the light-mode token block with a graduated scale (dark-shade text tokens + light-tint surface tokens), each pre-checked against white:

```css
/* Text (dark-on-light), checked against white */
--color-text-primary:   #0F172A;  /* ~17.9:1 AAA — unchanged in spirit, slightly deepened */
--color-text-secondary: #334155;  /* ~9.9:1 AAA  — was #687386 (too light) */
--color-text-muted:     #64748B;  /* ~4.9:1 AA   — was #9AA3B2 (too light) */

/* Surfaces — add real separation between page bg and card bg */
--color-background:     #F8FAFC;
--color-surface:        #FFFFFF;
--color-surface-hover:  #F1F5F9;
--color-border:         #CBD5E1;  /* was #E1E5EB — too close to white to read as a line */

/* Primary blue scale (for CTAs, active nav, links) */
--color-primary:         #2563EB;  /* white text, AA 4.6:1 */
--color-primary-hover:   #2354C7;  /* white text, AA 5.9:1 */
--color-primary-active:  #1E3A8A;  /* white text, AAA 9.8:1 */
--color-primary-light:   #E0ECFF;  /* dark text on top, AAA 16:1 — for selected-row/tab backgrounds */

/* Add missing text-on-badge tokens (light mode currently has none) */
--color-text-on-success: #166534;  /* on --color-success-bg, AAA 7.6:1 */
--color-text-on-warning: #92400E;  /* on --color-warning-bg, AAA 7.2:1 */
--color-text-on-danger:  #991B1B;  /* on --color-danger-bg, AAA 7.9:1 */
--color-text-on-info:    #1E40AF;  /* on --color-info-bg, check ratio and adjust if under 4.5:1 */
```

**HOW TO APPLY:**
1. Update the `.badge-*` classes in `index.css` to use `color: var(--color-text-on-success)` etc. instead of `color: var(--success)` (the raw semantic color), matching how dark mode already does it — this closes the light/dark inconsistency in badge contrast.
2. Update `.nav-item.active` (currently `background: rgba(91, 92, 226, 0.08)`, a very faint tint) to use `background: var(--color-primary-light)` for a clearer active-state indicator in the sidebar.
3. **Watch for:** don't reuse `--color-text-secondary` as a background tint color anywhere — it's a text token. Keep the text-scale and surface-tint scale as separate variable sets so nobody accidentally puts a text-contrast color where a background-contrast color is needed (this is the same category of bug as item #1).

---

## 3. HIDE THE OPEN-SOURCE GITHUB LINK

**WHERE:** confirmed present in `frontend/src/pages/LandingPage.jsx` (grep the file for `github.com/jm5155` and any bare GitHub icon `<a>` tag — the earlier fetch of the repo's public README shows the project also has a live Vercel deployment at `gmail-manager-gamma.vercel.app`, so check `LandingPage.jsx`'s footer/nav for a link to the repo). Also check `Settings.jsx` for any "About" section.

**HOW TO FIX:**
1. `grep -rn "github.com/jm5155\|github.com" frontend/src` to find every reference, including icon-only links with no visible text (e.g., a `<Github />` icon from `lucide-react` wrapped in an `<a>`).
2. Delete the element and its import entirely — don't just `display: none` it, since the URL still ships in the built JS bundle and is visible via dev tools/view-source.
3. Confirm no component reads `package.json`'s `repository`/`homepage` field into an "About" screen.

**Deliverable:** no visible or DOM-present link to the GitHub repo anywhere in the running app.

---

## 4. REPLACE "BATCH ANALYSIS" WITH CUSTOM EMAIL-COUNT INPUT

Note: your screenshot already shows a numeric input (currently `50`) next to "Analyze Emails" in `Inbox.jsx` — confirm whether this already IS the custom-count field or still a preset. If it's already a free-text/number input wired to a fixed batch size under the hood, the fix is backend-side only.

**WHERE:** `frontend/src/pages/Inbox.jsx` (the count input + "Analyze Emails" button), `backend/main.py` (the `/emails/analyze-bulk` route), `backend/gmail.py` (the bulk pipeline function).

**HOW TO FIX:**
1. In `main.py`, confirm the `/emails/analyze-bulk` handler reads a `count` value from the request body/query and passes it through — don't let it fall back to a hardcoded constant if the field is empty or zero.
2. In `gmail.py`, trace `count` through to the Gmail API call's `maxResults` param (capped per Gmail API limits — batch/paginate with `pageToken` if `count` exceeds ~500 in one call).
3. Add server-side validation: reject `count <= 0`, clamp/reject unreasonably large values with a clear 400 response (don't silently clamp without telling the frontend).
4. In `Inbox.jsx`, add matching client-side validation (min 1, max matching backend ceiling) with an inline error state, and confirm the SSE progress payload reports `processed / count` accurately so `ProgressBar.jsx` doesn't show wrong percentages.
5. **Watch for:** if the pipeline currently fetches all matching emails first and slices to a count in-memory, push `count` down to the actual Gmail API fetch call instead — slicing after fetching doesn't save API quota or time.

**Deliverable:** typing an arbitrary number in the count field analyzes exactly that many emails, end-to-end.

---

## 5. FIX EMAIL REWRITER TRUNCATION AT ~5000 WORDS

**WHERE:** `backend/ai_router.py` (the cascade: NVIDIA `minimaxai/minimax-m2.7` → Gemini `gemini-2.0-flash` → Cohere `command-r`), dispatched from the `/ai/rewrite` route in `backend/main.py`. Also check `frontend/src/pages/Rewriter.jsx` for display-side truncation before touching the backend.

**HOW TO FIX:**
1. First rule out a frontend display bug: check `Rewriter.jsx` for a `substring()`/`slice()` on the rewritten text, or a CSS `max-height` + `overflow: hidden` with no scroll — confirm the cutoff is actually happening in the AI response, not just visually clipped.
2. In `ai_router.py`, find the output-length parameter (`max_tokens` or equivalent) used specifically for the rewrite call for each provider — 5000 words ≈ 6500–7000 tokens, which exceeds common default caps (1024/2048/4096) copied from provider quickstart docs. Raise it with headroom (target ~8000+ words of output) for the rewrite path specifically — don't raise it for the classification calls too, since those need small outputs and raising them wastes cost/quota.
3. Check whether the *input* email body is being truncated before reaching the model (e.g. something like `body[:5000]` in `gmail.py` or wherever the body is passed into `ai_router.py`) — the cutoff could be on the input side, not the output side.
4. Check the cascade's failover logic for `finish_reason`/`stop_reason` handling: if NVIDIA's response was cut off by hitting its own length cap, does `ai_router.py` currently treat that as a successful response and return the truncated text? Add an explicit check — only accept a response that finished naturally, and either retry with a "continue from where you left off" follow-up call or fail over to the next provider if truncated.
5. **Watch for:** fixes #5 and the box styling in #6 interact — test them together with one genuinely long (>5000-word) email once both are done.

**Deliverable:** rewriting a long email returns the complete rewritten text with no silent truncation anywhere in the pipeline.

---

## 6. ADD A BOUNDING BOX AROUND THE REWRITTEN TEXT

**WHERE:** `frontend/src/pages/Rewriter.jsx`.

**HOW TO FIX:**
1. Find the wrapper element around the "Original" email body — note its class(es) (likely a `.card`/`neu-*` class using the design tokens).
2. Wrap the rewritten output in the same class/component rather than hand-rolled styles, so it stays visually consistent if the design tokens change later.
3. Add `overflow-y: auto` with a sensible `max-height` (or let it grow naturally) so a long rewritten email (post fix #5) doesn't overflow the layout — test with a long email specifically.

**Deliverable:** the rewritten email is visually boxed identically to the original, with correct overflow handling for long text.

---

## Also flagged during the audit (address opportunistically, not blocking)

- `Quarantine.jsx` and `Inbox.jsx` use hardcoded raw `rgba()` reds/greens instead of the `--color-danger`/`--color-success` tokens — won't stay in sync if the palette changes later.
- Several components use default Tailwind palette classes (`bg-slate-800`, `border-slate-700`, `text-amber-400`, `bg-red-950`, `bg-green-950`) that bypass the custom theme system entirely and won't respond to light/dark switching.
- `LandingPage.jsx` has a one-off hardcoded `#131926` with no token backing it.

## General instructions for the agent

- Fix #1 before manually re-verifying #2 — some of what looks like a contrast problem may actually be the missing-variable bug making elements invisible rather than wrong-colored.
- After each fix, state which file(s) changed and give a manual test case that would have caught the original bug.
- Don't introduce new hardcoded hex values or magic numbers — extend the token system instead.
- Update `DESIGN_SYSTEM_AUDIT.md` and `QA_FIXES_SUMMARY.md` (both already exist in the repo) with what changed, per the project's existing convention.
