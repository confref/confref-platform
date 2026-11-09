#!/usr/bin/env python3
"""Load the confref datasets into a Fuseki dataset: the stable version of every dataset in the data index of
confref-data (catalog/dataindex.json), with the corrections applied.

- Datasets that are replaced by another (replaced_by) or withdrawn, and datasets without a stable version are left out.
- Every dataset goes into its own named graph, graph IRI = dataset IRI (https://id.confref.org/datasets/<slug>);
  its description <slug>-meta.ttl.gz into <dataset IRI>/meta (kg-commons 0018).
- Only the RDF files of a version are loaded (.ttl, .nt, .n3, gzipped or not); the deletions of the correction
  datasets (*.ru.gz, SPARQL Update) are run after all datasets are loaded.
- Files are downloaded into STORE in the layout <slug>/<version>/<path> (the layout of every dumps location, kg-commons 0019),
  checked against the sha256 of the index, and not downloaded again. STORE can be served as a dumps location.
- Loading goes over HTTP (Graph Store Protocol), not with tdb2.tdbloader: the bulk loader of Fuseki 6.2.0 silently
  wraps integers beyond 64 bits (measured with Fuseki 6.2.0 in 2026-10). tdb2.tdbcompact has the same fault, so
  the files are scanned for numbers of 19 or more digits while they are uploaded: load.sh compacts the database only
  if there are none ("long numbers: 0" in the output).
- At the end every data graph is compared with the void:triples of its -meta (less the triples deleted by the
  corrections); the exit code is 1 if anything failed or differs.

    python3 load.py --fuseki http://127.0.0.1:3031/confref --store /data/confref/store
    python3 load.py --dry-run                 # only list what would be loaded

Python 3.11 or newer, standard library only.
"""

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

INDEX = "https://raw.githubusercontent.com/confref/confref-data/main/catalog/dataindex.json"
DATASETS = "https://id.confref.org/datasets/"
TYPES = {".ttl": "text/turtle", ".n3": "text/turtle", ".nt": "application/n-triples"}
AGENT = "confref-platform loader (https://www.confref.org)"
# a number of 19 or more digits as a value, not inside an IRI or a string: a bare token in Turtle or N-Triples, or a
# typed literal whose lexical form starts with it ("…"^^<…>); counted by post()
DIGITS = re.compile(rb"\d{19}")          # the quick test before LONG
LONG = re.compile(rb"""(?:^|[\s,(\[])[+-]?\d{19,}(?=[\s,;.)\]eE]|$)|["'][+-]?\d{19,}[^"'\s]*["']\^\^""")


def http(url, data=None, content_type=None, accept=None):
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET",
                                 headers={"User-Agent": AGENT})
    if content_type:
        req.add_header("Content-Type", content_type)
    if accept:
        req.add_header("Accept", accept)
    if hasattr(data, "read"):
        req.add_header("Content-Length", str(Path(data.name).stat().st_size))
    return urllib.request.urlopen(req)


def read_index(where):
    if re.match(r"https?://", where):
        with http(where) as r:
            return json.load(r)
    return json.loads(Path(where).read_text(encoding="utf-8"))


def plan(index):
    """(slug, version, files) of every dataset to load; files are the entries of the index."""
    out = []
    for slug, e in sorted(index["datasets"].items()):
        if e.get("replaced_by") or e.get("withdrawn") or not e.get("stable"):
            continue
        v = next(v for v in e["versions"] if v["version"] == e["stable"])
        files = [f for f in v["files"] if rdf_type(f["path"]) or f["path"].endswith(".ru.gz")]
        out.append((slug, e["stable"], files))
    return out


def rdf_type(path):
    return TYPES.get(Path(path.removesuffix(".gz")).suffix)


def fetch(store, base, slug, version, f):
    local = store / slug / version / f["path"]
    if not (local.exists() and local.stat().st_size == f["bytes"]):
        local.parent.mkdir(parents=True, exist_ok=True)
        part = local.parent / (local.name + ".part")
        with http(f"{base}{slug}/{version}/{f['path']}") as r, open(part, "wb") as out:
            shutil.copyfileobj(r, out)
        part.rename(local)
    h = hashlib.sha256()
    with open(local, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest() != f["sha256"]:
        local.rename(local.parent / (local.name + ".bad"))
        raise ValueError(f"checksum differs: {slug}/{version}/{f['path']}")
    return local


def update(fuseki, sparql):
    http(f"{fuseki}/update", sparql.encode("utf-8"), "application/sparql-update").read()


def select(fuseki, query):
    data = urllib.parse.urlencode({"query": query}).encode()
    with http(f"{fuseki}/query", data, "application/x-www-form-urlencoded", "application/sparql-results+json") as r:
        return [{k: v["value"] for k, v in b.items()} for b in json.load(r)["results"]["bindings"]]


def post(fuseki, local, graph):
    """Upload one file into a graph; gzipped files are unpacked into a temporary file first. Returns the number of
    long numbers in it (LONG)."""
    long = 0
    with tempfile.NamedTemporaryFile(suffix=Path(local.name.removesuffix(".gz")).suffix) as tmp:
        with (gzip.open(local) if local.name.endswith(".gz") else open(local, "rb")) as f:
            for line in f:
                tmp.write(line)
                if DIGITS.search(line):
                    long += len(LONG.findall(line))
        tmp.flush()
        with open(tmp.name, "rb") as body:
            http(f"{fuseki}/data?graph=" + urllib.parse.quote(graph, safe=""), body,
                 rdf_type(local.name)).read()
    return long


def check(fuseki, deletions):
    """Compare every data graph with the void:triples of its -meta, less what the corrections deleted."""
    counts = {r["g"]: int(r["n"]) for r in select(fuseki,
              "SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g")}
    stated = {r["g"]: int(r["t"]) for r in select(fuseki, """PREFIX void: <http://rdfs.org/ns/void#>
        PREFIX dcat: <http://www.w3.org/ns/dcat#>
        SELECT ?g ?t WHERE { GRAPH ?m { ?v dcat:isVersionOf ?g ; void:triples ?t }
                             FILTER(STR(?m) = CONCAT(STR(?g), "/meta")) }""")}
    print(f"graphs: {len(counts)} ({sum(g.endswith('/meta') for g in counts)} -meta), "
          f"triples: {sum(counts.values()):,}")
    differ = 0
    for g in sorted(stated):
        n, want = counts.get(g, 0), stated[g] - deletions.get(g, 0)
        if n != want:
            differ += 1
            print(f"  DIFFERS {g.removeprefix(DATASETS)}: loaded {n:,}, stated {stated[g]:,}"
                  f" less {deletions.get(g, 0):,} deleted")
    missing = [g.removeprefix(DATASETS) for g in counts if not g.endswith("/meta") and g not in stated]
    if missing:
        print("  data graphs without a stated count:", ", ".join(missing))
    return differ


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", default=INDEX, help="data index, URL or path (default: confref-data on GitHub)")
    ap.add_argument("--source", help="dumps location to download from (default: 'archive' of the index)")
    ap.add_argument("--store", type=Path, default=Path("store"), help="local copy of the files")
    ap.add_argument("--fuseki", default="http://127.0.0.1:3031/confref", help="Fuseki dataset (writable)")
    ap.add_argument("--dry-run", action="store_true", help="only list the datasets and files")
    ap.add_argument("--skip", default="", help="datasets not to load, separated by commas (e.g. springer-lod-chapters)")
    args = ap.parse_args()

    index = read_index(args.index)
    base = args.source or index["locations"]["dumps"]["archive"]
    todo = [t for t in plan(index) if t[0] not in set(filter(None, args.skip.split(",")))]
    print(f"data index of {index['checked']}: {len(todo)} datasets, "
          f"{sum(len(f) for _, _, f in todo)} files, from {base}")
    if args.dry_run:
        for slug, version, files in todo:
            print(f"  {slug} {version}: " + ", ".join(f["path"] for f in files))
        return 0

    failed, ru, long = [], [], 0
    for slug, version, files in todo:
        graph = DATASETS + slug
        print(f"{slug} {version}", flush=True)
        try:
            update(args.fuseki, f"DROP SILENT GRAPH <{graph}> ; DROP SILENT GRAPH <{graph}/meta>")
            for f in files:
                local = fetch(args.store, base, slug, version, f)
                if f["path"].endswith(".ru.gz"):
                    ru.append(local)
                    continue
                target = f"{graph}/meta" if f["path"] == f"{slug}-meta.ttl.gz" else graph
                print(f"  {f['path']} -> <{target}>", flush=True)
                n = post(args.fuseki, local, target)
                if n:
                    print(f"  {n:,} numbers of 19 or more digits", flush=True)
                long += n
        except Exception as e:      # report and go on with the next dataset
            print(f"  FAILED: {e}", flush=True)
            failed.append(slug)

    deletions = {}                  # graph -> triples deleted by the corrections
    for local in ru:
        print(f"corrections: {local.relative_to(args.store)}", flush=True)
        try:
            text = gzip.decompress(local.read_bytes()).decode("utf-8")
            # the deletions have the form DELETE { GRAPH ?g { ?s ?p ?o } } WHERE { ... }: count them first
            sel = re.sub(r"DELETE\s*\{\s*GRAPH \?g \{ \?s \?p \?o \} \}\s*WHERE", "SELECT ?g ?s ?p ?o WHERE", text)
            if sel != text:
                for r in select(args.fuseki, sel):
                    deletions[r["g"]] = deletions.get(r["g"], 0) + 1
            update(args.fuseki, text)
        except Exception as e:
            print(f"  FAILED: {e}", flush=True)
            failed.append(str(local.name))

    differ = check(args.fuseki, deletions)
    print(f"long numbers: {long}")      # load.sh compacts the database only if this is 0
    print("done" + (f"; failed: {', '.join(failed)}" if failed else "") + (f"; {differ} graphs differ" if differ else ""))
    return 1 if failed or differ else 0


if __name__ == "__main__":
    sys.exit(main())
