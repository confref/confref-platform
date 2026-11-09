# 0001 One VM for labs.confref.org and id.confref.org

Status: accepted · Date: 2026-11-09 · Builds on confref-data decisions 0002, 0007, 0014

## Context

confref-data 0002 and 0007 plan a second VM besides the project website: SPARQL, the landing pages of the
identifiers, showcases. Kai asked on 2026-11-09 for full dereferencing of id.confref.org, a search that defaults to
the landing pages, a map, lookup and reconciliation APIs, calendars and a dashboard, all in beta and in the design of
the project site, but recognisably not the project site.

## Decision

- **One VM** (Ubuntu LTS, 4 cores, 16 GB RAM, 32 GB system disk, 100 GB data disk for `/data`), set up from this repository (`host/install.sh`); a local Lima VM
  (`host/local-vm.yaml`) for tests. nginx is the only public entry; the services listen on 127.0.0.1.
- **Hosts:** `labs.confref.org` (the labs site, the map, SPARQL, the application) and `id.confref.org` (every path
  to the application, which resolves the IRIs: [0002](0002-dereferencing.md)).
- **Services:** Fuseki 6.2.0, read-only, loaded from the data index of confref-data (`services/load.sh`); one
  application in Python with the standard library (`apps/graph`, [0003](0003-application-and-index.md)); the labs
  site in Hugo (`site/`); showcases in repositories of their own, the first the map (`confref-map`).
- **Data:** the stable versions of the datasets, from the dumps location of the data index (archive.confref.org).
  All datasets are loaded into Fuseki unless `LOAD_SKIP` names some. Measured on the test VM on bee (2026-11-09): 6.9
  million triples, a database of 2.5 GB (3.9 GB before compacting), Fuseki using 0.7 GB of memory, the index of the
  application 0.4 GB, everything on the VM 7 GB of disk.
- **Loads on bee:** new data is loaded and checked on a test VM on bee (`host/bee-vm.yaml`) and its state copied to the
  VM, as for the other platform of kg-commons.

## Consequences

The project website stays on its own host (confref-data 0015). Moving the resolution of the identifiers to another
operator means moving the host id.confref.org with the application and its index.
