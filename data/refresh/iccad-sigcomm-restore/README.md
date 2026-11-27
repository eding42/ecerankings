# ICCAD 2006–2012, ICCAD 2016 and SIGCOMM 2015

These nine editions were missing or nearly empty in `cache/`. Prepared 2026-11-26.

## Membership

The CSV files here list each edition's papers as matched to the proceedings
contents list (SIGCOMM 2015: the official program). Embedded tutorials, front
matter, posters and demos are left out. Numbered contest-session papers in
ICCAD 2011 and 2012 are included. All 1,037 DOIs were found on Crossref under
the expected proceedings, with matching titles and author counts. Four ICCAD
2009 papers have no DOI. The contents lists were not fetched again on
2026-11-26.

The new rows replace the earlier rows for 2006–2012, which included unrelated
papers.

## Affiliations

The author list is Crossref's (for the four DOI-less papers, the earlier
publisher record). OpenAlex affiliations were added only when both author lists
had the same length and every position had a compatible name. Existing
affiliation text was kept. Twenty-seven ICCAD 2006 papers were found under
their ACM co-publication DOI (`10.1145/1233501.*`) by title; each such row
records it in `openalex_enrichment.alias_doi`.

One correction: three ICCAD 2009 authors whose only affiliation is "Ansoft LLC,
Burlington, MA" had been matched to the University of Vermont. The match was
removed (`affiliation_correction` on that row).

A harvest rerun that finds a valid cached edition keeps it. A forced re-harvest
writes Crossref records only, so the OpenAlex affiliations would need to be
added again.

## ICCAD 2005

The edition keeps the 147 rows under the 2005 DOI prefix that have authors,
unchanged from before. Removed: 46 rows without authors, six 1993 records, and
seven rows without a 2005 IEEE DOI (unrelated records and one ACM Digital Library
copy of a paper already among the 147). This list was not checked against a
contents list.

