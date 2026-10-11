# Gmail Manager — Remaining Compliance & Accessibility Fixes (Part 2)

Verified against the current `main` branch (commit `913f0e0`). P0 items #1–#3 from the original prompt are done. Everything below is confirmed still missing. Same format: WHERE / WHAT / HOW.

---

## 🔴 P0-4 — AI accuracy disclaimer on risk scores

**Where:** `frontend/src/components/ScamBadge.jsx` (renders the risk score badge), plus wherever it's used in `frontend/src/pages/Inbox.jsx` and `frontend/src/pages/ScamAlerts.jsx`.
**What's wrong:** Confirmed no `InfoTooltip` or disclaimer currently exists on the risk score badge. A 0–100 score is shown with no qualification that it's AI-generated and can be wrong.
**How to fix:**
1. Open `ScamBadge.jsx`, import the existing tooltip component: `import InfoTooltip from './InfoTooltip';`
2. Next to the score badge markup, add:
   ```jsx
   <InfoTooltip text="AI-generated estimate. Always verify suspicious emails yourself before acting." />
   ```
3. Confirm `ScamBadge` is used consistently in `Inbox.jsx` and `ScamAlerts.jsx` so the tooltip appears everywhere a score is shown, not just one page.

---

## 🟠 P1-5 — Business details + legal links in footer

**Where:** `frontend/src/pages/LandingPage.jsx`, the "Connect" column (currently empty — an orphaned `<li></li>` with no content, around line 1020–1024), and the bottom bar (around line 1035–1041, currently reads "© 2026 Gmail Manager. All rights reserved." with no business identity).
**What's wrong:** The legal pages (Privacy/Terms/Cookie/Refund) exist as routes now but are **not linked from anywhere in the UI** — a user has no way to find them. Also still no registered business name/address/contact.
**How to fix:**
Replace the empty Connect column:
```jsx
{/* Legal */}
<div className="min-w-0" style={{ width: '100%' }}>
  <h4 style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
    Legal
  </h4>
  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
    <li style={{ marginBottom: '0.5rem' }}>
      <Link to="/privacy-policy" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>Privacy Policy</Link>
    </li>
    <li style={{ marginBottom: '0.5rem' }}>
      <Link to="/terms" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>Terms of Service</Link>
    </li>
    <li style={{ marginBottom: '0.5rem' }}>
      <Link to="/cookie-policy" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>Cookie Policy</Link>
    </li>
    <li style={{ marginBottom: '0.5rem' }}>
      <Link to="/refund-policy" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>Refund Policy</Link>
    </li>
  </ul>
</div>
```
And update the bottom bar to include a business-identity line under the copyright:
```jsx
<div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
  © 2026 Gmail Manager. All rights reserved.<br/>
  [Your Legal Business Name] · [Registered Address] · [Contact Email]
</div>
```
**You must supply the real name/address/email** — do not launch with the bracketed placeholders still showing.

---

## 🟠 P1-6 — Consent checkbox before Google OAuth login

**Where:** `frontend/src/pages/Login.jsx` — confirmed no checkbox, no reference to Terms/Privacy anywhere in the file currently.
**What's wrong:** This app requests broad Gmail OAuth scopes (read/modify/delete). Google Fonts is not the concern here — the concern is granting that scope without the user first seeing/agreeing to your Terms and Privacy Policy.
**How to fix:**
1. Add state near the other `useState` calls at the top of the component:
   ```jsx
   const [agreed, setAgreed] = useState(false);
   ```
2. Add the checkbox in the JSX just above the login button:
   ```jsx
   <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.8125rem', marginBottom: '1rem', textAlign: 'left' }}>
     <input
       type="checkbox"
       checked={agreed}
       onChange={(e) => setAgreed(e.target.checked)}
       style={{ marginTop: '0.2rem' }}
     />
     <span>
       I agree to the{' '}
       <Link to="/terms" style={{ color: 'var(--color-primary)' }}>Terms of Service</Link>{' '}
       and{' '}
       <Link to="/privacy-policy" style={{ color: 'var(--color-primary)' }}>Privacy Policy</Link>.
     </span>
   </label>
   ```
3. Import `Link` from `react-router-dom` at the top if not already imported.
4. Disable the existing login button until checked:
   ```jsx
   <button onClick={handleLogin} disabled={!agreed || isLoading} ...>
   ```

---

## 🟡 P2 — Accessibility fixes (confirmed: none applied yet)

### a) Settings.jsx — label input needs an accessible name
**Where:** `frontend/src/pages/Settings.jsx`, the "Custom Labels" text input (search for `placeholder="Enter label name..."`).
**How to fix:**
```jsx
<label htmlFor="new-label-input" className="sr-only">New label name</label>
<input
  id="new-label-input"
  type="text"
  aria-label="New label name"
  value={newLabelName}
  onChange={(e) => setNewLabelName(e.target.value)}
  onKeyDown={(e) => e.key === 'Enter' && handleAddLabel()}
  placeholder="Enter label name..."
  className="neu-input flex-1"
  disabled={labelLoading}
/>
```
(Switched `onKeyPress` → `onKeyDown` since `onKeyPress` is deprecated.)

### b) Settings.jsx — delete label button
**Where:** same file, the "×" button that calls `handleDeleteLabel`.
**How to fix:**
```jsx
<button
  onClick={() => handleDeleteLabel(label)}
  aria-label={`Delete label ${label.label_name}`}
  className="ml-1 text-danger opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
>
  ×
</button>
```
(Adding `focus:opacity-100` is required — right now the button is invisible until mouse hover, making it unusable via keyboard-only/Tab navigation.)

### c) Settings.jsx — decorative provider icons
**Where:** same file, `<span className="text-lg flex-shrink-0">{field.icon}</span>` (renders 🟢🔵🟡⚪🛡️).
**How to fix:** add `aria-hidden="true"` to that span, since the adjacent text label already conveys the meaning.

### d) LandingPage.jsx — decorative dashboard mockup
**Where:** the fake dashboard screenshot block in the hero section (contains fabricated rows like "Account Services... High Risk 85%").
**How to fix:** wrap the outer container of that mockup with `aria-hidden="true" role="presentation"` so screen readers don't read fabricated email content as if it were real.

### e) Add `.sr-only` utility class
**Where:** `frontend/src/index.css`.
**How to fix:** add if not already present:
```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

### f) Dead footer links
**Where:** `frontend/src/pages/LandingPage.jsx`, "Documentation" and "API Reference" links under the "Resources" column currently point to `href="#"`.
**How to fix:** either link to the real GitHub README (e.g. `https://github.com/jm5155/gmail-manager#readme`) or remove the links until real destinations exist. Not a legal issue, just a trust/UX one — lower priority than everything else here.

---

## After these are done
That closes out every item from the original audit. Recommended final checks:
1. Load `/privacy-policy`, `/terms`, `/cookie-policy`, `/refund-policy` in a browser and click through from the footer to confirm the links actually work (this is the first time they'll be reachable from the UI).
2. Tab through the Login page and Settings page keyboard-only to confirm the checkbox, the label input, and the delete button are all reachable and visibly focused.
3. Swap in your real business name/address/contact email everywhere a placeholder is still showing, in both the footer and the legal pages generated in Part 1.
4. Get a lawyer's eyes on the final Privacy Policy / Terms before public launch — this prompt gets you compliant-shaped, not legally signed off.
