# US faculty context pilot results

> This records the initial feasibility stage. The subsequent official-membership
> review resolved the five current counts; see [current status](faculty-current-status.md).
> The user subsequently requested inclusion of officially announced incoming
> professors. Qian Xu and Carmen Amo Alonso are included under policy v3, with
> their 2027 starts retained. Original pilot decisions and sampling remain intact.

**Proceed with a reviewed US faculty directory. Keep public headcounts on hold
until appointment boundaries and conflicting records are reconciled.** The pilot
shows that official university sources can support both rosters and exact
person-to-paper links. It also shows that directory totals cannot safely become
a comparable faculty column without review.

The five units are Berkeley EE within EECS, Illinois ECE, Stanford EE, UT Austin
ECE, and Georgia Tech ECE. Sources were retrieved on 22 November 2026. The
software uses versioned JSON/CSV and the existing static-site architecture. No
database is needed for this pilot.

## What was completed

- Collected 736 directory entries across the five units, including supplementary
  appointment categories. These are extracted entries, not 736 verified current
  research faculty.
- Preserved original titles, source links, retrieval times, content hashes,
  category decisions, and unresolved cases. Checked pagination and duplicate
  profile identifiers.
- Drew and reviewed a fixed sample of 15 roster members and a separate fixed
  sample of 15 paper authorships, plus prominent-contributor and difficult cases.
- Accepted 16 specific authorship links for nine people. Exact references on
  university or officially linked personal publication pages were corroborated
  against publisher-deposited author positions and author counts. Two links
  belong to a person whose current faculty eligibility remains unresolved.
- Checked the original records against a 671-file ECE cache inventory. A
  direct scan covered 570,925 cached records in about 20 seconds; a local database
  would add complexity before solving a demonstrated performance problem.

The publication window is 2016–2025 across registered ECE venues, including
optional areas. This is an identity experiment over raw cached records: research
type, exclusions, and credit eligibility were not re-evaluated. An accepted link
does not certify that the work contributes to a particular ranking selection.

## What the sources taught us

**Directory membership needs an appointment decision.** Illinois separates
department faculty from affiliates, adjuncts, research faculty, and emeriti.
Its broader facts-page total uses another definition. Georgia Tech's faculty
filter includes supplementary categories and administrative titles whose
underlying faculty role is unclear. Those entries remain separate or unresolved.
[Illinois categories](https://ece.illinois.edu/about/directory),
[Georgia Tech directory](https://ece.gatech.edu/directory/all?field_person_groups_target_id=2323).

**Even official pages can disagree.** Berkeley lists Qian Xu as an assistant
professor, while the personal site linked by the university says the appointment
is incoming. The pilot withholds current-count eligibility while retaining
verified paper identity. Stanford's directory lists Priyanka Raina as assistant
professor; the central profile lists associate professor and identifies the
courtesy CS appointment separately.
[Berkeley profile](https://www2.eecs.berkeley.edu/Faculty/Homepages/qianxu.html),
[linked personal site](https://deltaxdeltaq.github.io/publications/),
[Stanford profile](https://profiles.stanford.edu/priyanka-raina).

**A school's published total is a cross-check, not an automatic correction.**
UT Austin's overview and current faculty category do not reconcile under the
pilot's title rules. The sources do not establish an aligned census date and
eligibility definition, so no public total is approved.
[UT Austin people overview](https://ece.utexas.edu/people),
[ECE faculty category](https://ece.utexas.edu/people/faculty/ece).

**Exact publications solve cases that names do not.** An Illinois profile links
Minjoo Lawrence Lee to publications naming Minjoo Larry Lee. Stanford publication
references resolve specific authorships with synthetic cached IDs. An officially
linked publication list resolves a Qian Xu authorship with no cached author ID.
Names alone retrieved many competing identities for several sampled people.
[Lee profile](https://ece.illinois.edu/about/directory/faculty/mllee),
[Rosenblum profile](https://profiles.stanford.edu/mendel-rosenblum).

**The exact work matters.** A lab-listed journal article and a cached conference
item share a title. That title was insufficient to approve the conference link.
Likewise, an officially linked Berkeley papers page returned 404. Failed links
and incomplete publication lists remain unresolved evidence, not zero output.

**Current employment and historical credit must stay separate.** Yuan Cao's
linked publication list identifies a cached MIT-affiliated paper while Berkeley
lists his current faculty role. Other historical high-credit contributors are
listed as emeriti or have official appointments elsewhere. Their earlier paper
credit remains at the institution printed on the paper.
[Cao publication list](https://www.caorqmlab.com/publications),
[Robert Heath biography](https://jacobsschool.ucsd.edu/people/profile/robert-w-heath-jr).

## Software decision

Use the [file-based architecture](faculty-software-architecture.md): collectors
produce observations, reviewed decisions establish appointments and individual
authorship links, and validation precedes small optional JSON exports for the
shared frontend. Start with US ECE. A later frontend change must still be checked
against Biology and Earth & Space configurations.

One existing author-summary issue deserves a separate fix: aggregation groups
missing author IDs under a shared key, so a displayed aggregate name can combine
unrelated authors. The pilot records those groups as unusable person identities
and works from individual raw bylines instead. It changes no aggregation or
ranking files. See `pipeline/aggregate.py` around `author_names[author_id]` and
`aggregate-identity-findings.json` in the evidence bundle.

## What is ready and what remains

The collection/matching workflow and its evidence files are ready for review.
Integrity validation and seven targeted tests pass. There is no independent
second review or representative accuracy estimate; positive examples were
deliberately investigated, and unresolved controls remain visible. No school has
a census approved for public display.

Next, resolve the five rosters' remaining appointment boundaries and effective
dates, review them independently, and measure refresh work through an actual
second observation. Then expose sourced school details before expanding the US
school set. Source failures should retain the last accepted snapshot and flag
its freshness. Faculty normalization of scores remains a separate methodology
decision.

## Evidence and reproduction

The [checklist](faculty-pilot-checklist.md) links the scope and review rules.
Evidence lives in `data/faculty-pilot/2026-11-22/`: `roster.csv` is the readable
roster; `roster-reconciliation.json`, the three sample-review files, and
`stress-case-reviews.json` explain decisions; `accepted-matches.json` contains
individual links; `validation.json` records checks. `schools.json` deliberately
leaves `publishable_headcount` null. The pre-review sampling population remains
frozen so an appointment correction does not quietly replace a difficult case.

```sh
python3 pipeline/faculty_pilot.py collect
python3 pipeline/faculty_pilot.py sample
python3 pipeline/faculty_pilot.py discover
python3 pipeline/faculty_pilot.py scan
python3 pipeline/faculty_pilot.py anchors
python3 pipeline/faculty_pilot.py anchored-papers
python3 pipeline/verify_faculty_pilot.py
python3 -m unittest tests.test_faculty_pilot -v
```

Review decisions and publisher checks are retained inputs, not automatically
approved outputs of a crawler. Raw pages are in ignored scratch space; source
URLs and hashes, extracted facts, and review decisions are retained. Re-fetching
a changed page requires a new observation and review. Validation can check saved
facts and available snapshots, but cannot reconstruct old HTML once scratch
copies are removed. Source-date changes must not be passed off as a historical
census replay.

ECE ranking data, Biology, and Earth & Space were retained and not refreshed.
There was no public-site update, commit, push, or deployment.
