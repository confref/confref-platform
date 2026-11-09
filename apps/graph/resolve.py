"""Dereferencing of https://id.confref.org/ (decision 0002): Cool URIs with 303 redirects.

- A resource IRI (series/<id>, event/<id>, data/…, datasets/…, ontology/…) answers 303 See Other to a document about
  it, chosen by the Accept header: <IRI>.html (the landing page or the record view), .ttl, .jsonld, .nt or .rdf.
  The ontology itself (ontology/) goes to ontology/index.<suffix>.
- A document answers 200 with the triples whose subject is the resource (RDF), or the page about it (HTML).
- A merged identifier answers 301 Moved Permanently to the identifier it was merged into (resource or document of
  the same format); a split one 300 Multiple Choices (HTML: its parts; RDF: its history); a retired one 410 Gone
  (with its history).
- Datasets and their versions: HTML goes to their page in the catalogue on www.confref.org (303); RDF from their
  -meta graphs. Files of a version (dumps/<slug>/<version>/<path>) go to the dumps location (302).
- / goes to the page about the identifiers on www.confref.org.
"""

import json
import re

import config
import pages
from common import FORMATS, db, error_page, negotiate, rdf_response, redirect, triples_of

B = config.BASE
SUFFIX = re.compile(r"^(.*)\.(html|ttl|jsonld|nt|rdf)$")
ID = re.compile(r"^[se][0-9a-hjkmnp-tv-z]{2,}$")


def not_found(path):
    return error_page(404, "Not found",
                      f'No resource at <code>{pages.esc(B + path)}</code>. '
                      f'<a href="{pages.esc(config.LABS)}/search/">Search confref</a> or see '
                      f'<a href="{pages.esc(config.WWW)}/identifiers/">how the identifiers are made</a>.')


def resolve(path, accept, query=""):
    """path without the leading slash."""
    if path == "":
        return redirect(302, config.WWW + "/identifiers/")
    if path.startswith("dumps/"):
        return redirect(302, config.ARCHIVE + path[len("dumps/"):])
    if path in ("ontology", "ontology/"):
        fmt = negotiate(accept)
        return redirect(303, f"{config.ID}/ontology/index.{fmt}", vary=True)
    m = SUFFIX.match(path)
    if m and m.group(1) == "ontology/index":
        return ontology_doc(m.group(2))
    if m and known(m.group(1)):
        return document(m.group(1), m.group(2))
    if known(path):
        fmt = negotiate(accept)
        state = former_state(path)
        if state and state["kind"] == "merged":
            return redirect(301, f"{config.ID}/{path.split('/')[0]}/{json.loads(state['targets'])[0]}")
        if path.startswith("datasets/") and fmt == "html":
            return redirect(303, catalogue_page(path), vary=True)
        return redirect(303, f"{config.ID}/{path}.{fmt}", vary=True)
    return not_found(path)


def known(path):
    """Whether path names one of our resources: an identifier (current or former) or an IRI with triples."""
    kind, _, ident = path.partition("/")
    if kind in ("series", "event") and ID.match(ident):
        if db().execute("SELECT 1 FROM entity WHERE id = ?", (ident,)).fetchone():
            return True
        return former_state(path) is not None
    if kind in ("data", "datasets", "ontology") and ident:
        return db().execute("SELECT 1 FROM subject WHERE iri = ?", (B + path,)).fetchone() is not None
    return False


def former_state(path):
    kind, _, ident = path.partition("/")
    if kind not in ("series", "event"):
        return None
    return db().execute("SELECT * FROM history WHERE id = ?", (ident,)).fetchone()


def catalogue_page(path):
    parts = path.split("/")
    slug = parts[1]
    if slug in ("vocabulary", "agents"):
        return config.WWW + "/datasets/"
    return config.WWW + f"/datasets/{slug}/" + (f"#v{parts[2]}" if len(parts) > 2 and parts[2] not in ("meta",) else "")


def document(path, fmt):
    iri = B + path
    kind, _, ident = path.partition("/")
    state = former_state(path)
    if state and state["kind"] == "merged":
        return redirect(301, f"{config.ID}/{kind}/{json.loads(state['targets'])[0]}.{fmt}")
    triples = triples_of(iri)
    status = 200
    if state and state["kind"] == "retired":
        status = 410
    elif state and state["kind"] == "split":
        status = 300
    if fmt == "html":
        if path.startswith("datasets/"):
            return redirect(303, catalogue_page(path))
        if state:
            body = pages.former(kind, ident, state)
        elif kind in ("series", "event"):
            body = pages.landing(kind, ident)
        else:
            body = pages.record(iri, triples)
        return pages_response(status, body)
    r = rdf_response(triples, fmt, comment=f"{iri} (confref labs, beta)", status=status)
    r.headers["Link"] = f'<{iri}>; rel="describes"'
    return r


def pages_response(status, body):
    from common import Response
    return Response(status, body, FORMATS["html"][0], {"Vary": "Accept"})


def ontology_doc(fmt):
    rows = db().execute("SELECT iri FROM subject WHERE iri LIKE ?", (config.ONTOLOGY + "%",)).fetchall()
    triples = [t for r in rows for t in triples_of(r["iri"])]
    if fmt == "html":
        terms = sorted(r["iri"] for r in rows if r["iri"] != config.ONTOLOGY)
        items = "".join(f'<li>{pages.link(t, "cr:" + t[len(config.ONTOLOGY):])} {pages.esc(pages.label(t) or "")}</li>'
                        for t in terms)
        body = (f'<section><div class="wrap prose"><p class="eyebrow">Ontology <span class="beta">Beta</span></p>'
                f'<h1>The confref ontology</h1><p>Namespace <code>{config.ONTOLOGY}</code> (prefix <code>cr:</code>). '
                f'The ontology is documented in <a href="https://github.com/confref/confref-ontology/blob/main/confref-ontology.md">'
                f'confref-ontology</a>; its terms:</p><ul>{items}</ul>{pages.formats_block(config.ID + "/ontology/index")}</div></section>')
        return pages_response(200, pages.page("Ontology", body, area="id"))
    return rdf_response(triples, fmt, comment="the confref ontology, https://id.confref.org/ontology/")
