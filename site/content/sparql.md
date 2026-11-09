---
title: SPARQL
url: /sparql/
layout: sparql
area: sparql
description: Query the confref datasets with SPARQL.
example: |
  PREFIX cr: <https://id.confref.org/ontology/>
  PREFIX schema: <http://schema.org/>
  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

  # the events of a series, with year and place
  SELECT ?event ?year ?name ?place WHERE {
    ?series a cr:Series ; rdfs:label "International Semantic Web Conference" .
    ?event cr:inSeries ?series ; rdfs:label ?name .
    OPTIONAL { ?event cr:year ?year }
    OPTIONAL { ?event schema:location ?p . ?p rdfs:label ?place . FILTER(LANG(?place) = "en") }
  }
  ORDER BY DESC(?year)
---
