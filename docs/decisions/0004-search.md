# 0004 The search: the identifiers by default, filters for field, discipline, time, series

Status: accepted · Date: 2026-11-09

## Decision

- The search (`/search/`, as JSON `/api/search`) finds the series and events of the identifier set, by default
  both; each result leads to its landing page.
- Text: every word must occur (the last one as a prefix) in the names, the acronyms (also with the year, "ISWC 2020",
  "ISWC2020"), the place and country, the series and the year; ranked by BM25 with names and acronyms weighted most.
  Without text the newest first.
- Filters with counts: kind, years (from, to, decades), academic field (the 6 major and 42 OECD fields), discipline
  (Wikidata items), country, series, attendance mode. A filter of a series also finds the series itself.

## Consequences

Names that only a source has (not the name `ids` chose) are not searched yet; `ids` names one name and up to three
acronyms per identifier. The records of the sources are found through the lookup API, not through the search.
