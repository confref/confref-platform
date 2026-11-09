"""Settings of the platform application and its jobs, from the environment (services/compose.yml sets them on the VM;
the defaults are those of production)."""

import os
from pathlib import Path

ID = os.environ.get("CR_ID_BASE", "https://id.confref.org").rstrip("/")        # where our IRIs resolve
LABS = os.environ.get("CR_LABS_BASE", "https://labs.confref.org").rstrip("/")  # the labs site
WWW = os.environ.get("CR_WWW", "https://www.confref.org").rstrip("/")          # the project website
ARCHIVE = os.environ.get("CR_ARCHIVE", "https://archive.confref.org/store/")    # the dumps location
BASE = "https://id.confref.org/"                                                 # the base of our IRIs, always
ONTOLOGY = BASE + "ontology/"

DB = Path(os.environ.get("CR_DB", "/generated/confref.sqlite"))                 # the index (jobs.py index)
GENERATED = Path(os.environ.get("CR_GENERATED", "/generated"))                  # files made by the jobs
STORE = Path(os.environ.get("CR_STORE", "/store"))                              # <slug>/<version>/<path>
DATAINDEX = os.environ.get(
    "CR_DATAINDEX", "https://raw.githubusercontent.com/confref/confref-data/main/catalog/dataindex.json")
CATALOG = os.environ.get("CR_CATALOG")   # local tests: the catalog/ folder of a confref-data checkout
ONTOLOGY_TTL = os.environ.get(
    "CR_ONTOLOGY_TTL", "https://raw.githubusercontent.com/confref/confref-ontology/main/confref-ontology.ttl")
SPARQL = os.environ.get("CR_SPARQL", "http://fuseki:3030/internal/query")       # for the dashboard job only
KIT_DIR = os.environ.get("CR_KIT_DIR")   # set locally: the kit is put into the pages by the app instead of nginx (SSI)
HOST = os.environ.get("CR_HOST", "0.0.0.0")
PORT = int(os.environ.get("CR_PORT", "8090"))
AGENT = "confref-platform (https://www.confref.org)"
