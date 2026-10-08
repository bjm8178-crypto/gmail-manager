// Unknown evidence is never a safety verdict. Legacy records need explicit completion.
export function securitySummary(email = {}) {
  const status = email.analysis_status || email.status || 'unknown';
  const complete = ['completed', 'analyzed'].includes(status);
  const score = typeof email.scam_score === 'number' && Number.isFinite(email.scam_score) && email.scam_score >= 0 && email.scam_score <= 100 ? email.scam_score : null;
  const level = score >= 70 ? 'high' : score >= 40 ? 'medium' : complete && score !== null ? 'low' : 'unknown';
  const label = {high:'High estimated risk',medium:'Suspicious',low:'Low estimated risk',unknown:status === 'failed' ? 'Analysis failed' : 'Not fully assessed'}[level];
  return {level, score, complete, status, label};
}
export function reviewStatus(email) {
  if (email.user_decision === 'safe') return 'user_safe';
  if (email.sync_status === 'failed') return 'sync_failed';
  if (email.sync_status === 'applied' || (!email.sync_status && [true,1].includes(email.synced_to_gmail))) return 'applied';
  if (!securitySummary(email).complete) return 'incomplete';
  return 'pending';
}
export function parseIndicators(value) {
  try { const parsed = typeof value === 'string' ? JSON.parse(value) : value; return Array.isArray(parsed) ? parsed.filter(x => typeof x === 'string') : []; }
  catch { return []; }
}
