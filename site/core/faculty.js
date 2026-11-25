// Optional current faculty context. This data is independent of ranking filters.
const escapeHtml = (value) => String(value).replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const METRICS = {
  'us-ece-current-v3': 'ece_regular_faculty',
  'us-ece-affiliated-v4': 'ece_affiliated_faculty',
  'us-ece-affiliated-v5': 'ece_affiliated_faculty',
};

function facultyIndex(payload, fieldId) {
  const records = new Map();
  if (payload?.schema_version !== 1 || payload.field !== fieldId ||
      !METRICS[payload.policy_id] || !Array.isArray(payload.schools)) return records;
  const metric = payload.metric_id ?? (payload.policy_id === 'us-ece-current-v3' ? 'ece_regular_faculty' : null);
  if (metric !== METRICS[payload.policy_id]) return records;
  for (const school of payload.schools) {
    if (!school || typeof school !== 'object') continue;
    if (!/^https:\/\/openalex\.org\/I\d+$/.test(school.institution_id || '') ||
        !Number.isSafeInteger(school.headcount) || school.headcount < 0 ||
        !/^\d{4}-\d{2}-\d{2}$/.test(school.observed_on || '') ||
        school.policy_id !== payload.policy_id) continue;
    const incoming = school.incoming_headcount ?? 0;
    const current = school.current_headcount ?? school.headcount - incoming;
    if (!Number.isSafeInteger(incoming) || incoming < 0 ||
        !Number.isSafeInteger(current) || current < 0 || current + incoming !== school.headcount) continue;
    const date = new Date(`${school.observed_on}T00:00:00Z`);
    if (Number.isNaN(date.valueOf()) || date.toISOString().slice(0, 10) !== school.observed_on) continue;
    try {
      const url = new URL(school.roster_url);
      if (url.protocol !== 'https:' || url.username || url.password) continue;
    } catch { continue; }
    // Duplicate records are ambiguous; omit the institution rather than choose one.
    if (records.has(school.institution_id)) records.set(school.institution_id, null);
    else records.set(school.institution_id, { ...school, metric_id: metric });
  }
  return records;
}

function renderFacultyContext(school) {
  if (!school || !Object.values(METRICS).includes(school.metric_id)) return '';
  const affiliated = school.metric_id === 'ece_affiliated_faculty';
  const date = new Date(`${school.observed_on}T00:00:00Z`).toLocaleDateString('en-US',
    { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  return `<aside class="faculty-context" aria-label="Current faculty">` +
    `<p><strong>${school.headcount}</strong> ${affiliated ? 'ECE-affiliated faculty' : 'EE/ECE faculty'}${school.incoming_headcount ? ` (${school.incoming_headcount} incoming)` : ''}</p>` +
    `<p class="faculty-source">${affiliated ? 'Includes affiliated, joint and courtesy professors' : 'Regular and in-residence appointments; courtesy excluded'} · Observed ${escapeHtml(date)} · ` +
    `<a href="${escapeHtml(school.roster_url)}" target="_blank" rel="noopener noreferrer">University roster</a></p></aside>`;
}

export { facultyIndex, renderFacultyContext };
