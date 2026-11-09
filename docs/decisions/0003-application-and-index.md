# 0003 One application; an index in SQLite made from the store after each load

Status: accepted · Date: 2026-11-09

## Context

The landing pages need the facts of an identifier and of the records, proceedings, places and ratings around it;
the search needs full text and filters with counts; the APIs need lookups by many kinds of keys. Asking Fuseki for
each page costs several queries per request, and a search engine (Solr) is one more service on the VM. The data is
small: 89,369 identifiers, 170,042 records.

## Decision

- **One application** (`apps/graph`, Python standard library, one container on 127.0.0.1:8090) answers the
  documents of id.confref.org and, on labs.confref.org, the search, the APIs, the reconciliation service, the
  calendars and the dashboard. nginx puts the kit into its pages (SSI).
- **An index in SQLite**, made by a job after each load (`jobs.py index`, about one minute) from the same files of
  the store that Fuseki loads: one row per identifier with its facts and a JSON document for its page; tables for the
  filters; a full-text index (FTS5) of names, acronyms with and without the year, places and series; the lookup keys;
  the triples of every IRI we coin (compressed), for the RDF documents; labels. The new index replaces the old one
  in one step; the application opens it at the next request.
- **Fuseki** serves SPARQL only. The application does not depend on it.

## Consequences

Pages and searches answer in milliseconds without Fuseki. What the index does not hold (records of the sources under
their own IRIs, e.g. dblp or Wikidata) is shown as links to the sources and is available in SPARQL.
