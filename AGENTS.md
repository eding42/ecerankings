# ECERankings.org — Agent Guide

Static, OpenAlex/Crossref-based research rankings with a Python data pipeline.

## Start here

- Read [docs/methodology.md](docs/methodology.md) before substantive work. Change ranking methodology, area taxonomy, or venue-inclusion policy only with explicit user approval.
- This file is canonical. `CLAUDE.md` is an `@AGENTS.md` import; edit this file instead.
- Use existing planning documents for scope/design changes; keep routine progress in chat.
- When editing skills, synchronize the physical copies under `.agents/skills/`, `.gemini/skills/`, and `.claude/skills/`.

## Working rules

- **Never commit or push without explicit confirmation.** Stage specific paths; never `git add .` or `git add -A`. Permission to push is for a feature/fix branch or PR, not production deployment.
- Never commit `.env`, `.tmp/`, `data/institutions.json` (the local index), or local settings. Read `OPENALEX_API_KEY` from the ignored root `.env`; never log keys or expose them in public assets.
- Core pipeline Python uses the standard library. `.venv/` is for optional semantic tools. Keep the static frontend free of runtime dependencies.
- `.tmp/` is scratch space; permanent fixes, scripts, and release candidates belong outside it.
- **`main` is the live site, and merging to it deploys** (`.github/workflows/deploy.yml`), so merge approval is deploy approval. Deploy only from an up-to-date, clean `main`, never from a feature branch or worktree. The manual fallback uses Wrangler as in [the runbook](docs/refresh-runbook.md), not `cf`.
- **Always check whether the remote has moved.** Several agents work in parallel and may merge to `main` at any time. Fetch before starting a task, before reporting findings or numbers, and before pushing; check `git rev-list --left-right --count origin/main...HEAD`. Your starting branch and local `main` may be stale: start new work from `origin/main`, and check claims about the public site against the live site. An accepted release lands on `main` through an approved PR; never leave it only on a feature branch.
- **A clean text merge is not proof.** Before opening a PR, rebuild the branch on current `origin/main`, then run what CI runs (the commands in `.github/workflows/check.yml`) from a clean checkout of the committed files, so files left only in your working tree cannot hide a failure. A required check on the PR re-tests it merged with the latest `main`.

## Disciplines and shared code

- [data/fields.json](data/fields.json) and [pipeline/fields.py](pipeline/fields.py) define field paths, capabilities, and credit types. Always pass `--field <ece|biology|earth-space>` to `aggregate.py`, `split.py`, `verify.py`, and `package_site.py`.
- Shared frontend logic belongs in `site/core/`. Discipline sites use thin entrypoints and palette overrides; never copy core implementations into sister sites.
- Keep registries and outputs field-specific. ECE and Earth & Space use `cache/`; Biology uses `cache_biosciences/`.
- Check shared changes against all affected fields, including their configurations; report results, untested cases, and intentional exceptions.
- Keep collection scoped. Refresh/release reports must identify every field as refreshed, retained, or unassessed. For assessed fields, report source/build dates, verified complete year, missing/partial venue-years, and verification status. A new build is not a data refresh.
- Apply verification and provenance gates separately to every promoted dataset. Structural packaging checks alone establish neither data integrity nor freshness.

## Methodology and data quality

- Preserve institution-level, publication-time credit: each paper contributes `1/N` per author to that author's listed institutions. Score uses the geometric mean of `1 + area credit`, including zero-scoring selected areas. Read area defaults from the registry.
- Follow [the refresh runbook](docs/refresh-runbook.md) for staged builds, validation, promotion, and releases. Published data changes only through `build_release.py` then `promote_release.py`; never rebuild directly into public ranking data or bypass checksum/hash gates. After an ECE release, run `node pipeline/prerender_site.mjs` and commit its output (CI fails when the prerendered pages are stale). See [README.md](README.md) for repository orientation and [the ML guide](docs/ml-pipeline.md) for publisher/PDF workflows.
- Neither curated affiliation mappings nor OpenAlex resolutions are ground truth. Adjudicate disagreements with evidence; run affiliation trap checks before and after mapping changes. Native institution resolutions can bypass the curated map, so verify both paths.
- Institution merges require matching name **and country**. Check campus, acronym, and company/city collisions. Preserve curated non-research exclusions and known-strong verification tripwires.

## Faculty context

- Follow [the counting policy](data/faculty/policy.json) and [school queue](data/faculty/school-queue.json). Count **ECE-affiliated faculty**, including official affiliated/below-the-line, courtesy and joint/secondary professorial EE/ECE appointments, with an explicit EE boundary in combined departments. CS-only contributors without an official EE/ECE affiliation, generic lab affiliates and other excluded roles remain excluded; preserve exact appointment categories without guessing subtypes.
- Include announced incoming professors in eligible categories, preserving incoming status, start dates, and subtotals. Keep stable identities, claim-level evidence, conflicts, and dated decisions; publication topics alone do not establish membership. Earlier narrower counts require broader-source coverage review before export under the new policy.
- `faculty_refresh.py observe` starts a separate agent audit; reconcile its recorded result before acceptance or `faculty_registry.py export`. Unresolved coverage is not zero. Counts stay fixed across publication filters and do not change ranking credit.
- Scope and implementation status live in the existing [roadmap](docs/faculty-vision-roadmap.md) and [architecture](docs/faculty-software-architecture.md). Historical roster queries are deferred; preserve observations without inferring employment intervals from capture dates.

## Specialized workflows

Read the relevant skill before starting; use its detailed procedures and gates.

| Task | Skill |
| --- | --- |
| Add/reverify a venue or area; establish source coverage | [collect-venue-data](.agents/skills/collect-venue-data/SKILL.md) |
| Resolve new or ambiguous affiliation strings | [adjudicate-affiliations](.agents/skills/adjudicate-affiliations/SKILL.md) |
| Verify after harvest, backfill, normalization, adjudication, aggregation, or before promotion; include seeded audits | [verify-data](.agents/skills/verify-data/SKILL.md) |
| Check PDF affiliations against rendered pages | [verify-pdf-affiliations](.agents/skills/verify-pdf-affiliations/SKILL.md) |
| Refresh, rebuild, validate, promote, or publish data | [refresh-data](.agents/skills/refresh-data/SKILL.md) |
| Write/review interface copy | [clean-copy](.agents/skills/clean-copy/SKILL.md) |
| Audit implicit state machines and async state | [find-implicit-state-machines](.agents/skills/find-implicit-state-machines/SKILL.md) |
