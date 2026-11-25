# Current faculty context: results and next steps

As of **25 November 2026**, the local public payload contains **94 verified
school counts** under `us-ece-affiliated-v5`: the top 50 plus 44 schools from
ranks 51-100 of the 2016-2025 US ranking (all 18 default areas). The definition
includes regular, in-residence, official affiliated/below-the-line, courtesy and
joint/secondary EE/ECE professors, plus announced incoming appointments with
separate incoming subtotals. Each person counts once per school. Practice-track
and teaching-track professors, research professors, adjuncts, visiting faculty,
emeriti and staff are excluded.

Ranks 51-100 were collected from official department pages with the generic
`cards`/`json_list` adapters (`pipeline/faculty_directories.py`), audited by a
separate agent and accepted with `pipeline/faculty_reconcile.py`. A school
counts only when every directory entry has a reconciled decision and the audit
reports no omission, source failure or unresolved person. Departments that
publish no directory category (for example emeritus or adjunct lists the
collector cannot read) are noted in the school's review rationale.

**Rank 51-100 schools not yet verified:**

| School | Status |
| --- | --- |
| Syracuse, Washington State, Missouri, Tennessee | Combined EE/CS units with no EE/ECE designation or filter; deferred by the owner (recorded `blocked`) |
| Chicago, UNC Chapel Hill | No official EE/ECE unit (recorded `out_of_scope`) |

Drexel's directory API answers only when sent the department page's own Referer
header and is paged; the project owner approved that on 2026-11-25. The pipeline
sends the header only for a configured same-site https page (`referer`, `page_offset`
on the list). Missouri S&T was closed by the owner's determination that Cheng-Hsiao
Wu, Chen Zhu, DongHyun Kim and Ahmad Alsharoa are not professors; an earlier audit
had seen official ECE pages that call Wu a Professor and Alsharoa an assistant
professor, so that determination overrides them and can be reversed. GWU's plain-text
emeriti are read by the `strong_lines_after_heading` option. IIT counts its university
directory filtered to ECE, which the owner designated as the official roster, plus new chair
Anna Barnett from the IIT news page (owner determination). Arizona counts the School of
Electrical, Computing, and Software Engineering faculty directory pages the owner supplied. Johns Hopkins refuses automated requests, so its four department lists are pinned captures
extracted in the owner's Chrome (`data/faculty/captures/jhu`, replayed by
`pipeline/faculty_capture.py`, recorded as `browser_dom` evidence and audited as shared
captures); Tennessee's single combined EECS department carries no EE label, so it is
`blocked`. Oregon State counts the
college directory filtered to its own 'Electrical and Computer Engineering' discipline
tag (the project owner supplied that boundary on 2026-11-25). ASU's roster was refreshed after
a cross-check against the Fulton ECEE directory found Michael Goryll missing from the
university feed (ASU now 84).

Four schools were closed on dated project-owner determinations (2026-11-25), each
recorded in the school's review rationale: Mines department head Abd Arkadan,
New Mexico chair Tim Kane and Houston joint appointee Mehdi Abolhassani are counted
as professors although no downloaded official page states their rank, and Kentucky's
Rohan Reddy Kalavakonda is counted on an institute news page quoting his
tenure-track Assistant Professor appointment. WashU's seven Senior Professors are
excluded as emeritus by owner determination (count unchanged).

**What is committed.** The release holds the accepted rosters with their full lineage
(observations, evidence, audits, policies), the schools/queue configuration, the pinned
JHU captures and the derived registry files. Building the registry from only that set
reproduces `people.json`, `sources.json` and `current.json` byte for byte. Working drafts
(`pending-reviews/`, `attempts/`, unaccepted observations and audit scratch) stay local.
`pipeline/verify_faculty_pilot.py` guards the earlier five-school paper-matching pilot. Its
strict check fails because the ICLR cache was rewritten after the pilot pinned its inventory;
`--recheck-authorships` passes (16 accepted authorships). The school headcounts do not depend on it.

Faculty-to-paper matching and per-faculty scoring were evaluated and dropped:
counts stay fixed per school and do not change ranking credit. Faculty changes
do not alter publication credit or ranking scores. ECE, Biology and Earth &
Space publication datasets are **retained**, with freshness **unassessed** by
this faculty-only collection. Nothing has been committed, pushed or deployed.

The following sections preserve the earlier pilot and implementation history.
Their old policy names, counts and migration states describe those earlier stages.

## Five-school result under the earlier v3 policy

Observed **22 November 2026**, under policy `us-ece-current-v3`. At the user's
direction, the total includes officially announced incoming regular professors;
their future status and start dates remain recorded.

| School and unit | EE/ECE faculty, including incoming | Official roster |
| --- | ---: | --- |
| Berkeley, Electrical Engineering within EECS | 59 (2 incoming) | [EE list](https://www2.eecs.berkeley.edu/Faculty/Lists/EE/list.html) |
| Illinois Urbana-Champaign, ECE | 88 | [Department faculty](https://ece.illinois.edu/about/directory/faculty-dept) |
| Stanford, EE | 59 | [Active faculty](https://ee.stanford.edu/people/faculty?type=active&limit=60) |
| UT Austin, ECE | 71 | [ECE faculty](https://ece.utexas.edu/people/faculty/ece) |
| Georgia Tech, ECE | 106 | [Faculty directory](https://ece.gatech.edu/directory/faculty) |

These are reviewed headcounts of regular and in-residence appointments, including
announced incoming hires and counting each person once per school. The export
keeps current and incoming subtotals. They describe the observed university websites,
rather than payroll or FTE. Teaching/practice, research-only, adjunct/courtesy,
affiliate, visiting, emeritus and retired roles are separate. A school's
broader published faculty total may use another definition.

All **736 collected entries** have decisions: 383 included and 353 excluded.
Astra independently reviewed the official categories and profiles; those
facts were reconciled before export. The user then amended incoming eligibility;
the original v2 policy and decisions remain archived. Additional official category pages were
checked for omissions, including names missing from the broad directories. This
is coverage against those university sources, not a measured national recall
rate or a guarantee that every university webpage is current.

Cross-checks changed the result:

- Berkeley's official future-start information identifies Qian Xu and
  Carmen Amo Alonso as incoming in 2027. Both are included under the revised
  policy while retaining incoming status. An EE-designated joint CS professor can qualify;
  CS research topics alone do not remove an official EE appointment.
- UT Austin lists Nanshu Lu in its ECE category, but the official appointment is
  courtesy. She is recorded separately from the regular count.
- Georgia Tech's generic titles hide adjunct, practice and emeritus categories.
  Computing and BME profiles establish joint ECE professorships for Frank Li,
  Brendan Saltaformaggio and May Wang. Li and Saltaformaggio retain unexplained
  affiliate job-code discrepancies; the reviewed count concerns academic
  appointments, without asserting payroll status. Separate official retirement
  and departure evidence resolves McLaughlin and Vito as excluded.

Additional-source leads and excluded-category names are retained in
[discovery-leads.json](../data/faculty/discovery-leads.json). The Georgia Tech
research-labs cross-check found two already-recorded ECE adjuncts and two CS
professors without verified regular ECE appointments. It identified no additional
verified regular ECE faculty; missing evidence is not proof that no unlisted
appointment exists.

## The professor record

Each record answers three separate questions:

| Question | Stored information | Evidence |
| --- | --- | --- |
| Who is this person? | Stable ID, official name, variants, profiles, external ID assertions | University profile, linked personal site/CV, ORCID links, exact publications |
| Do they currently belong to EE/ECE? | School, unit, category, current/incoming/past state, decision and date | Official roster, central appointment profile, university announcement |
| Which papers are theirs? | Exact DOI, byline position, printed name, original publication institution | Person-specific publication reference and publisher byline |

Every claim points to its source, observation date and response hash. A name
match does not establish employment. One matched paper does not approve an
entire OpenAlex author profile. Conflicts remain visible. Two pages copying the
same statement are not independent confirmations. Astra's independent review
is a separate check from source independence.

The initial matching experiment accepted 16 individual authorships for nine
people; it is not comprehensive paper coverage. Qian Xu's two links remain
identity evidence, and the incoming appointment is included under v3. The original
matching-pilot eligibility flag records the earlier pilot policy, not today's count.
An identified raw cached paper does not automatically qualify for ranking credit.

## Going school by school

The [queue](../data/faculty/school-queue.json) contains **909 US candidate
institutions**, with the pilots first and remaining candidates ordered by
existing ECE publication activity. Department existence still needs discovery.
Reconcile this list with official national education/program directories before
claiming US coverage; schools absent from our paper data can be missing.

The next proposed batch is MIT, Michigan, Carnegie Mellon, UC San Diego, Purdue,
UCLA, Virginia Tech, USC, Maryland College Park and Caltech. This is collection
order, not a faculty ranking. Apply the same checklist to every school:

1. Establish its official EE/ECE unit and boundary, especially within EECS.
2. Enumerate every roster page and relevant appointment category.
3. Cross-check another official source. Use profiles, announcements, professor
   sites, CVs and bibliographic leads to investigate omissions and conflicts.
4. Decide every inclusion/exclusion with evidence. Hold the count when
   eligibility is unresolved.
5. Reconcile independent review, validate and export the accepted current count.
6. Review changes at the next observation. The initial target is 90 days;
   no automatic schedule has been created.

## Software and validation

Offline collectors produce versioned JSON/CSV evidence and decisions. A small
validated JSON bundle feeds the existing static frontend. There is **no database
or new production service**. Supported school details show a count, observation
date and official source. Publication filters do not change that count.
Historical rosters are deferred; immutable observations are retained now.

Review [roster-review.csv](../data/faculty/roster-review.csv) for the decisions,
[people.json](../data/faculty/people.json) for detailed records, and the
[validation report](../data/faculty/validation.json) for pinned inputs.

Offline frontend checks, targeted faculty/release/field tests, and local packaging
for ECE, Biology and Earth & Space pass. Browser layout QA was skipped because
Playwright is not installed. Sister publication datasets were retained; this
task did not refresh or certify their freshness.

`AGENTS.md` now requires shared changes to be checked across all registered
disciplines and data freshness to be reported separately for each one. An ECE
refresh does not imply that Biology or Earth & Space was refreshed; collection
stays scoped, and each promoted dataset keeps its own verification gates.

Separate pipeline work changed the original matching pilot's publication-cache
checksums. Its original inventory was preserved. A
[scoped recheck](../data/faculty-pilot/2026-11-22/current-authorship-recheck.json)
passes for all 16 accepted authorships, including one changed raw record whose
DOI, byline, author count, ID and institution still agree. This does not
re-certify the changed global corpus. Faculty counts depend on university
appointment evidence and are independent of that corpus audit.

The [roadmap](faculty-vision-roadmap.md) and
[architecture](faculty-software-architecture.md) govern the next milestones.

The reusable refresh workflow is now implemented. Second live observations of
Berkeley and Georgia Tech retained the accepted faculty totals and incoming
dates. Berkeley's two missing baseline profile projections were reconciled
against unchanged official emeritus headings; the prior independent fact audit
was reused with that scope recorded. A real Georgia Tech source timeout was
rejected without changing the accepted roster, followed by a successful retry.
Collection, review, acceptance and export now have separate commands, durable
factual evidence and observation history. These were repeat captures on the
same day; no scheduled automation or historical roster query was added.

USC's initial new-school test collected all 136 ECE directory records and eight
appointment-category sets. The first collector draft
labeled 60 inclusions, 51 exclusions and 25 unresolved secondary/courtesy
appointments. USC explicitly combines those two appointment types in one
category, so a generic joint listing does not establish eligibility under our
policy. A malformed part-time faculty profile link was explicitly corrected to
the working official USC profile while retaining the original link. The school remains
pending with no public count; accepted schools and ranking credit are unchanged.
The collector now preserves POST filter parameters as part of source identity,
checks that USC applied those filters, and saves reviewed pending records without
accepting them. Details are in the USC review CSV under `data/faculty/reviews/`.

Independent review is now an enforced workflow stage. Successful collection
automatically starts a fresh reviewer; acceptance requires its candidate-bound
result and reconciled findings. New schools receive a full audit and refreshes
review all changes plus a seeded sample. Earlier accepted observations retain
their original review provenance; future acceptances require this new gate.

An earlier Astra audit tested the contract on USC: 136 records and nine category
lists returned, with 59 included, 46 excluded and 31 unresolved recommendations.
That audit disagreed with parts of the collector draft. Official
department/announcement pages returned 403 and a profile
returned 404, so its coverage was incomplete. The acceptance command rejected that
candidate; the five accepted schools and public counts stayed unchanged. No USC
headcount is certified. The immutable audit result and execution receipt are
under `data/faculty/audits/`; the configured Codex CLI runner still needs a live
model invocation test, while real T3 review/import and automatic subprocess
execution have been exercised.

The follow-up collection recovered all required sources with zero failures and
explicitly repaired Ioannou's departmental profile link. Detailed CVs and
appointment biographies now support individual primary-review corrections;
the fresh draft and named outstanding cases are in
[`usc-roster-review.csv`](../data/faculty/reviews/usc-roster-review.csv) and
[`usc-remaining-review.csv`](../data/faculty/reviews/usc-remaining-review.csv).
Those files distinguish a primary proposal from independent confirmation.
Current/past/outside-core labels on excluded emeritus appointments no longer
produce false count disputes; stored observations remain unchanged.

Terra's subsequent reviews verified directory filters and made some appointment
decisions but repeatedly stopped before completing the requested adjudication.
These partial results and their provenance are retained, not treated as signoff.
Sonnet, the user's other approved economical option, returned a schema-valid
review claiming complete coverage. Primary evidence checks rejected it: six
inclusions contradict explicit courtesy designations, and 15 claimed core-roster
confirmations refer to people absent from the 60-entry core roster. Its declared
review timestamp also predates the job. The raw result, actual execution receipt,
pinned capture packet and evidenced rejection are preserved without repairing
that timestamp into an apparently fresh signoff. Shared captures remain explicitly
identified as collector-fetched, independently inspected evidence; no independent
download is claimed for them.

The latest primary draft proposes 66 inclusions and 57 exclusions, with 13
appointment-type cases unresolved. Six proposed additional inclusions still need
valid independent confirmation. These are draft labels, not an accepted headcount.
The remaining-case CSV separates missing appointment evidence, unconfirmed
inclusions and rejected courtesy inclusions. The acceptance command rejects the
audit; five accepted schools, public counts and publication credit are unchanged.
