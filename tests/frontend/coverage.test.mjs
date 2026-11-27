import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { coverageSummary } from '../../pipeline/prerender_site.mjs';
import { cellState, renderCoverage, shortName } from '../../site/coverage.js';

const registry = { areas: { eda: { name: 'EDA', default_on: true, venues: [
  { key: 'conf', kind: 'conference', display: 'Example Conference (EXC)',
    years: { 2006: { source: 'crossref' }, 2007: { source: 'none', note: 'Not held' }, 2008: { source: 'none' } } },
  { key: 'jrnl', kind: 'journal', display: 'Example Journal' },
] } } };
const rows = { conf: [{ y: 2004, a: 1 }, { y: 2005, a: 2 }, { y: 2006, a: 0 }, { y: 2008, a: 1 }, { y: 2011, a: 1 }], jrnl: [] };

test('coverage comes from published credit, not from the venue list', () => {
  const summary = coverageSummary(registry, (area, venue) => rows[venue], 2010);
  const [conf] = summary.areas[0].venues;
  // 2006 is listed in the registry but has no credit; 2004 and 2011 are out of range.
  assert.deepEqual(conf.years, [2005, 2008]);
  assert.deepEqual(conf.none, { 2007: 'Not held' });
  assert.equal(cellState(conf, 2005).cls, 'cov-ok');
  assert.equal(cellState(conf, 2006).cls, 'cov-absent');
  assert.equal(cellState(conf, 2007).label, '2007: Not held');
  const html = renderCoverage(summary);
  assert.match(html, />EXC<\/th>/);
  assert.match(html, /Journals:<\/span> Example Journal/);
});

test('short names use the trailing acronym', () => {
  assert.equal(shortName('Design Automation Conference (DAC)'), 'DAC');
  assert.equal(shortName('Symposium on VLSI Technology'), 'Symposium on VLSI Technology');
});

test('the published summary lists every registered venue', () => {
  const published = JSON.parse(readFileSync(new URL('../../site/coverage-data.json', import.meta.url)));
  const areas = JSON.parse(readFileSync(new URL('../../site/data/areas.json', import.meta.url))).areas;
  const count = (list) => list.reduce((n, a) => n + a.venues.length, 0);
  assert.equal(count(published.areas), count(Object.values(areas)));
});
