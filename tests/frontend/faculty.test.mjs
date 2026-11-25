import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { facultyIndex, renderFacultyContext } from '../../site/core/faculty.js';
import { app, DEFAULT_CONFIG, loadFacultyContext } from '../../site/core/engine.js';

const exported = JSON.parse(readFileSync(new URL('../../site/faculty/current.json', import.meta.url)));
const data = { schema_version: 1, field: 'ece', policy_id: 'us-ece-affiliated-v4', metric_id: 'ece_affiliated_faculty',
  schools: [{ institution_id: 'https://openalex.org/I1', name: 'Example University', headcount: 12,
    incoming_headcount: 2, current_headcount: 10, observed_on: '2026-11-22',
    policy_id: 'us-ece-affiliated-v4', roster_url: 'https://university.edu/faculty' }] };

test('only ECE opts into faculty context; sister configurations omit it', () => {
  assert.equal(DEFAULT_CONFIG.facultyDataPath, null);
  for (const field of ['biology', 'earth-space']) {
    assert.equal(facultyIndex(data, field).size, 0);
    const source = readFileSync(new URL(`../../site/${field}/main.js`, import.meta.url), 'utf8');
    assert.doesNotMatch(source, /facultyDataPath/);
  }
  assert.match(readFileSync(new URL('../../site/main.js', import.meta.url), 'utf8'), /facultyDataPath/);
});

test('verified counts keep their observation date across publication filters', () => {
  const index = facultyIndex(data, 'ece');
  assert.equal(index.size, 1);
  const school = index.values().next().value;
  const html = renderFacultyContext(school);
  assert.match(html, /ECE-affiliated faculty/);
  assert.match(html, /\(2 incoming\)/);
  assert.match(html, /Observed Nov 22, 2026/);
  app.sel = { from: 2016, to: 2020 };
  assert.equal(renderFacultyContext(school), html);
  app.sel = { from: 2025, to: 2025 };
  assert.equal(renderFacultyContext(school), html);
  assert.equal(renderFacultyContext(index.get('unsupported')), '');
});

test('unknown counts, invalid dates, unsafe links, duplicates and wrong policies are omitted', () => {
  for (const mutation of [{ headcount: null }, { headcount: -1 }, { observed_on: '2026-02-31' },
    { roster_url: 'javascript:alert(1)' }, { policy_id: 'other' },
    { incoming_headcount: -1 }, { incoming_headcount: 1000 }, { current_headcount: 0 }]) {
    const payload = structuredClone(data);
    payload.schools = [{ ...payload.schools[0], ...mutation }];
    assert.equal(facultyIndex(payload, 'ece').size, 0);
  }
  const duplicate = { ...data, schools: [data.schools[0], data.schools[0]] };
  assert.equal(renderFacultyContext(facultyIndex(duplicate, 'ece').get(data.schools[0].institution_id)), '');
  assert.equal(facultyIndex({ ...data, schools: [null, data.schools[0]] }, 'ece').size, 1);
});

test('optional failures and late responses cannot replace another field context', async () => {
  const originalFetch = globalThis.fetch;
  const originalConfig = app.config;
  const originalFaculty = app.faculty;
  try {
    const config = { fieldId: 'ece', facultyDataPath: 'faculty/current.json' };
    app.config = config;
    app.faculty = new Map();
    globalThis.fetch = async () => { throw new Error('offline'); };
    await loadFacultyContext(config);
    assert.equal(app.faculty.size, 0);
    let resolve;
    globalThis.fetch = () => new Promise(r => { resolve = r; });
    const pending = loadFacultyContext(config);
    app.config = { fieldId: 'biology' };
    resolve({ ok: true, json: async () => data });
    await pending;
    assert.equal(app.faculty.size, 0);
  } finally {
    globalThis.fetch = originalFetch; app.config = originalConfig; app.faculty = originalFaculty;
  }
});

test('legacy counts retain their narrower label and cannot be relabeled as affiliated', () => {
  const legacy = structuredClone(data);
  legacy.policy_id = 'us-ece-current-v3';
  legacy.schools[0].policy_id = legacy.policy_id;
  assert.equal(facultyIndex(legacy, 'ece').size, 0);
  delete legacy.metric_id;
  const html = renderFacultyContext(facultyIndex(legacy, 'ece').values().next().value);
  assert.match(html, /courtesy excluded/);
  assert.doesNotMatch(html, /ECE-affiliated faculty/);
  assert.equal(facultyIndex({ ...data, metric_id: undefined }, 'ece').size, 0);
});

test('public export contains only counts approved under its declared metric', () => {
  const index = facultyIndex(exported, 'ece');
  assert.equal(index.size, exported.schools.length);
  assert.equal(exported.metric_id, 'ece_affiliated_faculty');
  assert.ok(exported.schools.every(s => s.policy_id === exported.policy_id));
});
