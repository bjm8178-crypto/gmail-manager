# Gmail Manager — Compliance, Legal, and Accessibility Fix Prompt

Use this as a direct implementation brief (for yourself, a dev, or a coding agent like Claude Code). Every item states **WHERE** (exact file/line), **WHAT** is wrong, and **HOW** to fix it. Ordered by priority.

---

## 🔴 P0 — Fix before any public launch

### 1. False "emails never leave your machine" claim (highest risk — active deception)
**Where:** `frontend/src/pages/LandingPage.jsx` line 438 (Trust Row) and line 1044 (Footer bottom bar).
**What's wrong:** Copy states "Emails never leave your machine." But the actual architecture (confirmed in `backend/database.py`, `vercel.json`, `README.md`) is:
- Frontend hosted on Vercel, backend hosted on Railway with a **Postgres database** storing user data.
- Email content is sent server-side to **three external AI providers** (Groq, Gemini, Cohere) for classification, and to **Google Safe Browsing API** for URL scanning.
- This is a live hosted demo (`gmail-manager-gamma.vercel.app`), not a fully local/offline app.
This is a false statement about data handling — a live regulatory and consumer-protection risk (FTC deceptive-advertising, GDPR/CCPA transparency obligations), not just a UX nitpick.
**How to fix:**
- Replace with accurate copy, e.g.: `"Self-hosted option available — or use our hosted cloud version"` or, if truly self-hosted deployment is possible with local Ollama/no external AI calls, clearly separate the two modes: "Self-hosted: fully local. Hosted demo: emails are processed by our servers and AI providers to deliver analysis — see Privacy Policy."
- Do this for **both** occurrences (line 438 and line 1044).
- Add a corresponding accurate data-flow section to the Privacy Policy (see item 6).

### 2. "Never Goes Down" — unsupported uptime guarantee
**Where:** `frontend/src/pages/LandingPage.jsx` line 403 (hero subhead) and line 633 (section header "Never Goes Down — AI Cascade").
**What's wrong:** No service can guarantee 100% uptime; this is an actionable false claim (especially paired with any future paid tier — deceptive advertising exposure).
**How to fix:**
- Line 403: change `"...that never goes down."` → `"...built for high availability."` or `"...with automatic failover between providers."`
- Line 633: change heading `"Never Goes Down — AI Cascade"` → `"Built for High Availability — AI Cascade"` or `"Automatic Failover — AI Cascade"`.
- If you want to keep a strong claim, add a footnote/disclaimer instead of removing entirely: `"Subject to upstream provider availability. No uptime is guaranteed."`

### 3. Missing legal documents (Privacy Policy, Terms, Cookie Policy, Refund Policy)
**Where:** New files needed under `frontend/src/pages/legal/`:
- `PrivacyPolicy.jsx`
- `TermsOfService.jsx`
- `CookiePolicy.jsx`
- `RefundPolicy.jsx`

**What to include in each (content guidance, not full legal text — have a lawyer review before launch):**

- **PrivacyPolicy.jsx** must accurately reflect the real architecture found in the codebase:
  - Data collected: Gmail OAuth token (via Google OAuth 2.0, see `backend/auth.py`), email metadata/content processed for classification, custom labels, API keys (encrypted at rest via Fernet/AES — see `backend/encryption.py`).
  - Data storage: Postgres database hosted on Railway (`backend/database.py`); confirm data retention period and add one.
  - Third parties data is shared with: **Groq, Google Gemini, Cohere** (email content for AI classification — `backend/ai_router.py`), **Google Safe Browsing API** (URLs from emails — `backend/security.py`), **Google Fonts** (visitor IP address, via `frontend/index.html` line 15).
  - Legal basis for processing (consent / legitimate interest), user rights (access, deletion, portability — GDPR Art. 15-20; CCPA "Do Not Sell/Share").
  - Data controller identity — **currently missing, must add real business/individual name + contact email + address** (see item 5).
  - International transfers disclosure if AI providers/Google process data outside the user's country.
- **TermsOfService.jsx**: acceptable use, no-warranty disclaimer for AI accuracy ("Scam Shield risk scores are automated estimates, not guarantees — see item 4"), limitation of liability, governing law/jurisdiction (needs item 8 decision), account termination, MIT license note (this only covers code, not the hosted service — clarify the two are different).
- **CookiePolicy.jsx**: Since the codebase has **no cookies and no analytics/tracking** (confirmed via full grep — none found), state this plainly: *"We do not use tracking or advertising cookies. We use `localStorage` to store your session token and `sessionStorage` for OAuth flow state, both strictly necessary for you to stay logged in."* This also means **no cookie-consent banner is legally required** right now — but flag this file as "must be updated if analytics/ads are ever added."
- **RefundPolicy.jsx**: Only needed if there's a paid tier. If it's currently free/open-source, either omit this page or state clearly "Gmail Manager is currently free to use; no payments are processed" so the placeholder link isn't misleading. Confirm with the business owner before writing refund terms.

**Routing (WHERE):** `frontend/src/App.jsx`
- Add imports near line 16 (after `Settings`): 
  ```js
  import PrivacyPolicy from './pages/legal/PrivacyPolicy';
  import TermsOfService from './pages/legal/TermsOfService';
  import CookiePolicy from './pages/legal/CookiePolicy';
  import RefundPolicy from './pages/legal/RefundPolicy';
  ```
- Add routes inside `<Routes>` near line 137 (next to `/login`):
  ```jsx
  <Route path="/privacy-policy" element={<PrivacyPolicy />} />
  <Route path="/terms" element={<TermsOfService />} />
  <Route path="/cookie-policy" element={<CookiePolicy />} />
  <Route path="/refund-policy" element={<RefundPolicy />} />
  ```

### 4. Add AI-accuracy / no-guarantee disclaimer near scam detection UI
**Where:** `frontend/src/components/ScamBadge.jsx` and wherever risk scores are displayed (`Inbox.jsx`, `ScamAlerts.jsx`).
**What's wrong:** A 0–100 "scam risk score" presented without qualification implies certainty the AI cannot back up (false positives/negatives are possible with any AI classifier).
**How to fix:** Add a small info tooltip (the codebase already has `InfoTooltip.jsx` — reuse it) next to risk badges: *"AI-generated estimate. Always verify suspicious emails yourself before acting."* Add the same line to Terms of Service under a "No Warranty" clause.

---

## 🟠 P1 — Consent & business identity

### 5. Add business/company details
**Where:** `frontend/src/pages/LandingPage.jsx`, footer "Connect" column (currently empty — lines 1007–1025, note the dangling empty `<li></li>` at line 1022-1023 which is dead markup).
**How to fix:** Replace the empty Connect column with real footer content:
```jsx
<div className="min-w-0" style={{ width: '100%' }}>
  <h4 style={{ ... }}>Legal</h4>
  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
    <li style={{ marginBottom: '0.5rem' }}><Link to="/privacy-policy">Privacy Policy</Link></li>
    <li style={{ marginBottom: '0.5rem' }}><Link to="/terms">Terms of Service</Link></li>
    <li style={{ marginBottom: '0.5rem' }}><Link to="/cookie-policy">Cookie Policy</Link></li>
    <li style={{ marginBottom: '0.5rem' }}><Link to="/refund-policy">Refund Policy</Link></li>
  </ul>
</div>
```
And add a business-identity line in the bottom bar near line 1041 (currently just `© 2026 Gmail Manager. All rights reserved.`):
```
[Your Legal Business Name] · [Registered Address] · [Contact Email] · [Company Registration No., if applicable]
```
**You must supply these values yourself** — I used placeholders since none were given. Do not launch with placeholder text still in the live footer.

### 6. Add consent checkbox before OAuth login
**Where:** `frontend/src/pages/Login.jsx`, in the render block before the "Sign in with Google" button (around line 90+, wherever the login button JSX lives).
**How to fix:** Add a required checkbox:
```jsx
const [agreed, setAgreed] = useState(false);
// ...
<label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.8125rem' }}>
  <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
  <span>I agree to the <Link to="/terms">Terms of Service</Link> and <Link to="/privacy-policy">Privacy Policy</Link>.</span>
</label>
<button onClick={handleLogin} disabled={!agreed || isLoading}>Sign in with Google</button>
```
This is your actual GDPR/consent checkpoint since this app requests broad Gmail OAuth scopes (read/modify/delete access) — consent must be informed and explicit before that grant happens.

### 7. Google Fonts third-party embed disclosure
**Where:** `frontend/index.html` lines 13–15.
**What's wrong:** `fonts.googleapis.com` sends visitor IP addresses to Google before consent — a minor but real GDPR data-transfer point.
**How to fix (pick one):**
- **Simplest/safest:** self-host the Inter font (download `.woff2` files, add via `@font-face` in `index.css`), removing the external request entirely. Safe by default, no disclosure needed.
- **Or:** keep it but disclose it explicitly in the Privacy Policy's third-party section (see item 3).

### 8. Determine applicable local law / jurisdiction
**Where:** Affects Terms of Service governing-law clause and Privacy Policy compliance-framework section.
**What to do:** This depends on facts I don't have — you (the business owner) need to confirm:
- Where the legal entity/individual operating this service is based (this sets the default governing law).
- Where your users are (if you have or expect EU/UK users → GDPR + UK GDPR applies regardless of where you're based; California users → CCPA/CPRA; if none disclosed, default to a general/neutral consumer-protection framing).
- Since Railway/Vercel infrastructure regions aren't fixed to one country, add a data-hosting-location statement to the Privacy Policy once you confirm your Railway project's region.
**Flag:** Do not silently assume US law — Gmail data + AI processing + no current jurisdiction statement is a real gap; get this confirmed before finalizing the Terms of Service governing-law clause.

---

## 🟡 P2 — Accessibility fixes

### 9. Settings.jsx — unlabeled input field
**Where:** `frontend/src/pages/Settings.jsx` lines 350–358 (the "Custom Labels" text input).
**What's wrong:** Input has only a `placeholder`, no `<label>`. Placeholder text disappears on focus/input and isn't a reliable accessible name for screen readers.
**How to fix:**
```jsx
<label htmlFor="new-label-input" className="sr-only">New label name</label>
<input
  id="new-label-input"
  type="text"
  aria-label="New label name"
  value={newLabelName}
  ...
/>
```
(Add an `.sr-only` utility class to `index.css` if not already present — visually hidden but screen-reader accessible.)

### 10. Settings.jsx — delete label button
**Where:** `frontend/src/pages/Settings.jsx` lines 378–384 (the "×" delete button per label).
**What's wrong:** Only has a `title` attribute, which is inconsistently announced by screen readers and not keyboard-focus-visible in all browsers.
**How to fix:**
```jsx
<button
  onClick={() => handleDeleteLabel(label)}
  aria-label={`Delete label ${label.label_name}`}
  className="ml-1 text-danger opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100"
  ...
>
  ×
</button>
```
(Added `focus:opacity-100` too — currently the button is invisible until hover, which makes it undiscoverable via keyboard-only navigation; must also show on keyboard focus.)

### 11. Decorative emoji icons need `aria-hidden`
**Where:**
- `frontend/src/pages/Settings.jsx` line 304 (`<span className="text-lg flex-shrink-0">{field.icon}</span>` — renders 🟢🔵🟡⚪🛡️)
- `frontend/src/pages/LandingPage.jsx` lines 458–460 (📥 ⚠️ 🔒 in the fake dashboard mockup)
**What's wrong:** Emojis are read aloud by screen readers (e.g., "green circle", "shield") which is noisy/confusing since they're purely decorative next to text labels that already convey the meaning.
**How to fix:** Add `aria-hidden="true"` to each emoji-containing span:
```jsx
<span className="text-lg flex-shrink-0" aria-hidden="true">{field.icon}</span>
```
Do this for all emoji icon spans in both files.

### 12. Entire hero "dashboard mockup" should be hidden from assistive tech
**Where:** `frontend/src/pages/LandingPage.jsx` lines 442–509 (the fake screenshot/dashboard mockup block).
**What's wrong:** It's a purely decorative visual (fabricated email rows, fake risk scores) with no `alt` text or `aria-hidden`, so screen readers will read through "Account Services... High Risk 85%... Suspicious Login Attempt..." as if it were real content/data — confusing and pointless for non-visual users.
**How to fix:** Wrap the whole container with `aria-hidden="true"` and `role="presentation"`:
```jsx
<div className="relative w-full max-w-4xl ..." aria-hidden="true" role="presentation" style={{ ... }}>
```

### 13. Mobile menu button and other icon-only buttons — verify all have `aria-label`
**Where:** `frontend/src/App.jsx` line 88–102 already has `aria-label="Open menu"` ✅ (good, no fix needed). Audit `Sidebar.jsx` for any icon-only buttons/links that may be missing `aria-label` — check nav icons there.
**How to fix:** For any icon-only interactive element found without a text label, add `aria-label="<description>"`.

### 14. Keyboard-friendly forms — Enter key handling
**Where:** `frontend/src/pages/Settings.jsx` line 354 already handles `Enter` via `onKeyPress` ✅. Note: `onKeyPress` is deprecated in React/DOM spec — recommend migrating to `onKeyDown` with `e.key === 'Enter'` check for future-proofing, but not an urgent accessibility bug today.

### 15. Color contrast — already largely compliant, spot-check one area
**Where:** `frontend/src/index.css` — the design system already documents WCAG ratios in comments (e.g. `--color-text-secondary: #334155; /* AAA 9.9:1 */`), and both light/dark themes look properly built. **No broad contrast fixes needed.**
**One thing to check manually:** `frontend/src/pages/LandingPage.jsx` lines 470–504 — the fake dashboard mockup uses raw Tailwind slate colors (`text-slate-400`, `text-slate-500`) on a custom dark background (`#0F1729`/`#131926`) that bypass the theme's audited CSS variables. Since item 12 makes this block `aria-hidden` (decorative-only), contrast here matters visually but not for a11y compliance — verify visually it's still legible for sighted users, but no urgent fix required.

### 16. Clear button labels — spot check
**Where:** `frontend/src/pages/LandingPage.jsx` line 432 `"Launch Live App →"` and line 344 `"Try Live Demo →"`.
**Note:** These are already clear and descriptive. ✅ No fix needed. The only unclear/non-functional buttons found are footer links using `href="#"` (lines 990, 995, 1000 — "Documentation", "API Reference") which go nowhere. Either link them to real destinations (e.g., the GitHub README) or remove them until real pages exist — dead links are a minor UX/trust issue, not a legal one.

---

## ✅ Already compliant — no action needed
- **No fake reviews/testimonials** anywhere in the codebase (confirmed via full-text search).
- **No analytics or tracking scripts** (no Google Analytics, Meta Pixel, Mixpanel, etc.) — confirmed via grep across `frontend/src` and `index.html`.
- **No tracking cookies** — auth uses `localStorage`/`sessionStorage` only, both strictly necessary (no cookie-consent banner legally required today).
- **No local copyrighted image assets** — icons come from an icon library, no photo/image copyright exposure found.
- **API keys encrypted at rest** (`backend/encryption.py`, Fernet/AES) — good security practice, mention this positively in the Privacy Policy's security section.

---

## Before you ship
1. Fill in real business name, address, and contact email everywhere placeholders are marked above.
2. Have a lawyer (or at minimum a legal-doc generator service reviewed by one) sign off on the final Privacy Policy / Terms, especially the GDPR/CCPA sections and the jurisdiction clause (item 8).
3. Re-run a manual screen-reader pass (VoiceOver/NVDA) over Login, Settings, and the landing page after applying items 9–13.
4. Re-check the "emails never leave your machine" and "never goes down" copy sitewide (search the whole repo, not just the two files listed, in case it's repeated elsewhere e.g. README or meta tags) before removing this warning from your checklist.
