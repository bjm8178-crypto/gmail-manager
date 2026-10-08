import React from 'react';
import { securitySummary, parseIndicators } from '../utils/security';
export default function ScamBadge({ email = {}, score, reason = '', indicators = [], expanded = false, onToggle = () => {} }) {
  const risk = securitySummary({...email, scam_score: score ?? email.scam_score});
  const color = {high:'var(--color-danger)',medium:'var(--color-warning)',low:'var(--color-success)',unknown:'var(--color-text-secondary)'}[risk.level];
  const statuses = {completed:'Completed',partial:'Partial',failed:'Failed',unavailable:'Unavailable',not_applicable:'No applicable URLs',threat_detected:'Threat detected'};
  return <div className="rounded-lg text-xs" style={{border:'1px solid var(--color-border)',color:'var(--color-text-secondary)'}}>
    <button type="button" onClick={onToggle} aria-expanded={expanded} className="w-full px-3 py-2 text-left flex items-center justify-between gap-2" style={{minHeight:44}}>
      <span style={{color}}>
        {risk.label}{risk.score !== null ? ` · ${risk.score}/100` : ''}
        <span 
          title="AI-generated score. Always verify suspicious emails independently." 
          style={{
            marginLeft: '4px',
            display: 'inline-block',
            width: '14px',
            height: '14px',
            lineHeight: '14px',
            textAlign: 'center',
            border: '1px solid currentColor',
            borderRadius: '50%',
            fontSize: '10px',
            opacity: 0.7,
            cursor: 'help'
          }}
        >?</span>
      </span>
      <span aria-hidden="true">{expanded ? '▴' : '▾'}</span>
    </button>
    {email.user_decision === 'safe' && <p className="px-3 pb-2">Marked safe by you — original risk retained.</p>}
    {expanded && <div className="px-3 pb-3 space-y-2">
      <p>Automated estimate, not a guarantee of safety. Sender identity is not verified by this score.</p>
      <dl className="space-y-1">
        <div>Analysis: {statuses[email.analysis_status] || (risk.complete ? 'Completed (legacy)' : 'Not fully assessed')}</div>
        <div>Category: {statuses[email.category_status] || 'Not reported'}</div>
        <div>URL evidence: {statuses[email.url_scan_status] || 'Not reported'}{Number.isInteger(email.urls_checked) && Number.isInteger(email.urls_total) ? ` · ${email.urls_checked}/${email.urls_total} checked` : ''}</div>
        <div>Gmail sync: {email.sync_status || (email.synced_to_gmail ? 'applied' : 'Not reported')}</div>
      </dl>
      {(email.reasoning || reason) && <p>{email.reasoning || reason}</p>}
      {email.error_reason && <p>Analysis issue: {email.error_reason}</p>}
      <ul className="list-disc pl-4">{parseIndicators(indicators).map((item,index) => <li key={index}>{item}</li>)}</ul>
    </div>}
  </div>;
}
