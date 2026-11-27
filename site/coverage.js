// Which years of each ECE venue are in the rankings. The summary is
// generated from the published data by pipeline/prerender_site.mjs.
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

export const shortName = (name) => /\(([^()]+)\)\s*$/.exec(name)?.[1] || name;

export function cellState(venue, year) {
  if (venue.years.includes(year)) return { cls: 'cov-ok', label: `${year}: in the rankings` };
  if (venue.none[year]) return { cls: 'cov-none', label: `${year}: ${venue.none[year]}` };
  return { cls: 'cov-absent', label: `${year}: not in the rankings` };
}

export function renderCoverage({ first, last, areas }) {
  const years = Array.from({ length: last - first + 1 }, (_, i) => first + i);
  const head = `<tr><td></td>${years.map((y) =>
    `<th class="cov-year" scope="col"><span class="${y % 5 === 0 ? '' : 'visually-hidden'}">${y}</span></th>`).join('')}</tr>`;
  const row = (venue) => {
    const label = venue.kind === 'conference' ? shortName(venue.name) : venue.name;
    const title = label === venue.name ? '' : ` title="${esc(venue.name)}"`;
    return `<tr><th scope="row"${title}>${esc(label)}</th>` + years.map((y) => {
      const state = cellState(venue, y);
      return `<td><i class="cov-key ${state.cls}" title="${esc(state.label)}"></i><span class="visually-hidden">${esc(state.label)}</span></td>`;
    }).join('') + '</tr>';
  };
  const journalHeading = `<tr class="cov-group"><th colspan="${years.length + 1}" scope="colgroup">Journals</th></tr>`;
  return areas.map((area) => {
    const conferences = area.venues.filter((v) => v.kind === 'conference');
    const journals = area.venues.filter((v) => v.kind !== 'conference');
    return `<section><h2>${esc(area.name)}${area.default_on ? '' : ' <span class="muted">off by default</span>'}</h2>` +
      `<table class="cov" style="--cov-years:${years.length}"><thead>${head}</thead>` +
      (conferences.length ? `<tbody>${conferences.map(row).join('')}</tbody>` : '') +
      (journals.length ? `<tbody>${journalHeading}${journals.map(row).join('')}</tbody>` : '') +
      '</table></section>';
  }).join('');
}

async function init() {
  const out = document.getElementById('venues');
  try {
    const res = await fetch('coverage-data.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    out.innerHTML = renderCoverage(data);
    document.getElementById('legend-absent').hidden = !out.querySelector('.cov-absent');
  } catch {
    out.innerHTML = '<p class="error">Could not load the venue list.</p>';
  }
}

if (typeof document !== 'undefined') void init();
