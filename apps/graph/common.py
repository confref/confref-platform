"""Shared parts of the application: responses, the page frame with the labs kit, content negotiation and the RDF
serialisations (Turtle, N-Triples, JSON-LD, RDF/XML) of a set of triples."""

import html
import io
import json
import re
import sqlite3
import threading
import zlib
from collections import defaultdict
from pathlib import Path

import config
from rdf import BNode, IRI, Literal, parse_ntriples

esc = html.escape

PREFIXES = {
    "cr": config.ONTOLOGY, "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#", "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#", "schema": "http://schema.org/", "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcterms": "http://purl.org/dc/terms/", "dcat": "http://www.w3.org/ns/dcat#", "prov": "http://www.w3.org/ns/prov#",
    "void": "http://rdfs.org/ns/void#", "foaf": "http://xmlns.com/foaf/0.1/", "wd": "http://www.wikidata.org/entity/",
    "wdt": "http://www.wikidata.org/prop/direct/", "dblp": "https://dblp.org/rdf/schema#",
    "gndo": "https://d-nb.info/standards/elementset/gnd#", "geo": "http://www.opengis.net/ont/geosparql#",
    "spr": "http://lod.springer.com/data/ontology/property/", "cf": config.BASE + "data/confident/vocab/",
    "portal": config.BASE + "data/confref-portal/vocab/", "obo": "http://purl.obolibrary.org/obo/",
}

FORMATS = {   # suffix -> (media type, name)
    "html": ("text/html; charset=utf-8", "HTML"),
    "ttl": ("text/turtle; charset=utf-8", "Turtle"),
    "jsonld": ("application/ld+json", "JSON-LD"),
    "nt": ("application/n-triples", "N-Triples"),
    "rdf": ("application/rdf+xml", "RDF/XML"),
}
ACCEPT = {
    "text/html": "html", "application/xhtml+xml": "html",
    "text/turtle": "ttl", "application/x-turtle": "ttl", "text/n3": "ttl",
    "application/ld+json": "jsonld", "application/json": "jsonld",
    "application/n-triples": "nt", "text/plain": "nt",
    "application/rdf+xml": "rdf", "application/xml": "rdf", "text/xml": "rdf",
}


class Response:
    def __init__(self, status=200, body="", ctype="text/html; charset=utf-8", headers=None):
        self.status, self.body, self.ctype, self.headers = status, body, ctype, dict(headers or {})


def redirect(status, location, vary=False):
    h = {"Location": location}
    if vary:
        h["Vary"] = "Accept"
    return Response(status, "", "text/plain; charset=utf-8", h)


def negotiate(accept):
    """The suffix of the best format for an Accept header (q values; HTML first among equals, also for */*)."""
    best, best_q = "html", -1.0
    order = list(FORMATS)
    for part in (accept or "").split(","):
        bits = [b.strip() for b in part.split(";")]
        mt = bits[0].lower()
        q = 1.0
        for b in bits[1:]:
            if b.startswith("q="):
                try:
                    q = float(b[2:])
                except ValueError:
                    q = 0.0
        fmt = ACCEPT.get(mt) or ("html" if mt in ("*/*", "text/*") else None)
        if fmt and (q > best_q or (q == best_q and order.index(fmt) < order.index(best))):
            best, best_q = fmt, q
    return best


# --- the index ------------------------------------------------------------------------------------------------------

_local = threading.local()


def db():
    """A read-only connection to the index for this thread; reopened when the file was replaced."""
    path = config.DB
    st = path.stat().st_ino if path.exists() else None
    c = getattr(_local, "conn", None)
    if c is None or getattr(_local, "ino", None) != st:
        if c is not None:
            c.close()
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        c.row_factory = sqlite3.Row
        _local.conn, _local.ino = c, st
    return c


def triples_of(iri):
    row = db().execute("SELECT nt FROM subject WHERE iri = ?", (iri,)).fetchone()
    if not row:
        return []
    return list(parse_ntriples(io.StringIO(zlib.decompress(row["nt"]).decode("utf-8")), iri))


_labels = {}


def label(iri, default=None):
    if iri in _labels:
        return _labels[iri]
    row = db().execute("SELECT label FROM label WHERE iri = ?", (iri,)).fetchone()
    v = row["label"] if row else default
    if len(_labels) > 50000:
        _labels.clear()
    _labels[iri] = v
    return v


# --- links ----------------------------------------------------------------------------------------------------------

def local(iri):
    """The address of one of our IRIs where it resolves (production: the IRI itself)."""
    if iri.startswith(config.BASE):
        return config.ID + "/" + iri[len(config.BASE):]
    return iri


def labs(path):
    return config.LABS + path


def short(iri):
    for p, ns in sorted(PREFIXES.items(), key=lambda x: -len(x[1])):
        if iri.startswith(ns) and re.fullmatch(r"[A-Za-z0-9_.-]*", iri[len(ns):]):
            return f"{p}:{iri[len(ns):]}"
    return iri


def link(iri, text=None):
    return f'<a href="{esc(local(iri))}">{esc(text or short(iri))}</a>'


def fmt_date(start, end=None):
    if not start:
        return ""
    if not end or end == start:
        return start
    if start[:7] == end[:7]:
        return f"{start}/{end[8:]}"
    return f"{start} to {end}"


def num(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


# --- pages ----------------------------------------------------------------------------------------------------------

SSI_HEADER = '<!--# include virtual="/kit/1/header.html" -->'
SSI_FOOTER = '<!--# include virtual="/kit/1/footer.html" -->'


def kit(text):
    """Put the kit into a page where nginx does not (local tests: CR_KIT_DIR)."""
    if not config.KIT_DIR:
        return text
    for ssi, name in ((SSI_HEADER, "header.html"), (SSI_FOOTER, "footer.html")):
        f = Path(config.KIT_DIR) / "1" / name
        text = text.replace(ssi, f.read_text(encoding="utf-8") if f.exists() else "")
    return text


def page(title, body, *, head="", canonical=None, description=None, area=""):
    """A complete HTML page in the frame of the labs kit. area: the part of labs the page belongs to (for the
    navigation: search, map, sparql, api, dashboard)."""
    meta = f'<meta name="description" content="{esc(description)}">' if description else ""
    canon = f'<link rel="canonical" href="{esc(canonical)}">' if canonical else ""
    return kit(f"""<!doctype html>
<html lang="en" data-area="{esc(area)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · confref labs</title>
{meta}
<link rel="icon" href="/kit/1/confref-mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/kit/1/confref.css">
{canon}
{head}
</head>
<body class="labs">
<a class="skip" href="#main">Skip to content</a>
{SSI_HEADER}
<main id="main">
{body}
</main>
{SSI_FOOTER}
</body>
</html>
""")


def error_page(status, title, text):
    body = f'<section><div class="wrap prose"><p class="eyebrow">{status}</p><h1>{esc(title)}</h1><p>{text}</p></div></section>'
    return Response(status, page(title, body))


# --- RDF serialisations -----------------------------------------------------------------------------------------------

def term_ttl(t, used):
    if isinstance(t, Literal):
        s = json.dumps(t.value, ensure_ascii=False)
        if t.lang:
            return f"{s}@{t.lang}"
        if t.datatype and t.datatype != PREFIXES["xsd"] + "string":
            return f"{s}^^{term_ttl(IRI(t.datatype), used)}"
        return s
    if isinstance(t, BNode):
        return f"_:{t}"
    for p, ns in PREFIXES.items():
        if t.startswith(ns) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", t[len(ns):]):
            used.add(p)
            return f"{p}:{t[len(ns):]}"
    return f"<{t}>"


def turtle(triples, comment=None):
    used, by = set(), defaultdict(lambda: defaultdict(list))
    for s, p, o in triples:
        by[s][p].append(o)
    blocks = []
    for s in sorted(by, key=lambda x: (isinstance(x, BNode), x)):
        lines = []
        for p in sorted(by[s], key=lambda x: (x != PREFIXES["rdf"] + "type", x)):
            pp = "a" if p == PREFIXES["rdf"] + "type" else term_ttl(IRI(p), used)
            objs = sorted(term_ttl(o, used) for o in by[s][p])
            lines.append(f"    {pp} " + " ,\n        ".join(objs))
        blocks.append(f"{term_ttl(s, used)}\n" + " ;\n".join(lines) + " .")
    head = "".join(f"@prefix {p}: <{PREFIXES[p]}> .\n" for p in sorted(used))
    pre = f"# {comment}\n" if comment else ""
    return pre + head + "\n" + "\n\n".join(blocks) + "\n"


def ntriples(triples):
    from rdf import nt
    return "".join(f"{nt(s)} {nt(IRI(p))} {nt(o)} .\n" for s, p, o in sorted(triples, key=lambda t: (t[0], t[1], str(t[2]))))


def jsonld(triples):
    by = defaultdict(lambda: defaultdict(list))
    for s, p, o in triples:
        if isinstance(o, Literal):
            v = {"@value": o.value}
            if o.lang:
                v["@language"] = o.lang
            elif o.datatype and o.datatype != PREFIXES["xsd"] + "string":
                v["@type"] = o.datatype
        else:
            v = {"@id": ("_:" + o) if isinstance(o, BNode) else str(o)}
        by[s][p].append(v)
    graph = []
    for s in sorted(by):
        node = {"@id": ("_:" + s) if isinstance(s, BNode) else str(s)}
        for p in sorted(by[s]):
            if p == PREFIXES["rdf"] + "type":
                node["@type"] = sorted(v["@id"] for v in by[s][p])
            else:
                node[p] = by[s][p]
        graph.append(node)
    return json.dumps({"@graph": graph}, ensure_ascii=False, indent=1) + "\n"


def rdfxml(triples):
    from xml.sax.saxutils import escape, quoteattr
    ns, by = {}, defaultdict(list)
    for s, p, o in triples:
        by[s].append((p, o))

    def qname(p):
        m = re.match(r"^(.*[/#])([A-Za-z_][A-Za-z0-9_.-]*)$", p)
        if not m:
            raise ValueError(p)
        base, localname = m.groups()
        if base not in ns:
            pre = next((k for k, v in PREFIXES.items() if v == base), f"ns{len(ns)}")
            ns[base] = pre
        return f"{ns[base]}:{localname}"

    out = []
    for s in sorted(by):
        attr = f"rdf:nodeID={quoteattr(s)}" if isinstance(s, BNode) else f"rdf:about={quoteattr(str(s))}"
        out.append(f"  <rdf:Description {attr}>")
        for p, o in sorted(by[s], key=lambda x: (x[0], str(x[1]))):
            q = qname(p)
            if isinstance(o, Literal):
                a = f" xml:lang={quoteattr(o.lang)}" if o.lang else (
                    f" rdf:datatype={quoteattr(o.datatype)}" if o.datatype and o.datatype != PREFIXES["xsd"] + "string" else "")
                out.append(f"    <{q}{a}>{escape(o.value)}</{q}>")
            elif isinstance(o, BNode):
                out.append(f"    <{q} rdf:nodeID={quoteattr(o)}/>")
            else:
                out.append(f"    <{q} rdf:resource={quoteattr(str(o))}/>")
        out.append("  </rdf:Description>")
    rdf_ns = PREFIXES["rdf"]
    ns_decl = " ".join(f"xmlns:{pre}={quoteattr(base)}" for base, pre in sorted(ns.items(), key=lambda x: x[1])
                       if base != rdf_ns)
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<rdf:RDF xmlns:rdf="{rdf_ns}" {ns_decl}>\n'
            + "\n".join(out) + "\n</rdf:RDF>\n")


def rdf_response(triples, fmt, comment=None, status=200):
    body = {"ttl": lambda t: turtle(t, comment), "nt": ntriples, "jsonld": jsonld, "rdf": rdfxml}[fmt](triples)
    return Response(status, body, FORMATS[fmt][0], {"Access-Control-Allow-Origin": "*"})
