# 0002 id.confref.org: Cool URIs with 303 redirects

Status: accepted · Date: 2026-11-09 · Builds on confref-data decisions 0002, 0005, 0014

## Context

The identifiers stand for series and events, not for web pages. Kai asked for linked data dereferencing with 303
redirects (2026-11-09).

## Decision

- **Resources and documents:** an IRI of a series, event, record (`data/…`), ontology term or dataset is a
  resource. A request for it answers `303 See Other` with a document about it, chosen by the `Accept` header (q
  values; HTML first among equals and for `*/*`): `<IRI>.html` (landing page or record view), `.ttl`, `.jsonld`,
  `.nt`, `.rdf`. Answers carry `Vary: Accept`. A document answers `200`; RDF documents hold the triples whose
  subject is the resource and name it in a `Link: <…>; rel="describes"` header.
- **History of identifiers** (confref-data 0005): a merged identifier answers `301` with the identifier it was merged
  into (for documents: the document of the same format); a split one `300 Multiple Choices` with its parts; a retired
  one `410 Gone` with its history.
- **Datasets** (`datasets/<slug>`, versions, metadata graphs): HTML is their page in the catalogue on www.confref.org
  (303); RDF comes from their `-meta` graphs. The concepts of the dataset vocabulary (`datasets/vocabulary/…`, the
  dataset `confref-vocabulary`) are shown on the platform like records. **Files** (`dumps/<slug>/<version>/<path>`)
  answer `302` with their address on the dumps location. **The ontology** (`ontology/`): HTML is its page on
  www.confref.org (`/ontology/`, 303), RDF `ontology/index.<suffix>`; its terms go to `ontology/<term>.<suffix>`,
  and the HTML of a term links its section on that page (`/ontology/#<term>`). The ontology is read from the stable
  version of the dataset `confref-ontology`. **`/`** goes to the page about the identifiers on www.confref.org.
- The same paths are answered on labs.confref.org; the pages name the address on id.confref.org as canonical.

## Consequences

`curl -L -H "Accept: text/turtle" https://id.confref.org/event/<id>` gives the data of an event; browsers see its
landing page. Lookup by identifiers of other sources is an API of the labs ([0005](0005-apis.md)).
