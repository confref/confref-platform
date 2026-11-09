# confref-platform

The platform of confref on one VM: **labs.confref.org** (search, map, SPARQL, APIs, dashboard, all in beta) and
**id.confref.org** (the resolution of the confref identifiers, with 303 redirects to their landing pages and data).
The data is the stable versions of the datasets of [confref-data](https://github.com/confref/confref-data); the
project website is [confref-site](https://github.com/confref/confref-site) (www.confref.org). Decisions:
[docs/decisions](docs/decisions/).

| Path | What |
|---|---|
| `apps/graph/` | the application (Python, standard library): `app.py` (routes), `resolve.py` (id.confref.org), `pages.py` (landing pages, records), `search.py`, `api.py` (lookup, reconciliation, calendars), `dashboard.py`, `index.py` (the SQLite index, made by `jobs.py index`), `rdf.py` (copied from confref-data) |
| `site/` | the labs site (Hugo) and the kit (`/kit/1/`: header, footer, stylesheet) that nginx puts into every page; `site/build.sh` |
| `services/` | `compose.yml` (Fuseki, the application), `load.sh` (a new Fuseki database from the data index, then `jobs.sh`), `jobs.sh` (the index, the map), `fuseki/` (image, read-only configuration, loader) |
| `host/` | `install.sh` (a fresh Ubuntu VM), `nginx/confref-labs.conf` (both hosts), `local-vm.yaml` (Lima), `deploy.sh` (the site) |

## Setting up a VM

1. On the VM: clone this repository and [confref-map](https://github.com/confref/confref-map) into `/data/confref/src/`;
   `sudo host/install.sh` (`TLS=self-signed` on a test VM). DNS of labs.confref.org and id.confref.org must point to
   the VM before Let's Encrypt can issue the certificate.
2. `services/load.sh`: downloads the files of the stable versions into `/data/confref/store`, builds and checks a
   Fuseki database, switches the endpoint to it, then `services/jobs.sh` (the index of the application, the map).
3. From a checkout: `host/deploy.sh <ssh host>` builds the labs site and copies it.

A local test VM: `limactl start --name=confref host/local-vm.yaml`, then in the VM steps 1 and 2 with
`CR_ID_BASE=https://localhost` and `CR_LABS_BASE=https://localhost` in `services/.env`, and
`host/deploy.sh lima-confref https://localhost/`.

## Without a VM

The application and the site run on a Mac against a local store:

```
cd apps/graph
CR_STORE=~/lokal/confref/store CR_CATALOG=../../../confref-data/catalog python3 index.py /tmp/confref.sqlite
site/build.sh http://localhost:8091/
CR_DB=/tmp/confref.sqlite CR_PORT=8091 CR_ID_BASE=http://localhost:8091 CR_LABS_BASE=http://localhost:8091 \
  CR_KIT_DIR=../../site/public/kit CR_SITE_DIR=../../site/public python3 app.py
python3 ../../../confref-map/build.py /tmp/confref.sqlite ../../site/public/map
```

`CR_CATALOG` takes the stable versions from a confref-data checkout (also those not yet published); without it, the
data index on GitHub. `CR_KIT_DIR` and `CR_SITE_DIR` let the application do what nginx does on the VM.

## Licence

Code: MIT. Data: as stated by each dataset (mostly CC0).
