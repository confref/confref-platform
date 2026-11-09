---
title: APIs
url: /api/
area: api
eyebrow: APIs
beta: true
lead: Read-only interfaces to the confref identifiers. Answers are JSON with CORS, unless stated otherwise. The interfaces are in beta and can change.
---

## Identifiers and their data {#identifiers}

Every identifier resolves on `id.confref.org`. The identifier itself stands for the series or event; a request for it
answers `303 See Other` with the address of a document about it, chosen by the `Accept` header.

| Accept | Document |
|---|---|
| `text/html` (browsers) | `https://id.confref.org/event/<id>.html`, the landing page |
| `text/turtle` | `….ttl` |
| `application/ld+json` | `….jsonld` |
| `application/n-triples` | `….nt` |
| `application/rdf+xml` | `….rdf` |

```
curl -L -H "Accept: text/turtle" https://id.confref.org/series/s10ajew
```

The same holds for the records we coin (`data/…`), the terms of the ontology (`ontology/<term>`) and the datasets
(`datasets/<slug>`; HTML is their page in the catalogue). A merged identifier answers `301` with the identifier it
was merged into, a split one `300` with its parts, a retired one `410`.

## Lookup {#lookup}

`GET /api/lookup?id=<identifier>` finds the confref identifiers for an identifier of a source or of the proceedings:

- dblp: `conf/semweb/iswc2020`, `https://dblp.org/db/conf/semweb/iswc2020`, a venue `conf/semweb`, a publication
  `https://dblp.org/rec/conf/semweb/2020-1`
- Wikidata: `Q108265748` or the item's IRI
- GND: `https://d-nb.info/gnd/…` or `gnd:…`
- ConfIDent and the confref portal: the page URL or our record IRI
- Springer LOD: `http://lod.springer.com/data/conference/…`
- proceedings: DOI (`10.1007/…`), ISBN
- a former confref identifier (merged ones lead to their successor)

```
curl "https://labs.confref.org/api/lookup?id=10.1007/978-3-030-62419-4"
```

`GET /api/resolve?id=<identifier>` answers `303` with the confref identifier when there is exactly one, `300` with the
list when there are several, `404` when there is none.

## Search {#search}

`GET /api/search` takes the parameters of the [search](/search/) and gives its results as JSON, 25 per page:
`q` (text), `kind` (`event`, `series`), `field` (OECD codes `1` or `1.2`, repeatable), `discipline` (Wikidata QID,
repeatable), `series` (confref identifier), `country` (ISO code), `mode` (`OnlineEventAttendanceMode`, …),
`from`, `to` (years), `sort` (`relevance`, `newest`, `oldest`, `name`), `page`.

```
curl "https://labs.confref.org/api/search?q=semantic+web&field=1.2&from=2015&to=2019"
```

`GET /api/entity/<id>` gives the facts of one series or event: names, dates, place, series, fields and disciplines,
sources, proceedings, ratings.

## Reconciliation (OpenRefine) {#reconcile}

`https://labs.confref.org/reconcile` is a reconciliation service (version 0.2 of the API of the W3C Entity
Reconciliation Community Group). In OpenRefine: on a column with conference names, *Reconcile* → *Start
reconciling* → *Add standard service*, then the address above. Types: `event` and `series`. Properties that improve
the scores: `year`, `country` (ISO code), `acronym`. A name with a year ("ISWC 2020") is matched against events of
that year. The service also offers suggestions and a preview.

## Calendars {#feeds}

Coming events as iCalendar, for calendar programs:

- all: `https://labs.confref.org/feeds/upcoming.ics`
- a series: `https://labs.confref.org/feeds/series/<id>.ics`
- an academic field: `https://labs.confref.org/feeds/field/<code>.ics` (e.g. `1.2`)

Coming events are those with a start date from today; most come from ConfIDent.

## SPARQL {#sparql}

`https://labs.confref.org/sparql` (GET or POST, the SPARQL 1.1 protocol), with an [editor](/sparql/). Queries stop
after 120 seconds; at most 5 requests per second per address.

## Status {#status}

`GET /status.json`: the versions loaded and the figures of the [dashboard](/dashboard/).
