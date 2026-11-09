"""The index of the platform: one SQLite file made from the stable versions of the datasets in the store, read by the
application for the landing pages, the record views, the search and the APIs (decision 0003).

    python3 index.py            (or: python3 jobs.py index)

Reads the data index of confref-data (CR_DATAINDEX) for the stable versions and the files of the store (CR_STORE,
<slug>/<version>/<path>, as load.py downloads them). Writes CR_DB (via a temporary file, then renamed, so that the
running application keeps reading the old one until the new one is complete).

Tables:
- entity: one row per series and event of the identifier set ids, with the facts the pages and filters need and a
  JSON document (doc) with the rest (members, proceedings, ratings, conflicts).
- entity_field, entity_discipline, entity_series: for the filters.
- entity_fts (FTS5): names, acronyms (also with the year), place and country, series and year.
- member: every record of every identifier; lookup: normalised keys (IRIs, dblp keys, Wikidata QIDs, GND numbers,
  DOIs and ISBNs of proceedings, page URLs) -> identifier.
- subject: the triples of every IRI we coin (identifiers, history, records below data/, datasets and versions,
  ontology terms), as N-Triples, for the RDF documents.
- label: labels of places, countries, fields, disciplines, rating systems, datasets, series.
- history: merged, split and retired identifiers.
- meta: the versions read, counts, the time of the build.
"""

import gzip
import io
import json
import re
import sqlite3
import sys
import time
import urllib.request
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import config
from rdf import BNode, IRI, Literal, nt, read_triples, TurtleParser

B = config.BASE
CR = config.ONTOLOGY
SCHEMA = "http://schema.org/"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCT = "http://purl.org/dc/terms/"
OWL_SAME = "http://www.w3.org/2002/07/owl#sameAs"
W = "http://www.wikidata.org/prop/direct/"
WD = "http://www.wikidata.org/entity/"
SPR = "http://lod.springer.com/data/ontology/property/"
DBLP = "https://dblp.org/rdf/schema#"
CF = B + "data/confident/vocab/"
PORTAL = B + "data/confref-portal/vocab/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# datasets whose subjects are not ours and that are not needed for the index (they are in the SPARQL endpoint)
SKIP_SUBJECTS = {"springer-lod-2015", "tuwien-pc"}
DATASET_TITLES = {}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def val(o):
    return o.value if isinstance(o, Literal) else str(o)


# --- the store -----------------------------------------------------------------------------------------------------

def dataindex():
    """The data index of confref-data; with CR_CATALOG (a checkout's catalog/ folder) the stable versions of the
    catalogue instead, also those not yet published (local tests)."""
    if config.CATALOG:
        out = {}
        for p in sorted(Path(config.CATALOG).glob("*.md")):
            head = p.read_text(encoding="utf-8").split("+++")[1] if p.read_text(encoding="utf-8").startswith("+++") else ""
            slug = re.search(r'^slug = "([^"]+)"', head, re.M)
            stable = re.search(r'^stable = "([^"]+)"', head, re.M)
            title = re.search(r'^title = "([^"]+)"', head, re.M)
            if slug and stable:
                out[slug.group(1)] = {"stable": stable.group(1), "title": title.group(1) if title else slug.group(1)}
        return {"datasets": out}
    src = config.DATAINDEX
    if re.match(r"https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": config.AGENT})
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    return json.loads(Path(src).read_text(encoding="utf-8"))


def stable_files(index):
    """{slug: (version, [paths of RDF files], meta path or None)} of the stable versions in the store."""
    out = {}
    for slug, d in index["datasets"].items():
        v = d.get("stable")
        if not v or d.get("withdrawn") or d.get("replaced_by"):
            continue
        DATASET_TITLES[slug] = d.get("title", slug)
        folder = config.STORE / slug / v
        if not folder.is_dir():
            log(f"not in the store: {slug}/{v}")
            continue
        files = sorted(p for p in folder.iterdir() if re.search(r"\.(ttl|nt)(\.gz)?$", p.name))
        meta = [p for p in files if p.name.endswith("-meta.ttl.gz")]
        out[slug] = (v, [p for p in files if p not in meta], meta[0] if meta else None,
                     sorted(p for p in folder.iterdir() if p.name.endswith(".tsv.gz")))
    return out


def triples_of(files, slug, name=None):
    for p in files[slug][1]:
        if name is None or p.name == name:
            yield from read_triples(p)


# --- lookup keys -----------------------------------------------------------------------------------------------------

DOI = re.compile(r"(10\.\d{4,9}/\S+)", re.I)


def norm(s):
    """The key of an identifier or IRI as written by a user or a source: lower case, without scheme, "www.", a
    trailing slash or "index.html"; DOIs as "10.x/y"; GND, dblp and Wikidata IRIs and keys in a short form."""
    s = (s or "").strip().strip("<>").strip()
    if not s:
        return ""
    m = DOI.search(s)
    if m and ("doi" in s.lower() or s.startswith("10.")):
        return m.group(1).lower().rstrip(".")
    low = s.lower()
    low = re.sub(r"^https?://", "", low)
    low = re.sub(r"^www\.", "", low)
    low = re.sub(r"(/index(\.html)?|\.html|/)$", "", low)
    m = re.fullmatch(r"(?:wikidata\.org/(?:entity|wiki)/)?(q[0-9]+)", low)
    if m:
        return m.group(1)
    m = re.fullmatch(r"(?:d-nb\.info/gnd/|gnd:)?([0-9x-]{5,}(?:-[0-9x])?)", low)
    if m and ("gnd" in low or "-" in low):
        return "gnd:" + m.group(1)
    m = re.fullmatch(r"(?:dblp\.org/(?:db|streams|rec)/|dblp\.uni-trier\.de/db/|dblp:)?((?:conf|journals|series)/[^\s]+)", low)
    if m:
        return m.group(1)
    m = re.fullmatch(r"(?:isbn:?\s*|urn:isbn:)?([0-9][0-9 -]{8,16}[0-9x])", low)
    if m:
        digits = re.sub(r"[^0-9x]", "", m.group(1))
        if len(digits) in (10, 13):
            return "isbn:" + digits
    return low


# --- building -------------------------------------------------------------------------------------------------------

def build(db_path):
    t0 = time.time()
    index = dataindex()
    files = stable_files(index)
    log(f"{len(files)} datasets with a stable version in {config.STORE}")
    tmp = db_path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA_SQL)

    # labels: fields, rating systems, disciplines, places and countries
    labels = {}
    pref = {}

    def put_label(s, o, rank):
        if isinstance(o, Literal) and (s not in pref or rank < pref[s]):
            pref[s] = rank
            labels[s] = o.value

    for slug in ("oecd-fos", "rating-systems", "wikidata-disciplines", "wikidata-places"):
        if slug not in files:
            continue
        for s, p, o in triples_of(files, slug):
            if p in (SKOS + "prefLabel", RDFS + "label") and isinstance(o, Literal):
                put_label(str(s), o, {"en": 0, "mul": 1, "de": 2}.get(o.lang or "", 3))
    fos_broader, notation = {}, {}
    for s, p, o in triples_of(files, "oecd-fos"):
        if p == SKOS + "broader":
            fos_broader[str(s)] = str(o)
        elif p == SKOS + "notation":
            notation[str(s)] = o.value
    disc_field = defaultdict(set)
    for s, p, o in triples_of(files, "ls-fields"):
        if p == CR + "field" and str(s).startswith(WD):
            disc_field[str(s)].add(notation.get(str(o), ""))
    # places
    place = defaultdict(dict)
    for s, p, o in triples_of(files, "wikidata-places"):
        s = str(s)
        if p == W + "P625":
            m = re.match(r"\s*point\(\s*([-0-9.eE]+)\s+([-0-9.eE]+)\s*\)", val(o), re.I)
            if m and "lon" not in place[s]:
                place[s]["lon"], place[s]["lat"] = round(float(m.group(1)), 4), round(float(m.group(2)), 4)
        elif p == W + "P17":
            place[s].setdefault("countries", []).append(str(o))
        elif p == W + "P297":
            place[s]["iso"] = o.value
        elif p == W + "P300":
            place[s]["region"] = o.value
    for s, d in place.items():
        if d.get("countries"):
            d["country"] = sorted(d["countries"], key=lambda c: (c != s, c))[0]
        d["level"] = 3 if "iso" in d else 2 if "region" in d else 1
    log(f"labels {len(labels):,}, places {len(place):,}")

    # the identifier set
    ent = defaultdict(lambda: defaultdict(list))
    ids_triples = defaultdict(list)
    for s, p, o in triples_of(files, "ids", "ids.ttl.gz"):
        ent[str(s)][p].append(o)
        ids_triples[str(s)].append(nt_line(s, p, o))
    history = defaultdict(lambda: defaultdict(list))
    for s, p, o in triples_of(files, "ids", "ids-history.ttl.gz"):
        history[str(s)][p].append(o)
        ids_triples[str(s)].append(nt_line(s, p, o))
    members = defaultdict(list)
    member_of = {}
    for path in files["ids"][3]:
        if path.name == "ids-members.tsv.gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                next(f)
                for line in f:
                    ident, rec, source, ds = line.rstrip("\n").split("\t")
                    members[ident].append({"iri": rec, "source": source, "dataset": ds})
                    member_of[rec] = ident
    conflicts = defaultdict(list)
    for path in files["ids"][3]:
        if path.name == "ids-conflicts.tsv.gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                next(f)
                for line in f:
                    ident, fact, values = line.rstrip("\n").split("\t")
                    conflicts[ident].append({"fact": fact, "values": values})
    log(f"ids: {len(ent):,} identifiers, {len(member_of):,} records")

    # facts of the records shown on the pages: proceedings, pages of ConfIDent and the portal, ratings
    proc = defaultdict(dict)
    wanted = {str(o) for f in ent.values() for o in f.get(CR + "proceedings", [])}
    for s, p, o in triples_of(files, "dblp"):
        s = str(s)
        if s in wanted:
            if p == DBLP + "title":
                proc[s]["title"] = o.value
            elif p == DBLP + "yearOfPublication":
                proc[s]["year"] = o.value
            elif p == DBLP + "doi" or (p == OWL_SAME and "doi.org/" in str(o)):
                proc[s].setdefault("doi", norm(str(o)))
            elif p == DBLP + "isbn":
                proc[s].setdefault("isbn", []).append(str(o).rsplit(":", 1)[-1])
            elif p == DBLP + "publishedInSeries":
                proc[s]["series"] = o.value
            elif p == DBLP + "publishedInSeriesVolume":
                proc[s]["volume"] = o.value
    for s, p, o in triples_of(files, "springer-lod"):
        s = str(s)
        if s in wanted:
            if p == SPR + "title":
                proc[s]["title"] = o.value
            elif p == SPR + "bookDOI":
                proc[s]["doi"] = o.value.lower()
            elif p in (SPR + "ISBN", SPR + "EISBN"):
                proc[s].setdefault("isbn", []).append(o.value)
            elif p == SPR + "copyrightYear":
                proc[s]["year"] = o.value
            elif p == SPR + "bookSeriesAcronym":
                proc[s]["series"] = o.value
            elif p == SPR + "volumeNumber":
                proc[s]["volume"] = o.value
    for s, p, o in triples_of(files, "wikidata"):
        s = str(s)
        if s in wanted:
            if p == RDFS + "label" and isinstance(o, Literal) and o.lang in ("en", "mul") and "title" not in proc[s]:
                proc[s]["title"] = o.value
            elif p == W + "P356":
                proc[s]["doi"] = o.value.lower()
            elif p == W + "P212":
                proc[s].setdefault("isbn", []).append(o.value)
            elif p == W + "P577":
                proc[s]["year"] = o.value[:4]
    pages = {}
    for s, p, o in triples_of(files, "confident"):
        if p == CF + "page":
            pages[str(s)] = str(o)
    for s, p, o in triples_of(files, "confref-portal"):
        if p == PORTAL + "portalPage":
            pages[str(s)] = str(o)
    ratings = defaultdict(list)
    for slug in [s for s in files if s.startswith("ratings-")]:
        node = defaultdict(dict)
        for s, p, o in triples_of(files, slug):
            node[str(s)][p.rsplit("/", 1)[-1]] = val(o)
        for r, d in node.items():
            ident = member_of.get(d.get("ratingOf", ""))
            if ident:
                ratings[ident].append({"iri": r, "system": d.get("ratingSystem"), "value": d.get("ratingValue"),
                                       "date": d.get("date"), "source": d.get("source"), "dataset": slug})
    log(f"proceedings {len(proc):,}, pages {len(pages):,}, rated identifiers {len(ratings):,}")

    # entities
    def lit(f, p):
        v = f.get(p)
        return val(v[0]) if v else None

    rows, fts, ef, ed, es = [], [], [], [], []
    series_label = {}
    for x, f in ent.items():
        if str(f.get(RDF_TYPE, [""])[0]).endswith("Series"):
            series_label[x] = lit(f, RDFS + "label") or x.rsplit("/", 1)[1]
    events_of = defaultdict(list)
    for x, f in ent.items():
        for sx in f.get(CR + "inSeries", []):
            events_of[str(sx)].append(x)
    for x, f in ent.items():
        ident = x.rsplit("/", 1)[1]
        kind = "series" if str(f.get(RDF_TYPE, [""])[0]).endswith("Series") else "event"
        label = lit(f, RDFS + "label") or ident
        alt = [val(o) for o in f.get(SCHEMA + "alternateName", [])]
        start, end = lit(f, SCHEMA + "startDate"), lit(f, SCHEMA + "endDate")
        year = lit(f, CR + "year")
        year = int(year[:4]) if year else (int(start[:4]) if start else None)
        loc = f.get(SCHEMA + "location", [])
        pl = str(loc[0]) if loc and not isinstance(loc[0], Literal) else None
        pl_name = loc[0].value if loc and isinstance(loc[0], Literal) else None
        pd = place.get(pl, {}) if pl else {}
        country = pd.get("country") if pd.get("level", 0) < 3 else pl
        iso = place.get(country, {}).get("iso") if country else None
        series = sorted(str(o).rsplit("/", 1)[1] for o in f.get(CR + "inSeries", []))
        fields = sorted({notation.get(str(o), "") for o in f.get(CR + "field", [])} - {""})
        majors = sorted({c.split(".")[0] for c in fields})
        discs = sorted(str(o) for o in f.get(CR + "discipline", []))
        mode = lit(f, SCHEMA + "eventAttendanceMode")
        status = lit(f, SCHEMA + "eventStatus")
        edition = lit(f, CR + "edition")
        mems = members.get(ident, [])
        for m in mems:
            if m["iri"] in pages:
                m["page"] = pages[m["iri"]]
        doc = {"members": mems, "url": lit(f, SCHEMA + "url"),
               "proceedings": [dict(iri=str(o), **proc.get(str(o), {})) for o in sorted(f.get(CR + "proceedings", []))],
               "ratings": ratings.get(ident, []), "conflicts": conflicts.get(ident, []),
               "place_name": pl_name, "disciplines": {d: labels.get(d, d.rsplit("/", 1)[1]) for d in discs}}
        first = last = n = None
        if kind == "series":
            ys = sorted(int(val(ent[e][CR + "year"][0])[:4]) for e in events_of.get(x, []) if ent[e].get(CR + "year"))
            first, last = (ys[0], ys[-1]) if ys else (None, None)
            n = len(events_of.get(x, []))
        rows.append((ident, kind, label, json.dumps(alt, ensure_ascii=False), start, end, year, pl,
                     pd.get("lat"), pd.get("lon"), pd.get("level"), iso, mode.rsplit("/", 1)[1] if mode else None,
                     status.rsplit("/", 1)[1] if status else None, int(edition) if edition else None,
                     json.dumps(series), json.dumps(fields), json.dumps(majors), json.dumps(discs), first, last, n,
                     json.dumps(doc, ensure_ascii=False)))
        for c in fields:
            ef.append((ident, c))
        for c in majors:
            ef.append((ident, c))
        for d in discs:
            ed.append((ident, d.rsplit("/", 1)[1]))
        for s in series:
            es.append((ident, s))
        names = [label] + [val(o) for o in f.get(SCHEMA + "name", []) if val(o) != label]
        acr = alt + ([f"{a} {year}" for a in alt] + [f"{a}{year}" for a in alt] if year else [])
        pl_text = " ".join(t for t in (labels.get(pl, "") if pl else pl_name or "", labels.get(country, "") if country else "",
                                       iso or "") if t)
        other = " ".join([series_label.get(B + "series/" + s, "") for s in series] + ([str(year)] if year else []))
        fts.append((ident, " ".join(names), " ".join(acr), pl_text, other))
    db.executemany("INSERT INTO entity VALUES (" + ",".join("?" * 23) + ")", rows)
    db.executemany("INSERT INTO entity_fts (id, name, acronym, place, other) VALUES (?,?,?,?,?)", fts)
    db.executemany("INSERT INTO entity_field VALUES (?,?)", ef)
    db.executemany("INSERT INTO entity_discipline VALUES (?,?)", ed)
    db.executemany("INSERT INTO entity_series VALUES (?,?)", es)
    log(f"entities {len(rows):,}")

    # history
    hist_rows = []
    for x, f in history.items():
        ident = x.rsplit("/", 1)[1]
        if f.get(CR + "mergedInto"):
            hist_rows.append((ident, "merged", json.dumps([str(o).rsplit("/", 1)[1] for o in f[CR + "mergedInto"]]),
                              lit(f, CR + "mergeDate")))
        elif f.get(CR + "splitInto"):
            hist_rows.append((ident, "split", json.dumps(sorted(str(o).rsplit("/", 1)[1] for o in f[CR + "splitInto"])),
                              lit(f, CR + "splitDate")))
        elif f.get(CR + "retiredDate"):
            hist_rows.append((ident, "retired", "[]", lit(f, CR + "retiredDate")))
    db.executemany("INSERT INTO history VALUES (?,?,?,?)", hist_rows)

    # members and lookup keys
    db.executemany("INSERT OR IGNORE INTO member VALUES (?,?,?,?)",
                   [(m["iri"], ident, m["source"], m["dataset"]) for ident, ms in members.items() for m in ms])
    keys = set()
    for ident, ms in members.items():
        keys.add((ident, ident, "identifier"))
        keys.add((norm(B + ("series/" if ident[0] == "s" else "event/") + ident), ident, "identifier"))
        for m in ms:
            k = norm(m["iri"])
            keys.add((k, ident, m["source"]))
            part = re.match(r"^(conf/.*[0-9]{4})-[0-9]{1,3}$", k)
            if part:   # the numbered parts of one dblp event (conf/eccv/eccv2024-1): also the key without the number
                keys.add((part.group(1), ident, m["source"]))
            if m.get("page"):
                keys.add((norm(m["page"]), ident, m["source"] + " page"))
    for x, f in ent.items():
        ident = x.rsplit("/", 1)[1]
        for o in f.get(CR + "proceedings", []):
            keys.add((norm(str(o)), ident, "proceedings"))
            pr = proc.get(str(o), {})
            if pr.get("doi"):
                keys.add((norm("doi:" + pr["doi"]), ident, "proceedings DOI"))
            for i in pr.get("isbn", []):
                keys.add((norm("isbn:" + i), ident, "proceedings ISBN"))
    for ident, kind, targets, _d in hist_rows:
        keys.add((ident, ident, "former identifier"))
    db.executemany("INSERT INTO lookup VALUES (?,?,?)", sorted(k for k in keys if k[0]))
    log(f"lookup keys {len(keys):,}")

    # triples of our IRIs (RDF documents): ids, history, records below data/, datasets, ontology
    subj = defaultdict(list)
    for s, lines in ids_triples.items():
        subj[s].extend(lines)
    for slug, (v, paths, meta, _tsv) in sorted(files.items()):
        for p in ([] if slug in SKIP_SUBJECTS or slug == "ids" else paths):
            for s, pr, o in read_triples(p):
                if isinstance(s, IRI) and s.startswith(B):
                    subj[str(s)].append(nt_line(s, pr, o))
        if meta:
            for s, pr, o in read_triples(meta):
                if isinstance(s, IRI):
                    subj[str(s)].append(nt_line(s, pr, o))
    onto = ontology_triples(files)
    for s, pr, o in onto:
        if isinstance(s, IRI):
            subj[str(s)].append(nt_line(s, pr, o))
            if pr in (RDFS + "label",) and isinstance(o, Literal) and str(s) not in labels:
                labels[str(s)] = o.value
    db.executemany("INSERT INTO subject VALUES (?,?)",
                   [(s, zlib.compress(("\n".join(sorted(set(ls))) + "\n").encode("utf-8"), 6)) for s, ls in subj.items()])
    log(f"subjects {len(subj):,}")

    for slug, title in DATASET_TITLES.items():
        labels[B + "datasets/" + slug] = title
    for x, l in series_label.items():
        labels[x] = l
    for s, d in place.items():
        if s in labels:
            pass
    db.executemany("INSERT INTO label VALUES (?,?)", sorted(labels.items()))
    db.executemany("INSERT INTO place VALUES (?,?,?,?,?,?)",
                   [(s, d.get("lat"), d.get("lon"), d.get("level"), d.get("country"), d.get("iso")) for s, d in place.items()])
    db.executemany("INSERT INTO discipline_field VALUES (?,?)",
                   [(d.rsplit("/", 1)[1], c) for d, cs in disc_field.items() for c in cs if c])
    meta = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds": round(time.time() - t0),
            "versions": {s: v[0] for s, v in files.items()},
            "counts": {"series": sum(1 for r in rows if r[1] == "series"), "events": sum(1 for r in rows if r[1] == "event"),
                       "records": len(member_of), "proceedings": len(proc), "places": len(place),
                       "rated": len(ratings), "conflicts": sum(len(v) for v in conflicts.values())}}
    db.execute("INSERT INTO meta VALUES ('build', ?)", (json.dumps(meta),))
    db.commit()
    db.execute("ANALYZE")
    db.close()
    tmp.replace(db_path)
    log(f"done: {db_path} ({db_path.stat().st_size / 1e6:.0f} MB) in {time.time() - t0:.0f} s")
    return meta


def nt_line(s, p, o):
    return f"{nt(s)} {nt(IRI(p))} {nt(o)} ."


def ontology_triples(files):
    """The ontology: the stable version of the dataset confref-ontology in the store; without it CR_ONTOLOGY_TTL."""
    if "confref-ontology" in files:
        return [t for p in files["confref-ontology"][1] for t in read_triples(p)]
    src = config.ONTOLOGY_TTL
    try:
        if re.match(r"https?://", src):
            req = urllib.request.Request(src, headers={"User-Agent": config.AGENT})
            text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        else:
            text = Path(src).read_text(encoding="utf-8")
    except OSError as e:
        log(f"ontology not read: {e}")
        return []
    return list(TurtleParser(io.StringIO(text), "confref-ontology.ttl").triples())


SCHEMA_SQL = """
CREATE TABLE entity (id TEXT PRIMARY KEY, kind TEXT, label TEXT, alt TEXT, start TEXT, end TEXT, year INTEGER,
  place TEXT, lat REAL, lon REAL, level INTEGER, country TEXT, mode TEXT, status TEXT, edition INTEGER,
  series TEXT, fields TEXT, majors TEXT, disciplines TEXT, first INTEGER, last INTEGER, n INTEGER, doc TEXT);
CREATE INDEX entity_year ON entity (year);
CREATE INDEX entity_country ON entity (country);
CREATE INDEX entity_kind ON entity (kind);
CREATE VIRTUAL TABLE entity_fts USING fts5 (id UNINDEXED, name, acronym, place, other,
  tokenize = "unicode61 remove_diacritics 2");
CREATE TABLE entity_field (id TEXT, code TEXT);
CREATE INDEX entity_field_code ON entity_field (code, id);
CREATE INDEX entity_field_id ON entity_field (id);
CREATE TABLE entity_discipline (id TEXT, qid TEXT);
CREATE INDEX entity_discipline_qid ON entity_discipline (qid, id);
CREATE INDEX entity_discipline_id ON entity_discipline (id);
CREATE TABLE entity_series (id TEXT, series TEXT);
CREATE INDEX entity_series_series ON entity_series (series, id);
CREATE INDEX entity_series_id ON entity_series (id);
CREATE TABLE member (iri TEXT PRIMARY KEY, id TEXT, source TEXT, dataset TEXT);
CREATE INDEX member_id ON member (id);
CREATE TABLE lookup (key TEXT, id TEXT, how TEXT);
CREATE INDEX lookup_key ON lookup (key);
CREATE TABLE subject (iri TEXT PRIMARY KEY, nt BLOB);   -- zlib-compressed N-Triples
CREATE TABLE label (iri TEXT PRIMARY KEY, label TEXT);
CREATE TABLE place (iri TEXT PRIMARY KEY, lat REAL, lon REAL, level INTEGER, country TEXT, iso TEXT);
CREATE TABLE discipline_field (qid TEXT, code TEXT);
CREATE TABLE history (id TEXT PRIMARY KEY, kind TEXT, targets TEXT, date TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else config.DB
    out.parent.mkdir(parents=True, exist_ok=True)
    build(out)
