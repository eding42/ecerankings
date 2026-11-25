# Faculty context pilot checklist

> Completed feasibility checklist. The later current-count implementation and
> remaining rollout work are tracked in [the roadmap](faculty-vision-roadmap.md)
> and [current status](faculty-current-status.md).

The pilot tests whether we can show a trustworthy faculty count beside a school's
research output, and connect verified people to the papers already counted.
It covers five US ECE units. It does not change scores, paper credit, venue policy,
or public assets. Biology and Earth & Space retain their existing datasets and
are outside this collection; their different appointment and institution types
remain a requirement for any later shared implementation.

## Completion checklist

- [x] Read `AGENTS.md` and `PLAN.md`; record existing working-tree changes.
- [x] Define the pilot population, evidence rules, school selection, and outputs
  before collection.
- [x] Confirm an official roster source and unit boundary for each school.
- [x] Extract every available roster entry, preserve source names and appointment
  titles, and record inclusion, exclusion, or uncertainty with a reason.
- [x] Check pagination, duplicates, category boundaries, and a second official
  source where available. Distinguish a fully enumerated source from an
  independently reconciled faculty census.
- [x] Record source URLs, retrieval times, hashes, extraction methods, and
  freshness limitations. Keep observations separate from effective employment
  dates. Do not collect personal contact information.
- [x] Produce a roster and category counts for each school; flag partial or
  unresolved populations rather than publishing a false total.
- [x] Select reproducible faculty and paper samples before accepting matches.
- [x] Test both directions: roster members to cached papers, and cached
  authorships to official people. Include random and difficult cases as well as
  prominent contributors.
- [x] Save candidate links separately from accepted person-to-authorship links.
  Verify accepted examples with official publications or identifiers plus byline
  evidence. Preserve the paper's original institution attribution.
- [x] Exercise joint appointments, emeriti/teaching/adjunct categories, common
  names, moves, and missing or synthetic author IDs; record untested cases.
- [x] Validate schema, references, unique keys, source evidence, category totals,
  sampling reproducibility, and the original cache records for accepted matches.
- [x] Report what the sample establishes, unresolved errors, collection effort,
  maintenance needs, and a go/no-go recommendation. Do not estimate global recall
  or roster completeness from a small convenience sample.
- [x] Reconcile every checklist item with actual evidence and deliver the results.

## Five schools and why

| School | Proposed unit | What it tests |
| --- | --- | --- |
| UC Berkeley | Electrical Engineering within EECS | Combined department and overlapping appointments |
| University of Illinois Urbana-Champaign | Electrical and Computer Engineering | Large standalone ECE department |
| Stanford University | Electrical Engineering | Private university, joint appointments, integrated profiles |
| University of Texas at Austin | Electrical and Computer Engineering | Regular, professional, and affiliate faculty categories |
| Georgia Institute of Technology | Electrical and Computer Engineering | Large public school and mixed faculty/staff directory |

Selection is deliberate, not representative of all universities. Record any
source-driven change to the unit or school before using a replacement.

The original exploratory selection included Manchester, ETH Zurich, and KAIST.
Manchester's Research Explorer returned HTTP 403 with `Cf-Mitigated: challenge`;
Imperial was considered as a UK replacement. The user then narrowed the pilot to
the United States before publication matching. Stop international collection,
retain the scope history, and use the five US schools above for the active pilot.

## Counting policy for this experiment

This section preserves the initial feasibility rules. The active policy is
[`us-ece-current-v3`](../data/faculty/policy.json), which includes officially
announced incoming professors and records their status and start dates.

Count unique people with an explicitly listed current regular research academic
appointment in the selected unit. Include assistant/associate/full professors;
classify US lecturers and professors of instruction/practice as teaching faculty.
Preserve the original title. International title equivalence is future work.

Keep teaching-only, adjunct/courtesy, visiting/honorary, emeritus, and research-only
appointments in separate categories. An unclear title stays unresolved. A joint
appointment does not imply half an FTE: count a person once within the selected
unit, record the joint role when evidenced, and make no FTE claim. Directory
membership alone does not prove full-time employment, tenure, or recent activity.

These are pilot classification rules, not an approved global faculty definition.
Faculty without a selected-venue paper remain in the roster. A roster count stays
independent of publication matches and of the site's year/area selection.

## Matching policy

Official appointment evidence establishes faculty status. An official profile/CV
listing an exact publication, or an officially linked identifier corroborated on
the work, can establish a person-to-paper link after inspecting the byline. Name,
institution, topic, and coauthors alone produce candidates for review. A correct
OpenAlex profile match does not approve every paper in that profile.

Use local person IDs and individual `(work, byline position)` links because cached
author IDs may be null, synthetic, split, or merged. Keep unmatched people,
unmatched authorships, conflicting identities, and verified non-faculty distinct.
Never infer a faculty appointment from last-author position or from
`last_known_institutions`. Current appointments never overwrite publication-time
affiliations or change the original author-count denominator.

## Deliverables and decision

Save factual rosters, source metadata, sample selections, reviewed matches, and
machine-readable validation under `data/faculty-pilot/2026-11-22/`. Keep collector
and validator code under `pipeline/`. Put the readable findings in
`docs/faculty-pilot-results.md`. Raw downloaded pages may live in ignored scratch
space; permanent evidence must include the factual fields needed to inspect each
decision and the corresponding source locator.

A useful outcome is a clear account of which sources support a dated headcount,
which matching methods survive difficult examples, and where review is required.
Do not ship a global faculty column or per-faculty ranking from this pilot. No
commit, push, or deployment is authorized by this checklist.

## Completed evidence and remaining product gates

The experiment is complete; the findings are in
[US faculty context pilot results](faculty-pilot-results.md). A checked item means
the investigation was performed and its limitations recorded, not that a public
faculty census was approved.

| Checklist evidence | Artifact under `data/faculty-pilot/2026-11-22/` |
| --- | --- |
| Source provenance and scope | `sources.json`, `profile-sources.json`, `review-sources.json`, `control-sources.json`, `scope-history.json` |
| Full extraction and categories | `roster.csv`, `roster.json`, `schools.json` |
| Reconciliation and uncertainty | `roster-reconciliation.json`, `roster-review-overrides.json` |
| Fixed populations and selections | `sampling-population.json`, `roster-sample.json`, `authorship-sample.json`, `high-credit-sample.json` |
| Both review directions | `roster-sample-reviews.json`, `authorship-reviews.json`, `high-credit-reviews.json` |
| Difficult cases | `stress-case-reviews.json`, `identifier-stress-sample.json`, `aggregate-identity-findings.json` |
| Exact-work links and publisher checks | `publication-anchors.json`, `accepted-matches.json`, `publisher-checks.json` |
| Integrity and reproducibility | `cache-inventory.json`, `scan-run.json`, `discovery-run.json`, `sampling-replay.json`, `validation.json` |

Public headcounts still require appointment reconciliation and independent review.
Global accuracy and ongoing manual cost were not estimated: this small deliberate
sample and a single collection cannot establish them. Record actual reviewer time
and source changes during the next observation. No frontend or ranking release
is part of this completed experiment.
