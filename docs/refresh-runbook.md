# Refresh and publish

Use Python 3.11+, Git LFS, a materialized source cache, and the OpenAlex key in
the ignored root `.env`. Methodology and venue decisions belong in `docs/methodology.md`
and the venue registries; a refresh does not change them.

All three fields release the same way. Every release command takes
`--field ece|biology|earth-space` (default `ece`) and reads the field's
registry, cache, credited institution types and site data directory from
`data/fields.json`:

| Field | Registry | Cache | Site data |
|---|---|---|---|
| `ece` | `data/areas.json` | `cache/` | `site/data/` |
| `earth-space` | `data/areas_earth_space.json` | `cache/` (shared with ECE) | `site/earth-space/data/` |
| `biology` | `data/areas_biosciences.json` | `cache_biosciences/` (not in Git) | `site/biology/data/` |

Below, `<field>`, `<cache>` and `<site-data>` stand for one row of this table.

## Authorization

| Request | Authorized work |
|---|---|
| Refresh data / prepare a release | Collect, build, verify, report |
| Push the refresh | Commit to a review branch, push, open a PR |
| Merge / deploy | Merge the approved change or publish the accepted release |

Stage explicit paths and present the change before committing. Push requires
its own confirmation. Never infer production publication from a review-branch push.

## 1. Prepare and collect

```sh
git lfs install
git lfs pull --include='cache/**,site/data/author-info.csv'
python3 pipeline/verify.py --all
```

Save the verification output as the baseline. Do not harvest over LFS pointers.
Use staged collectors with explicit scope and request limits:

```sh
python3 pipeline/refresh_openalex.py --venue jssc --year-range 2025 2025 --dry-run
python3 pipeline/refresh_openalex.py --venue jssc --year-range 2025 2025 \
  --out-cache .tmp/refresh/journals/cache --manifest .tmp/refresh/journals.json \
  --max-list-requests 100 --refresh
python3 pipeline/refresh_conferences.py --venue iedm --years 2024 2025 \
  --output .tmp/refresh/conferences/cache --report .tmp/refresh/conferences.json
```

The journal tool clips years to `data/source-first-years.json`. Conference
membership must match the registered edition source and DOI scope. Reuse
completed outputs only when their recorded hashes match. Failed requests stay
unresolved, not empty observations. For ML, follow [ml-pipeline.md](ml-pipeline.md).

Backfill or normalize only the intended cache tree. Use the stdlib normalizer
by default; the semantic normalizer is optional and should run separately.
Adjudicate new raw strings, replay prior decisions after normalization, and run
`pipeline/adjudication.py check`. Do not accept author-profile affiliations.

Affiliation credit policy (user rulings, 2026-11-23):
- A university's own hospital or medical centre credits the university; an
  independent medical centre with no university named credits nobody.
- A string naming one university credits that university; companies, hospitals
  and non-university bodies named beside it are ignored.
- A string naming two or more universities (a joint institute) is a `joint`
  decision with `institution_ids`. The map row gets status `joint`, with the
  members joined by `|` in `institution_id` and ` | ` in `institution_name`.
  `aggregate.py` splits the author's `1/N` share evenly across them. Native
  OpenAlex institutions on an authorship still take precedence over the map.
- A constituent establishment that grants degrees under its own name, named
  beside its parent university or federation (Télécom Paris with Institut
  Polytechnique de Paris, Grenoble INP with Université Grenoble Alpes,
  Instituto Superior Técnico with the University of Lisbon), is `joint` too:
  native OpenAlex lists both on such authorships and `aggregate.py` does not
  roll lineage up, so splitting keeps the map and native paths consistent. A
  string naming only one of them credits only that one. A department, faculty,
  college, lab or research institute inside a university (Courant Institute,
  Gatsby Unit) is not a second institution: credit the university. (Agent
  default, 2026-11-24; veto by asking for parent-only or school-only credit.)
- A company, investor or lab named beside one university does not make a
  joint row: "MIT & Sequoia Capital" credits MIT, and "MIT-IBM Watson AI Lab"
  credits MIT (this supersedes the 2026-11-19 trap that kept it uncredited).
- A university system or federation named beside a member (CUNY, University of
  California, Université de Lyon, Université de Toulouse, HESAM, Paris-Est Sup)
  credits the member only; named alone, it credits the system's own record.
- A CUHK unit placed in Shenzhen (School of Data Science, School of Science and
  Engineering, SRIBD, AIRS, FNii, "(Shenzhen)") credits CUHK-Shenzhen; CUHK's
  own Shenzhen Research Institute credits CUHK. (Agent defaults, 2026-11-24.)

## 2. Build an isolated candidate

`prepare_refresh.py` can combine complete collector outputs with an immutable
baseline. Supply `--baseline`, `--out`, `--report`, and the matching
`--journal-cache`/`--journal-manifest`, `--conference-cache`/`--conference-manifest`,
and optional `--ml-cache`/`--ml-manifest` paths. It retains unresolved scope and
quarantine evidence. Its output becomes the candidate cache below.

```sh
python3 pipeline/refresh_manifest.py --cache-dir <candidate-cache> --out .tmp/refresh.json
python3 pipeline/build_release.py --field <field> --cache-dir <candidate-cache> \
  --refresh-manifest .tmp/refresh.json --out .tmp/release-<field>
```

The builder checks source hashes, rejects writes into the field's site data,
aggregates, splits, writes `institutions.json` (name, country, and the type each
institution was credited under), reconciles credit across the CSV and JSON
artifacts, and records code, input and artifact hashes in `manifest.json`.
Biology's aggregator also produces all-institution tables; the release keeps the
education-only tables the site ranks. Direct aggregation must always be
followed by splitting.

## 3. Verify before promotion

```sh
cp <site-data>/.coverage-snapshot.json <site-data>/.ranking-snapshot.json .tmp/release-<field>/
python3 pipeline/verify.py --field <field> --all --cache-dir <candidate-cache> \
  --data-dir .tmp/release-<field>
python3 pipeline/compare_aggregates.py --reference <site-data> --candidate .tmp/release-<field> \
  --report .tmp/release-diff-<field>.json
```

Copy the snapshots only where the field has them (ECE today).

Review finding changes against the baseline and explain intended credit changes.
Stop for unexplained critical/high findings, regressions, dropped publisher
membership, duplicate keys, inconsistent artifact counts, or hash mismatches.
Also stop when coverage drops more than five points, a known-strong institution
reaches zero, or default-on top-20 membership changes by more than 10% without
a documented cause. Missing source metadata is not evidence of zero papers.

Do not edit `known-strong.json`, methodology, area defaults, or gate thresholds
to clear a failure. Never advance snapshots to hide findings. Accept snapshots
with `--update-snapshots` only after the candidate has been reviewed and the
verifier reports no critical/high findings.

## 4. Promote, commit, and publish

After validation passes:

```sh
python3 pipeline/promote_release.py --field <field> --cache-dir <candidate-cache> \
  --release .tmp/release-<field> --check-only
python3 pipeline/promote_release.py --field <field> --cache-dir <candidate-cache> \
  --release .tmp/release-<field>
```

Promotion refuses a candidate built for another field, checks all source, input
and artifact hashes again, copies the candidate cache into the field's cache
(through Git LFS where it is tracked), removes data JSON for venues or areas the
release no longer has, and writes the release manifest last. Copy accepted coverage/ranking snapshots from the candidate to
`site/data` separately; they are not promotion artifacts. Keep the previous
release until verification and publication finish.

With commit approval, create a review branch and stage only reviewed paths:

```sh
git switch -c data/refresh-YYYY-MM-DD
git add data/areas.json data/affiliation-map.csv data/excluded-works.csv \
  data/institution-aliases.csv cache site/data site/index.html site/institution site/sitemap.xml
```

For a sister field, stage its registry and `<site-data>` instead of the ECE
paths. Biology's raw cache is not in Git, so a Biology release can only be
rebuilt on a machine that holds `cache_biosciences/`.

Never use `git add -A`. Exclude `.env`, `.tmp/`, `ai_temp/`, local settings,
`data/institutions.json`, and generated dependency/build directories. State the
scope, unresolved editions, coverage/credit deltas, and validation results in
the PR. Commit, push, and merge only at their authorized levels.

For an approved Cloudflare publication, package the accepted public files and
deploy with Wrangler. The repo has no Wrangler config file; Wrangler is still
the maintainer's chosen deploy tool, so do not substitute the `cf` CLI.


```sh
node pipeline/prerender_site.mjs
python3 pipeline/package_site.py --out dist
npx wrangler pages deploy dist --project-name ecerankings --branch main
```

`prerender_site.mjs` writes the default ranking into `site/index.html`, one page per
ranked institution under `site/institution/`, and `site/sitemap.xml`; commit the
result with the data. The packager refuses an `index.html` built from other data.
Only ECE is prerendered. The ECE package includes the `biology/` and
`earth-space/` sites. For every field the packager requires a passing release
manifest whose hashes match each published data file, publishes the same data
layout (registry, institutions, manifest, per-area and per-venue JSON), excludes
CSVs, raw cache data and LFS pointers, and enforces the 25 MiB asset limit.
`package_site.py --field biology|earth-space` packages one sister site alone. Code-only publications still need a valid existing dataset. A Git-connected
Pages project may deploy on a `main` push; confirm that configuration before pushing.
Rollback with the previous Pages deployment or a reviewed Git revert. Do not
publish a partially promoted tree or rewrite provenance hashes to make it pass.
