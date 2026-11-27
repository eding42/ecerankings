# Repeated papers, 2026-11-26

One paper stored under two identifiers was counted twice. `aggregate.py` skips
only identical identifiers.

Candidates: same venue and year, same title (25+ characters), same author count
and at least 80% of surnames. An extra copy was excluded only with an identical
title and ordered surnames plus one of these:

- CLEO listed under both Optica and IEEE identifiers (CLEO 2019's `10.23919`
  identifiers that were sampled are not registered at doi.org);
- DAC listed by both IEEE and ACM;
- a one-page IEEE entry beside the full paper, in the same proceedings or journal;
- a second IEEE deposit with no pages, in the same proceedings;
- one DOI resolving to the other in Crossref;
- the same Optica paper number under two CLEO prefixes;
- a copy without a DOI beside the DOI record.

Publisher records came from Crossref. The copy listing the most author schools
was kept; no excluded copy listed more than the kept one. The rules were
spot-checked on samples, not every pair. The excluded copies, each with its
reason and kept copy, are in `data/excluded-works.csv` (`decided_by`
`repeat-check`).

`left-for-review.csv` holds candidates that did not meet the rules, including
every multidisciplinary-journal case: some of those identifiers also appear in
the Biology cache, which shares the exclusion list.

`pipeline/verify_global.py` now reports a venue-year with 20 or more repeats
making up at least 2% of its papers. Only ECE caches were examined.
