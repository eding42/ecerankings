# Methodology

How ECERankings and its sister rankings (Biology, Earth & Space) count research,
and why. Changing anything here needs the maintainer's explicit approval.
Venues and area defaults live in the registries (`data/areas.json`,
`data/areas_biosciences.json`, `data/areas_earth_space.json`); how to run a
release is in [refresh-runbook.md](refresh-runbook.md).

## Counting

- **Adjusted count.** Each paper is worth 1.0, split evenly across its N authors.
  An author's share goes to the institutions they listed on that paper, split
  evenly if there are several. Each institution counts once per author.
- **Score.** Geometric mean across the *selected* areas,
  `(∏(1 + count_i))^(1/n) − 1`. Areas with zero papers still count toward `n`,
  which rewards breadth and resists single-area dominance.
- **No citations.** Publication counts at selective venues only.
- **Whole institutions**, not departments or faculty rosters. OpenAlex
  institutions are used as reported, with no rollup to a parent. Duplicate IDs
  are folded through `data/institution-aliases.csv` only when name and country
  both match.
- **Credited institution types** are set per field in `data/fields.json`:
  education only for ECE and Biology; education, facility, government and
  nonprofit for Earth & Space, where national labs and observatories do much of
  the research.
- **Default window** 2016–2025. Earlier years are cached for history views.
- **Non-research items** (editorials, news, commentary, prefaces, tributes,
  translated abstracts) are excluded by type and by `data/excluded-works.csv`.
  This matters because a single-author item earns a full 1.0.

## Attribution at time of publication

Each paper is credited to the institutions its authors listed **on that paper**.
This measures output realized under an institution's banner when it happened.
CSRankings instead credits a person's whole career to their current institution,
which measures the current roster. Neither is more correct; we publish the
first. A "current faculty" mode (OpenAlex `last_known_institutions`, filtered
for one-year stints) is a possible later toggle. Current author profiles never
supply historical credit.

## Affiliation credit rules

Native OpenAlex institutions on an authorship take precedence; the curated
`data/affiliation-map.csv` is consulted only when they are empty. Map decisions
follow the maintainer's rulings (details in the runbook):

- A university's own hospital or medical centre credits the university; an
  independent medical centre credits nobody.
- A joint institute naming two or more universities credits all of them,
  splitting the author's share evenly. A degree-granting constituent named
  beside its parent (Télécom Paris with IP Paris) is joint as well.
- A lab, department or company named beside a university credits only the
  universities the string names.
- A university system named beside a member credits the member.

The map is not ground truth. Every decision goes through `pipeline/adjudication.py`
with evidence, and `data/adjudication-traps.csv` guards past mistakes.

## Venue inclusion

A venue joins an area only if it passes both tests:

1. **Selectivity**: among the hardest places to publish in that subfield.
2. **Scope**: roughly 80% or more of its content is within the area. Scoping is
   by venue choice, never per-paper topic classification, so every counted
   paper can be checked.

Consequences:

- **Field-scoped Nature journals** (Nature Electronics, Nature Photonics, Light)
  sit in their subfield areas.
- **Multidisciplinary journals** (Nature, Science, PNAS, Nature Communications)
  are mostly outside ECE and would rank schools by biomedical output, so in ECE
  they live only in the off-by-default Flagship area. Biology and Earth & Space
  count only their in-field sections.
- **Review-only journals are not venues.** Invited reviews reward existing
  reputation rather than new research. Biology excludes Nature Reviews and
  Annual Reviews; Earth & Space dropped Annual Review of Earth & Planetary
  Sciences and Earth-Science Reviews on 2026-11-24. Journals named "Reviews"
  that mainly publish original research (Quaternary Science Reviews) or mission
  instrument papers (Space Science Reviews) stay.
- **Within-area balance**: venues in one area should have comparable volume and
  selectivity. A high-volume workhorse journal next to selective flagships
  belongs in a toggleable second tier rather than dominating.
- **Defaults**: every ECE area is on by default except Flagship. Machine
  Learning has been on since 2026-11-24.

## Data sources

- **OpenAlex** supplies works and paper-specific affiliations. It covers
  IEEE/Optica venues well, unlike DBLP, which is weak on core-EE journals.
- **Crossref** supplies exact conference-edition membership by DOI prefix where
  OpenAlex leaves proceedings without a source or lags; OpenAlex affiliations are
  then joined by DOI. Rule: use OpenAlex where a year has a real source,
  otherwise Crossref.
- **Publisher proceedings and OpenReview** supply ML conference membership, with
  PDF author blocks as the affiliation fallback ([ml-pipeline.md](ml-pipeline.md)).
- **Rejected: the IEEE Xplore API.** Its terms forbid bulk storage,
  redistribution and bulk display, which a cached, published static site needs.

## Open questions

- **ML venue status**: NeurIPS, ICML and ICLR count by default but stay
  `candidate` until their data covers the full year range (ICLR 2016, for
  example, has no affiliations). Maintainer decision, 2026-11-24.
- **Current-faculty attribution mode**: designed above, not built.
- **Second-tier venues**: no tiering yet.
- **Corrections intake**: no public submission path.
- **Biology clinical medicine** (JAMA, Lancet, NEJM families): deferred; see
  [biologyrankings-roadmap.md](biologyrankings-roadmap.md).
