---
title: About confref labs
url: /about/
area: about
eyebrow: About
beta: true
lead: The services of confref on its identifiers, in beta.
---

## What is here

- **Landing pages:** one page per conference series and per event, at its identifier on `id.confref.org`, with the
  records of the sources, the proceedings, the ratings and the data in RDF.
- **Search:** series and events by name, acronym, place and year, with filters for academic field, discipline,
  time, series, country and attendance mode.
- **Map:** the events at their places, over time.
- **SPARQL:** all datasets in one endpoint.
- **APIs:** lookup of identifiers, search as JSON, reconciliation for OpenRefine, calendars.
- **Dashboard:** what the loaded data covers and where the sources disagree.

## Beta

The services are new. They can change, move or be unavailable for a while, and their data is loaded from the
current versions of the datasets, which can still contain errors. The identifiers on `id.confref.org` do not
change: an identifier that turns out to stand for two events is split, two identifiers for one event are merged,
and the old identifiers keep resolving.

## labs and www

- **www.confref.org** is the project site: the datasets with their dumps and descriptions, the identifiers, the
  history of the project, news.
- **labs.confref.org** holds the services on the data. Its pages have the dark header with the "labs" mark.
- **id.confref.org** is where the identifiers resolve; its landing pages belong to the labs.

## Where the data comes from

The labs load the stable versions of the datasets of
[confref-data](https://github.com/confref/confref-data): the identifier set `ids`, made from the records of
Springer LOD, the confref portal, ConfIDent, dblp, Wikidata and the GND, joined by linksets; the places of the
events and their academic fields, matched to Wikidata and the OECD classification of fields of science; the ratings
Springer published for its series. Each dataset is described on [www.confref.org](https://www.confref.org/datasets/).

## Source code

The platform: [confref-platform](https://github.com/confref/confref-platform). Problems and suggestions: its
[issues](https://github.com/confref/confref-platform/issues).
