# Faculty context software architecture

Add an evidence-backed faculty directory as an offline enrichment of the existing
static ranking site. Begin with US ECE schools. Faculty size and verified paper
contributors provide context; the ranking calculation and publication-time
attribution keep their existing meanings.

The [vision and roadmap](faculty-vision-roadmap.md) govern scope: current counts
first, labeled **ECE-affiliated faculty** and based on official regular,
in-residence, affiliated/below-the-line, courtesy and joint/secondary EE/ECE professorial appointments,
including announced incoming professors. Retain incoming status and announced start
dates; expose current and incoming subtotals within the total. CS-only contributors are excluded
from faculty context even when their papers occur in registered ECE venues. A
real joint EE/CS appointment qualifies, including courtesy. Preserve each explicit
subtype; use `joint_secondary` for an official professorial appointment whose
regular-versus-courtesy subtype is unspecified. Generic affiliates and the other
excluded appointment types do not qualify merely because the label says affiliated.

Policy v5 broadens the earlier regular/in-residence population. Immutable school
observations retain their exact policy ID and checksum. Historical reads validate
against the matching archived policy; acceptance still requires the active policy.
The derived registry preserves people, claims and individual paper links from
older observations but marks their school summaries `needs_update`, retaining the
earlier total in `previous_count`. Only independently reconciled active-policy
counts enter the public bundle. Both the frontend and packaging gate check the
metric/policy pairing, so an old count cannot acquire the broader label. The five
pilot observations need courtesy-coverage upgrades; USC needs a fresh v4 audit.

Browser access and source identity are explicit. HTTP response bodies retain
`response_sha256`; rendered browser DOM instead has `response_sha256: null`,
`capture_format: browser_dom`, `capture_sha256` and the capture tool. Never present
a DOM fingerprint as an origin HTTP-response hash or invent an HTTP status.
Browser judgments require a pinned host-capture packet and its declared shared
review mode. Unlinked or shared-profile university entries receive scoped entry
IDs; they do not acquire invented personal profile URLs.

`faculty_refresh.py reassess-policy --school <key>` creates a new candidate under
an amended policy while preserving source dates, hashes, parent and prior review.
It does not claim a fresh retrieval. A frozen shared-capture audit may use those
same-date captures predating its job, with a candidate-bound immutable packet and
a new independent judgment. Ordinary independent-download audits still require
post-job retrievals. Source/configuration changes or incomplete captures require
collection. The expanded affiliate scope required additional UC San Diego pages;
those sources were collected rather than treated as already covered.

## Implementation readiness

The current-count pilot has working records, validation and static export.
The reusable collection/review/accept/export workflow is implemented and has
been exercised with second live observations of Berkeley and Georgia Tech.
Additional directory formats, nationwide coverage and scheduling remain work.
The design sections below include intended behavior as well as implemented code;
this table defines the present boundary.

| Component | What works now | Remaining work |
| --- | --- | --- |
| Person and appointment records | Stable assigned IDs, names/variants, external ID assertions, multiple-appointment structure, membership/category/status, incoming dates | Explicit merge/split and move workflows; automatic cross-profile identity reconciliation |
| Evidence and decisions | Persistent factual claims, source URLs/dates/hashes, source-change detection, conflicts, reviewed decisions and versioned policies | Automatic claim reconciliation and copied-source provenance analysis; reviewed facts remain the authority |
| School collection | Configurable school/date inputs, per-school commands, pagination checks and five directory-layout adapters | Adapters for additional directory formats and reviewed school configurations |
| School queue | Candidate institutions, priorities, states/history, per-school commands, collection attempts and refresh due dates | Broader US inventory, batch/scheduled execution, and coverage measurement beyond publication-derived candidates |
| Review and publication | JSON/CSV review, validation, incoming/current totals, hashed public export and optional shared display; local packaging checked across all three fields | Public rollout and browser layout QA; a dedicated review UI is optional, not required for the file-based workflow |
| Paper identities | Candidate discovery, reviewed individual authorship links and exact-byline rechecks | Full-roster matching, measured precision/coverage and scalable review of ambiguous profiles; matching remains a small pilot |
| Refresh and evidence retention | Immutable factual source snapshots and observation lineage, reviewed diffs, locked/atomic accepted pointers, staged exports, stale-review protection and tested failure retention | Scheduled collection; wider experience with real appointment changes |
| Independent agent audit | Automatic separate-agent launch after successful collection, blind brief, full new-school audit or changes plus seeded refresh sample, immutable result and execution receipt, mandatory reconciliation gate | Broader operational experience; local CLI needs the configured model and official-source access |
| Historical rosters | Appointment date fields and observation/decision groundwork | Complete historical evidence, employment intervals, point-in-time school queries and UI |

Live refreshes found the same roster entries at both schools. Berkeley required
explicit reconciliation for two emeritus profiles whose original full-page
projections were unavailable; their current official headings match the prior
independently reviewed appointment facts. No new independent audit was run;
unchanged appointment-fact reviews were inherited with their scope recorded.
A Georgia Tech HR-page timeout produced a rejected candidate and left the
accepted pointer unchanged; a successful retry was reviewed and accepted.
These are same-day repeat observations, not a longitudinal accuracy study.
Those earlier accepted observations predate the automatic audit stage. Every
future acceptance, including an unchanged refresh, requires a fresh agent result.

## Data flow

```text
Official university directories and profiles
                 |
       source-specific collectors
                 |
   observed people, roles, and source evidence
                 |
     independent agent audit of the candidate
                 |
      reconcile appointment decisions and findings
                 |
Existing cached papers --> candidate matching --> reviewed authorship links
                 |                                  |
                 +--------- validation -------------+
                                  |
                       small public JSON files
                                  |
                shared static frontend in site/core/
```

Collection and matching run on a developer machine or scheduled build worker.
Visitors make no calls to university websites, OpenAlex, an LLM, or a database.
The first pilot creates reviewable evidence files; frontend integration follows
only after the data supports the display.

## Records and ownership

| Record | Responsibility |
| --- | --- |
| Person | Local identity, name variants, official profiles, external IDs with provenance |
| Appointment | Person, institution, department/EE track, original title, category, joint/courtesy status, known effective dates, observation date |
| Source | URL, retrieval status/time, response hash, factual evidence and locator |
| Decision | Inclusion or exclusion, evidence, rationale, reviewer, policy version, superseded decision |
| Authorship link | Person, work identifier, exact byline position, evidence, accepted/candidate/rejected status |
| Roster manifest | Unit boundary, category totals, pagination, completeness limits, validation and freshness |

Maintain a school collection queue with an explicit workflow state and transition
history. Seed candidate US institutions from existing ECE data, verify that an
in-scope unit exists, then collect systematically. Track source discovery,
enumeration, review, accepted count, and refresh state separately from any score.

A professor record aggregates evidence from multiple channels: department and
central university pages, university announcements, the professor's site/CV,
ORCID, and publisher/bibliographic records. Preserve original assertions and
their provenance rather than replacing them with one confidence number. Source
authority depends on the claim: departmental scope and official appointments,
personal identity and name variants, and exact paper authorship need different
evidence. Shared upstream provenance is recorded so copied assertions do not
count as independent corroboration.

Store subject membership separately from appointment category and paper identity:
`ece`, `cs_only`, `outside_ece`, or `unresolved`; and `included`, `excluded`, or
`unresolved` as an explicit reviewed decision. Include policy version and source
references. A generic Professor title is insufficient without an official EE/ECE
membership boundary. Official membership may come from a designated EE roster;
the degree title or a publication's topic is not a substitute.

Canonical inputs are versioned JSON/CSV evidence and decisions. The pilot reads
the existing CSV/JSON paper data directly. Consider a rebuildable local index
only if measured lookup costs justify it; there is no production database. Keep
raw downloaded HTML out of public assets. Retain only the factual fields needed for review, without contact
details or full biographies. Record source restrictions before public reuse.

Production person IDs are assigned once and retained through moves and profile
URL changes. The pilot's deterministic IDs identify source profiles; future
cross-profile merges need explicit, evidenced decisions. OpenAlex author IDs,
ORCID iDs, names, and profile URLs are external identifiers, not identity truth.

## Collection and review

Use small adapters for each directory's structure. Follow pagination, reconcile
categories against additional official sources, and fail visibly on extraction
errors. Keep failed collection distinct from an empty roster. Observing a page
today does not establish the employment date of each person on it.

The university's designated current EE/ECE roster is the population authority.
Official profiles disambiguate specific appointment types and jointly held roles.
Explicit official future-start, retirement, or departure information is reviewed
against the roster. A linked personal site can aid identity discovery and flag a
discrepancy but cannot independently overturn the university's classification.

Refreshes propose additions, title changes, removals, and source failures as diffs.
An unavailable profile does not automatically remove a person. Retain the last
accepted snapshot and mark its freshness when a source fails. Review ambiguous
appointment changes and identity conflicts before publishing a replacement.

After successful collection, `faculty_refresh.py observe` automatically prepares
an audit job and invokes the runner in `data/faculty/audit-config.json`. The
default is a fresh, ephemeral Terra agent (`gpt-6.1-terra`) through `codex exec`, in a temporary
working directory with a read-only sandbox and structured JSON output. The agent
receives the policy, official source configuration and required identities,
without collector classifications or prior counts. It independently retrieves
sources, enumerates the complete roster/categories and checks incoming hires and
omissions. It records actual retrieval hashes, times and GET/POST parameters.
Terra is the default for routine audits to control usage. Changing the reviewer
model does not relax coverage or acceptance requirements. Historical Astra
reviews retain their original execution receipts; the runner has no automatic
fallback to a more expensive model.

For host-managed review, `observe --audit-transport handoff` creates the same
mandatory job without starting a duplicate CLI agent. A reconciliation review
may attach `supplemental_sources`: immutable, successful HTTPS captures from the
same observation date, with matching source/evidence hashes. `prepare
--evidence-url URL` pins additional verdict-free source leads for the auditor.
Proposed inclusions awaiting independent confirmation can be saved as unpublished
drafts; the acceptance validator still rejects them.

When the auditor's network path fails, it may independently inspect a frozen raw
capture packet. The execution receipt explicitly records
`independent_judgment_of_shared_captures`, the packet hash, and the collector's
capture origin. Shared source IDs must match the pinned URL, response hash,
retrieval time and GET/POST parameters. This is independent judgment of a shared
primary source, not a claim of independent retrieval or a second university
confirmation. Independent directory enumeration and unresolved-case gates remain
required. Original captures and partial reviews are retained.

Schema validity is separate from substantive evidence review. An assessor may
import a result with an evidenced `--rejection` naming the affected people and
source IDs. The immutable audit bundle retains the original result, execution
receipt, rejection findings and metadata-validation errors. Rejected results
cannot satisfy acceptance or later export, even if the model declares complete
coverage and zero unresolved people. Drafts retain that rejection in their
lineage and collection-attempt status. A failed timestamp is preserved as a
validation failure rather than rewritten into a fresh-looking signoff.

A new school requires decisions for every candidate. A refresh requires every
changed person plus a seeded sample of unchanged roster entries: 10%, with a
minimum of 10 and maximum of 25, capped by available entries. The recorded seed
makes the selection reproducible. Excluded entries participate in sampling.
Use `prepare --force --full` to expand a refresh audit before correcting an
otherwise unsampled person. This sample is a review safeguard, not a measured
accuracy or completeness estimate.

The immutable job pins the candidate, parent, policy and school configuration.
The result pins the job, blind brief and agent execution receipt. Acceptance
requires completed coverage, independent roster/category agreement, evidence and
agreement with final appointment decisions, including incoming dates. Missing or
stale reviews, unresolved decisions, source failures, omissions and policy
ambiguities block acceptance. Resolve findings with evidence and rerun the audit
when necessary; a reviewer name or prose signoff cannot bypass the gate. Drafts
can be saved while blocked. The accepted roster and public count stay intact.
Equivalent current/past/outside-core labels for excluded emeritus appointments
do not create count disputes; current/outside-core labels for other active
excluded roles are also equivalent. Original states remain stored. Included
current versus incoming status, categories, membership and start dates still
compare explicitly; departed versus active roles remain distinct.

The reviewer proposes findings and decisions; only the deterministic acceptance
command can update accepted pointers. File permissions still define the trusted
operator boundary: hashes/receipts establish reproducible lineage, not a
cryptographic proof that an LLM fetched a source or an independent HR census.
The core remains standard-library Python; the external agent CLI is optional
for reading/exporting already accepted data and required for automatic new audits.

## Matching

Index work identifiers, names, institutions, author IDs, and byline positions from
the existing cache. Use names, known publications, identifiers, and affiliations
to retrieve candidates. Accept an individual authorship only when recorded
evidence connects the official person to that publication and byline slot.

Allow one person to map to multiple bibliographic profiles and preserve exceptions
inside mixed profiles. Never approve a whole author cluster because one paper
matches. Missing and synthetic IDs are valid inputs to review. Faculty status,
person identity, and a paper's institutional affiliation remain separate claims.

The matcher never rewrites raw papers, affiliation mappings, author counts, or
ranking credit. A person's current employer does not replace a paper's printed
affiliation. Faculty without a selected-venue publication remain in the roster.

## Publishing and shared frontend

After validation, export an optional institution index and lazy-loaded per-school
faculty JSON containing names, role categories, official links, source dates,
scope/completeness, and accepted publication links. Keep detailed review evidence
outside the public bundle.

The first implementation exports only current counts and official roster links;
per-school public person lists and paper-link views are later work. The internal
person records preserve those claims for review.

Implement display behavior once in `site/core/`, with optional field capability
and data-path configuration. The first dataset supplies US ECE appointments.
Schools and disciplines without supported records omit the feature; they do not
display zero faculty. A roster headcount is fixed to its census/observation and
does not change with publication filters. A filtered count must be labeled as
matched contributors, separately from total faculty.

Historical school rosters are a later phase. Keep immutable observations and
superseding decisions now, but export only the latest accepted current count in
the first release. Do not infer past employment from capture dates or make the
current count follow the publication-year slider.

Run relevant shared checks across ECE, Biology, and Earth & Space when frontend
or shared pipeline code changes. Biology's hospitals and Earth & Space's research
institutes require their own appointment policies before collection expands.

## Verification and rollout

Validate unique identities and authorship keys, evidence references, source
failures, classification totals, pagination, and reproducible samples. Audit
both accepted matches and unresolved cases. Report sampled accuracy separately
from roster completeness and matching coverage. Do not infer global recall from
this pilot or assign fake certainty to name matches.

The [US pilot checklist](faculty-pilot-checklist.md) records initial feasibility;
[current status](faculty-current-status.md) records the completed current-count
milestone and verification limits. Expand the school queue in reviewed batches
and measure an actual second observation before automating refresh decisions.
Per-faculty scoring and current-faculty credit reassignment are separate future
methodology decisions. The architecture requires no new production backend.

## Implemented files and commands

| File | Purpose |
| --- | --- |
| `data/faculty/policy.json` | Versioned membership, appointment and evidence rules |
| `data/faculty/schools.json` | School identity, directory URLs, GET/POST filters, explicit profile URL corrections, layout adapter and pagination limits |
| `data/faculty/accepted.json` | Atomic pointers to accepted immutable per-school observations |
| `data/faculty/evidence/` | Persistent extracted roster/appointment facts, retrieval metadata and content/semantic hashes; no full biographies or contact lists |
| `data/faculty/observations/<school>/` | Immutable candidate and accepted observations, source references and diffs |
| `data/faculty/pending-reviews/` and `attempts/` | Review templates/decisions and latest collection attempt, separate from accepted counts |
| `pipeline/faculty_audit.py`, `data/faculty/audit-config.json`, `audits/` | Agent runner, blind jobs/briefs, closed result schema, mutable execution states and immutable reviewed results/receipts |
| `data/faculty/policies/` and `review-history/` | Prior policy versions and decisions preserved when eligibility changes |
| `data/faculty/school-queue.json` | Candidate institutions, collection priority, state/history, next action and refresh date |
| `data/faculty/person-ids.json` | Assigned local identities retained across rebuilds |
| `data/faculty/people.json` | Names, identifiers, appointment decisions, claim evidence, conflicts and individual authorship links |
| `data/faculty/sources.json` | Successful source responses, URLs, dates, hashes, source types and provenance limits |
| `data/faculty/discovery-leads.json` | Additional-source candidates and excluded-category cross-checks without forced identity merges |
| `data/faculty/reviews/` | Per-school decisions and pinned independent audit references |
| `data/faculty/observations/` | Immutable derived observations; acceptance requires the matching validation report |
| `data/faculty/current.json` | Current observation pointer and school summaries |
| `data/faculty/roster-review.csv` | Readable review table generated by validation |
| `site/faculty/current.json` and `manifest.json` | Small optional public count bundle with its own hash gate |
| `site/core/faculty.js` | Shared optional display; only the ECE wrapper enables this dataset |

Original feasibility artifacts remain under `data/faculty-pilot/2026-11-22/`.
The reusable workflow reads school configuration, a requested observation date,
and accepted snapshots; adding a school requires a reviewed configuration and
an appropriate directory adapter. It is not an unattended nationwide crawler
or an implemented historical query service.

```sh
python3 pipeline/faculty_refresh.py init
python3 pipeline/faculty_refresh.py observe --school berkeley
# Collection automatically launches the configured independent agent.
# Reconcile its result with the emitted diff and review template, then:
python3 pipeline/faculty_refresh.py review --review path/to/review.json
python3 pipeline/faculty_refresh.py accept --review path/to/review.json
python3 pipeline/faculty_refresh.py export
python3 pipeline/faculty_registry.py validate
python3 pipeline/verify_faculty_pilot.py --recheck-authorships
```

`init` imports the already validated pilot once. Observation collection and its
agent audit write candidate/evidence/review files, never accepted data. Unchanged
facts can carry forward, with a fresh sampled audit; changed appointments need
explicit decisions and independent reconciliation. Directory absence alone is insufficient
departure evidence. Review files pin both candidate and parent, so a stale
review cannot overwrite a newer accepted observation. The requested observation
date must match actual retrieval dates; it cannot backdate live collection.

Retry a failed runner with `python3 pipeline/faculty_audit.py run --review
path/to/review.json`. A fresh job uses `prepare --force` before `run`; add `--full`
to require every person on a refresh. A configured `command` runner receives a
JSON object containing `brief` and `schema` on stdin and returns the result JSON
on stdout, without a shell. A host-managed T3 reviewer can use `prepare` and
`import --result path/to/result.json --receipt path/to/receipt.json` instead; the
receipt records job/candidate hashes, transport, actual run ID and successful
exit status. Explicit `handoff` configuration leaves the job pending until import;
it does not satisfy the gate. Runner failures/timeouts retain accepted data and
record failure without copying potentially sensitive agent stderr into artifacts.

The live USC contract test used a fresh Astra subagent through T3 and imported
its actual execution receipt. All 136 required records and nine lists were
returned; inaccessible official pages and ambiguous appointments kept coverage
incomplete. Acceptance was attempted and correctly rejected, with accepted
pointers and the public count bundle unchanged. An actual separate-process test
exercises automatic command launch; mocked tests check Codex arguments and
failure handling. The configured Codex model invocation has not been live-tested.

The accepted-pointer update is atomic and guarded by a process lock. Derived
registry files are rebuildable; public export validates a staged bundle before
replacing the previous directory, with rollback on installation failure.
No scheduled job was created. Export never runs the ranking aggregator. The
packager checks the faculty bundle's separate manifest while retaining all
existing ranking-data gates. Standard release authorization is still required.
The original full pilot verifier intentionally fails if its frozen publication
inventory changes; the scoped authorship recheck does not replace that audit.
