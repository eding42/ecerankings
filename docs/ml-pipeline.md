# Publisher-first ML collection

`pipeline/harvest_ml.py` stages ICLR, ICML, and NeurIPS works in the existing
`works.jsonl` envelope. It never writes the production cache or enables ML.
Publisher membership and bylines remain canonical; an enrichment record cannot
admit another paper or change the author-credit denominator.

## Sources and evidence

- ICLR: official proceedings, reconciled with authenticated OpenReview.
- ICML: the edition's PMLR volume, with main-track filtering.
- NeurIPS: the official proceedings book and configured track labels.
- Affiliations: identity-checked OpenAlex work authorships or the final publisher
  PDF. PDF evidence takes precedence; `--prefer-openalex` reverses that choice.
- Semantic Scholar supplies DOI/arXiv discovery hints only. Author-profile
  affiliations cannot earn historical credit.

Supported editions and included tracks live in `EDITIONS` in the script.
Unsupported years fail explicitly. Follow the source-specific membership
checks instead of treating a search-result count as a proceedings total.

## Collect and inspect

Python 3.11+ is sufficient. PDF stages also need `pdftotext` and `pdftoppm`.
Read API keys from the ignored root `.env`. OpenReview reconciliation needs an
`OPENREVIEW_TOKEN` or the account's `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`.
Never copy credentials into reports or checkpoints.

```sh
python3 pipeline/harvest_ml.py --venue iclr --year 2025 --stage all
python3 pipeline/harvest_ml.py --venue iclr --year 2025 --stage gates
```

`all` runs membership, discovery, OpenAlex enrichment, PDF extraction, build,
and gates. Each stage checkpoints inputs and outputs. Failed lookups stay
retryable; an HTTP challenge never becomes an empty proceedings list.

- `--stage-root` selects isolated storage (default `.tmp/ml-harvest/`).
- `--max-list-calls` and `--max-search-calls` cap OpenAlex usage for the run.
- `--offline` reuses cached responses; it cannot finish missing enrichment.
- `--restart-stage` invalidates the selected stage and downstream checkpoints.
- `--stage reconcile-openreview` compares accepted notes with publisher membership.
- `--stage normalize` resolves this edition's strings in the shared affiliation
  map. It is explicit because it writes curated data; it is never part of `all`.

Builds go to `<stage-root>/cache/<venue>/<year>/works.jsonl`. Membership,
identifier discovery, OpenAlex evidence, PDF text, state, and review queues stay
under the same staging root. Extractor-version changes reparse saved text.
Partial extractions stay in review; they are not silently credited.

## Verify PDF evidence

```sh
python3 pipeline/harvest_ml.py --venue iclr --year 2025 --stage verify-prep
python3 pipeline/harvest_ml.py --venue iclr --year 2025 --stage verify-status
```

Use the [verification skill](../.agents/skills/verify-pdf-affiliations/SKILL.md)
with the user's selected model and scope. Workers read source images and save
one complete draft per paper. The parent checks batch identity, every author's
name/index/order, and image accuracy before accepting results. Draft completion
alone is not proof of affiliation accuracy. Preserve incomplete attempts and
unclear marks for review.
Preparation records the full selected sample in `pdf-verify/selection.json`,
including papers omitted by a pilot limit or rendering failure. The accuracy
gate requires that selection to be fully reviewed; older preparations without
the selection file must be prepared again before the gate can pass.
An `unclear` or `not_found` image verdict suppresses that author's unconfirmed
PDF extraction, and `not_found` also prevents the byline gate from passing.
For a PDF with an extra author or another material difference from the publisher
byline, record `byline_discrepancy: true` on the paper's result and explain it
in `notes`; this blocks both the byline gate and, for a sample paper, sample
completion until the discrepancy is resolved.
Use `source_discrepancy: true` for an unresolved mismatch suggesting the PDF
may be the wrong publication. The build quarantines that PDF's evidence and
the PDF evidence gate fails pending reconciliation.
A verdict judges the extraction its batch carried. After an extractor-version
change, rerun the pdf stage and `verify-prep`, then have the sample judged
again; until then `gates` reports the previous extractor's accuracy.

```sh
python3 pipeline/harvest_ml.py --venue iclr --year 2025 --stage verify-apply
python3 pipeline/harvest_ml.py --venue iclr --year 2025 --stage build
python3 pipeline/harvest_ml.py --venue iclr --year 2025 --stage gates
```

Resolve new strings through the adjudication workflow, replay earlier decisions
after normalization, and rerun map QA. Do not edit historical author credit from
knowledge of an author's current employer.

## Resolve discrepancies

Image checks that flag a byline or document discrepancy, or an author not found
on the page, are resolved in `data/refresh/ml-discrepancy-resolutions.jsonl`
(durable; the staging tree is not). One record per paper: `byline`
(`same_people` | `different_people`), `source` (`same_paper` |
`different_document`), `authors` (`{"<index>": {"resolution": "present",
"page_affiliations": [...]} | {"resolution": "absent"}}`), `evidence`,
`decided_by`. `different_people` and `different_document` withhold the paper's
PDF evidence; the extractor-accuracy sample is scored on the original verdicts.

The institution-resolution gate counts a string adjudicated as non-university
(a manual map row without an institution id) as resolved: it was decided, and it
deliberately credits nobody. `unresolved` decisions still count against it.

## Credit policy decisions (user, 2026-11-19)

- A string that states no institution ("Independent Researcher", "Unaffiliated",
  "None", a freelance-journalist byline) is recorded as non-credit (`noneducation`).
- Only printed affiliation text earns credit. A logo alone does not.
- A role or footnote mark ("Core Authors (MBZUAI)") names a role, not a workplace,
  and earns no credit.
- A string naming two or more universities, or a joint lab, stays `unresolved`
  (or `needs-policy`) until map rows can carry several institutions; credit would
  then split evenly, as `PLAN.md` already specifies for multi-affiliation authors.

- Northeastern University: a string with no location is credited to Northeastern
  University (US); a string printing a China location is credited to Northeastern
  University (Shenyang, CN).
- A paper whose official listing prints no authors (NeurIPS 2016 `5d616dd3...`,
  2017 `861dc9bd...`, 2018 `959a557f...`, 2019 `08040837...`) is a documented
  exception in `data/refresh/ml-authorless-papers.jsonl` (user, 2026-11-20). It
  stays a member, earns no credit, and does not block `byline_integrity`. The
  gate reports `documented_authorless_papers`; any other empty byline still fails.
  A publisher-first byline is never taken from the PDF.

## Acceptance

An edition stays `staged` unless every gate passes: membership discrepancy at
most 1% against every official count the edition has (as for other venues, an
official count proves the source on recent editions; an older edition from the
same source with no published count passes and is reported `anchored: false`;
user, 2026-11-20), paper-specific affiliation coverage at least 90%, institution resolution
at least 95%, and extractor accuracy at least 98% on the designated image sample.
Byline integrity, track purity, and zero profile-affiliation leakage are also
required. Do not change thresholds or the sample to make a run pass.

Passing an edition's gates permits candidate preparation, not automatic
promotion. Follow the [release runbook](refresh-runbook.md) and preserve current
limitations in the [pilot checkpoint](ml-pilot-status-2026-10-29.md).
