"""The HTML documents of our IRIs: landing pages of series and events, pages of former identifiers, records below
data/, ontology terms (decision 0002)."""

import json
from collections import defaultdict

import config
from common import (FORMATS, PREFIXES, db, esc, fmt_date, label, labs, link, local, num, page, short, triples_of)

B = config.BASE
SOURCES = {   # dataset -> name, and how a record of it is linked for people
    "springer-lod": "Springer LOD (2018)", "confref-portal": "confref portal (2020)", "confident": "ConfIDent",
    "wikidata": "Wikidata", "dblp": "dblp", "gnd": "GND",
}
MODES = {"OfflineEventAttendanceMode": "on site", "OnlineEventAttendanceMode": "online",
         "MixedEventAttendanceMode": "hybrid"}
STATUS = {"EventScheduled": "as scheduled", "EventCancelled": "cancelled", "EventPostponed": "postponed",
          "EventRescheduled": "rescheduled", "EventMovedOnline": "moved online"}
SYSTEMS = {"core": "CORE", "qualis": "Qualis", "gii-grin-scie": "GII-GRIN-SCIE", "ccf": "CCF",
           "h5-index": "h5-index", "h5-median": "h5-median"}


def entity_row(ident):
    return db().execute("SELECT * FROM entity WHERE id = ?", (ident,)).fetchone()


def fos_label(code):
    return label(B + "data/oecd-fos/" + code, code)


def human_link(iri):
    """Where a record of a source can be read by people."""
    if iri.startswith("http://www.wikidata.org/entity/"):
        return "https://www.wikidata.org/wiki/" + iri.rsplit("/", 1)[1]
    if iri.startswith("http://lod.springer.com/"):
        return None
    return local(iri)


def formats_block(path):
    links = " · ".join(f'<a href="{esc(path)}.{s}" type="{esc(FORMATS[s][0].split(";")[0])}">{FORMATS[s][1]}</a>'
                       for s in ("ttl", "jsonld", "nt", "rdf"))
    return f'<p class="formats muted">Data: {links}</p>'


def alternates(path):
    return "\n".join(f'<link rel="alternate" type="{esc(FORMATS[s][0].split(";")[0])}" href="{esc(path)}.{s}">'
                     for s in ("ttl", "jsonld", "nt", "rdf"))


def beta_note():
    return ('<p class="beta-note"><span class="beta">Beta</span> confref labs is under development. Identifiers are '
            'stable; pages, data and services can change.</p>')


def facts_dl(items):
    rows = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in items if v)
    return f'<dl class="facts">{rows}</dl>'


def place_html(r, doc):
    if r["place"]:
        name = label(r["place"], r["place"].rsplit("/", 1)[1])
        c = db().execute("SELECT country FROM place WHERE iri = ?", (r["place"],)).fetchone()
        country = c["country"] if c and c["country"] and c["country"] != r["place"] else None
        s = f'<a href="https://www.wikidata.org/wiki/{esc(r["place"].rsplit("/", 1)[1])}">{esc(name)}</a>'
        if country:
            s += ", " + esc(label(country, ""))
        if r["lat"] is not None and r["level"] != 3:
            s += (f' <a class="small" href="{esc(labs("/map/"))}#e={esc(r["id"])}">on the map</a>')
        return s
    if doc.get("place_name"):
        return esc(doc["place_name"]) + ' <span class="muted small">(name as given by the source)</span>'
    return ""


def fields_html(fields, discs):
    majors = sorted({c.split(".")[0] for c in fields})
    parts = []
    for m in majors:
        sub = [c for c in fields if c.startswith(m + ".")]
        url = labs(f"/search/?field={m}")
        s = f'<a href="{esc(url)}">{esc(fos_label(m))}</a>'
        if sub:
            s += ": " + ", ".join(f'<a href="{esc(labs("/search/?field=" + c))}">{esc(fos_label(c))}</a>' for c in sub)
        parts.append(s)
    f = "<br>".join(parts)
    d = ", ".join(f'<a href="{esc(labs("/search/?discipline=" + q.rsplit("/", 1)[1]))}">{esc(n)}</a>'
                  for q, n in sorted(discs.items(), key=lambda x: x[1].lower()))
    return f, d


def sources_html(members):
    by = defaultdict(list)
    for m in members:
        by[m["dataset"] or m["source"]].append(m)
    rows = []
    for ds in sorted(by, key=lambda d: list(SOURCES).index(d) if d in SOURCES else 99):
        items = []
        for m in sorted(by[ds], key=lambda m: m["iri"]):
            h = human_link(m["iri"])
            iri = f'<code>{esc(m["iri"])}</code>'
            s = f'<a href="{esc(h)}">{iri}</a>' if h else iri
            if m.get("page"):
                s += f' · <a href="{esc(m["page"])}">page</a>'
            items.append(f"<li>{s}</li>")
        name = SOURCES.get(ds, ds)
        rows.append(f'<tr><th><a href="{esc(local(B + "datasets/" + ds))}">{esc(name)}</a></th><td><ul class="plain">'
                    + "".join(items) + "</ul></td></tr>")
    return '<table class="sources">' + "".join(rows) + "</table>"


def proceedings_html(procs):
    if not procs:
        return ""
    rows = []
    for p in sorted(procs, key=lambda p: (p.get("year") or "", p.get("title") or "")):
        title = esc(p.get("title") or short(p["iri"]))
        src = ("dblp" if "dblp.org" in p["iri"] else "Springer" if "springer" in p["iri"]
               else "Wikidata" if "wikidata" in p["iri"] else "")
        ser = esc(f'{p["series"]} {p.get("volume", "")}'.strip()) if p.get("series") else ""
        doi = f'<a href="https://doi.org/{esc(p["doi"])}">{esc(p["doi"])}</a>' if p.get("doi") else ""
        h = human_link(p["iri"])
        t = f'<a href="{esc(h)}">{title}</a>' if h and h.startswith("http") else title
        rows.append(f"<tr><td>{t}<div class='muted small'>{ser}</div></td><td>{doi}</td><td>{esc(p.get('year') or '')}</td>"
                    f"<td class='muted'>{src}</td></tr>")
    return ('<section class="block"><h2>Proceedings</h2><div class="table-wrap"><table class="list">'
            '<thead><tr><th>Title</th><th>DOI</th><th>Year</th><th>Record</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div></section>")


def ratings_html(ratings):
    if not ratings:
        return ""
    rows = []
    for r in sorted(ratings, key=lambda r: (r.get("system") or "", r.get("date") or "")):
        sys_ = (r.get("system") or "").rsplit("/", 1)[-1]
        src = f' · <a href="{esc(r["source"])}">source</a>' if r.get("source") else ""
        rows.append(f'<tr><td><a href="{esc(local(r["system"]))}">{esc(SYSTEMS.get(sys_, sys_))}</a></td>'
                    f'<td><strong>{esc(r.get("value") or "")}</strong></td><td>{esc(r.get("date") or "")}</td>'
                    f'<td class="muted"><a href="{esc(local(B + "datasets/" + r["dataset"]))}">{esc(r["dataset"])}</a>{src}</td></tr>')
    return ('<section class="block"><h2>Ratings</h2><p class="muted small">As the rating systems gave them at the date '
            'shown; a rating dataset keeps them as its source published them.</p><div class="table-wrap"><table class="list">'
            '<thead><tr><th>System</th><th>Value</th><th>Date</th><th>Dataset</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div></section>")


def conflicts_html(conflicts):
    if not conflicts:
        return ""
    items = "".join(f"<li><strong>{esc(c['fact'])}</strong>: {esc(c['values'])}</li>" for c in conflicts)
    return (f'<section class="block"><h2>Where the sources disagree</h2><ul>{items}</ul>'
            f'<p class="muted small">The facts above are taken from the source first in precedence (ConfIDent, Springer, '
            f'dblp, Wikidata, the portal, the GND).</p></section>')


def schema_jsonld(r, doc, kind):
    iri = B + kind + "/" + r["id"]
    d = {"@context": "https://schema.org", "@type": "EventSeries" if kind == "series" else "Event", "@id": iri,
         "name": r["label"], "identifier": r["id"], "url": local(iri)}
    alt = json.loads(r["alt"])
    if alt:
        d["alternateName"] = alt
    if r["start"]:
        d["startDate"] = r["start"]
    if r["end"]:
        d["endDate"] = r["end"]
    if r["place"]:
        pl = {"@type": "Place", "name": label(r["place"], ""), "sameAs": r["place"]}
        if r["lat"] is not None:
            pl["geo"] = {"@type": "GeoCoordinates", "latitude": r["lat"], "longitude": r["lon"]}
        d["location"] = pl
    if r["mode"]:
        d["eventAttendanceMode"] = "https://schema.org/" + r["mode"]
    if r["status"]:
        d["eventStatus"] = "https://schema.org/" + r["status"]
    if kind == "event" and json.loads(r["series"]):
        d["superEvent"] = [{"@type": "EventSeries", "@id": B + "series/" + s} for s in json.loads(r["series"])]
    if doc.get("url"):
        d["sameAs"] = [doc["url"]]
    return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def landing(kind, ident):
    r = entity_row(ident)
    doc = json.loads(r["doc"])
    iri = B + kind + "/" + ident
    path = local(iri)
    alt = json.loads(r["alt"])
    fields, discs = fields_html(json.loads(r["fields"]), doc.get("disciplines", {}))
    chips = "".join(f'<span class="chip teal">{esc(a)}</span>' for a in alt)
    head_facts = []
    series_rows = db().execute(
        "SELECT e.id, e.label, e.alt FROM entity_series s JOIN entity e ON e.id = s.series WHERE s.id = ?", (ident,)).fetchall()
    if kind == "event":
        series = ", ".join(link(B + "series/" + s["id"], s["label"]) for s in series_rows)
        head_facts = [
            ("Date", esc(fmt_date(r["start"], r["end"])) or (esc(str(r["year"])) if r["year"] else "")),
            ("Place", place_html(r, doc)),
            ("Series", series), ("Edition", esc(str(r["edition"])) if r["edition"] else ""),
            ("Attendance", esc(MODES.get(r["mode"] or "", ""))), ("Status", esc(STATUS.get(r["status"] or "", ""))),
            ("Website", f'<a href="{esc(doc["url"])}">{esc(doc["url"])}</a>' if doc.get("url") else ""),
            ("Academic field", fields), ("Disciplines", discs),
        ]
    else:
        span = f'{r["first"]} to {r["last"]}' if r["first"] and r["last"] and r["first"] != r["last"] else (
            str(r["first"]) if r["first"] else "")
        head_facts = [
            ("Events", f'{num(r["n"] or 0)}' + (f" ({esc(span)})" if span else "")),
            ("Website", f'<a href="{esc(doc["url"])}">{esc(doc["url"])}</a>' if doc.get("url") else ""),
            ("Academic field", fields), ("Disciplines", discs),
        ]
    head_facts.append(("Identifier", f'<code class="ident">{esc(iri)}</code>'))
    eyebrow = "Conference series" if kind == "series" else "Event"
    body = [f"""<section class="entity-head"><div class="wrap">
<p class="eyebrow">{eyebrow} <span class="beta">Beta</span></p>
<h1>{esc(r["label"])}</h1>
<div class="chips">{chips}</div>
{facts_dl(head_facts)}
</div></section><div class="wrap entity-body">"""]
    if kind == "series":
        body.append(editions_html(ident))
    body.append(proceedings_html(doc.get("proceedings", [])))
    body.append(ratings_html(doc.get("ratings", [])))
    body.append(conflicts_html(doc.get("conflicts", [])))
    former = db().execute("SELECT id FROM history WHERE kind = 'merged' AND targets LIKE ?", (f'%"{ident}"%',)).fetchall()
    hist = ""
    if former:
        hist = "<p>Former identifiers merged into this one: " + ", ".join(
            link(B + kind + "/" + f["id"], f["id"]) for f in former) + "</p>"
    body.append(f"""<section class="block"><h2>Sources</h2>
<p class="muted small">The records of the sources that this identifier brings together (<code>cr:sameAs</code>).</p>
{sources_html(doc.get("members", []))}{hist}</section>
<section class="block cite"><h2>Cite</h2>
<p><code>{esc(r["label"])}. confref identifier {esc(ident)}. {esc(iri)}</code></p>
{formats_block(path)}
<p class="muted small"><a href="{esc(labs("/api/"))}">APIs</a> · <a href="{esc(labs("/sparql/"))}?query={esc(sparql_describe(iri))}">SPARQL</a>
 · <a href="{esc(config.WWW + "/identifiers/")}">About the identifiers</a></p>
</section>{beta_note()}</div>""")
    head = alternates(path) + "\n" + schema_jsonld(r, doc, kind)
    desc = f'{eyebrow}: {r["label"]}' + (f', {fmt_date(r["start"], r["end"])}' if r["start"] else "")
    return page(r["label"], "\n".join(body), head=head, canonical=path + ".html", description=desc, area="id")


def sparql_describe(iri):
    import urllib.parse
    return urllib.parse.quote(f"DESCRIBE <{iri}>")


def editions_html(sid):
    rows = db().execute("""SELECT e.* FROM entity_series s JOIN entity e ON e.id = s.id WHERE s.series = ?
        ORDER BY e.year DESC, e.start DESC, e.label""", (sid,)).fetchall()
    if not rows:
        return ""
    years = [r["year"] for r in rows if r["year"]]
    bars = ""
    if years:
        lo, hi = min(years), max(years)
        count = defaultdict(int)
        for y in years:
            count[y] += 1
        cells = "".join(
            f'<span class="tl-y{" on" if count.get(y) else ""}" title="{y}: {count.get(y, 0)}"></span>' for y in range(lo, hi + 1))
        bars = f'<div class="timeline-bar" aria-hidden="true">{cells}</div><p class="muted small tl-axis"><span>{lo}</span><span>{hi}</span></p>'
    trs = []
    for r in rows:
        pl = label(r["place"], "") if r["place"] else ""
        if r["place"] and r["country"]:
            pass
        alt = json.loads(r["alt"])
        trs.append(f'<tr><td>{esc(str(r["year"] or ""))}</td><td>{esc(str(r["edition"] or ""))}</td>'
                   f'<td>{link(B + "event/" + r["id"], r["label"])}<div class="muted small">{esc(", ".join(alt))}</div></td>'
                   f'<td>{esc(pl)}</td><td class="muted small">{esc(fmt_date(r["start"], r["end"]))}</td></tr>')
    return (f'<section class="block"><h2>Events ({num(len(rows))})</h2>{bars}<div class="table-wrap"><table class="list">'
            '<thead><tr><th>Year</th><th>No.</th><th>Event</th><th>Place</th><th>Date</th></tr></thead><tbody>'
            + "".join(trs) + "</tbody></table></div>"
            f'<p class="small"><a href="{esc(labs("/map/"))}#s={esc(sid)}">The events on the map</a> · '
            f'<a href="{esc(labs("/search/?series=" + sid))}">in the search</a> · '
            f'<a href="{esc(labs("/feeds/series/" + sid + ".ics"))}">calendar of coming events</a></p></section>')


def former(kind, ident, h):
    targets = json.loads(h["targets"])
    iri = B + kind + "/" + ident
    if h["kind"] == "split":
        items = "".join(f"<li>{link(B + kind + '/' + t, entity_label(t))}</li>" for t in targets)
        text = f"<p>This identifier was split on {esc(h['date'] or '')}: it stood for several {kind}. They are now:</p><ul>{items}</ul>"
        title = f"Split identifier {ident}"
    else:
        text = f"<p>This identifier was retired on {esc(h['date'] or '')}: no source knows its {kind} any more.</p>"
        title = f"Retired identifier {ident}"
    body = (f'<section><div class="wrap prose"><p class="eyebrow">Former identifier</p><h1>{esc(title)}</h1>{text}'
            f'<p><code>{esc(iri)}</code></p>{formats_block(local(iri))}</div></section>')
    return page(title, body, head=alternates(local(iri)), area="id")


def entity_label(ident):
    r = db().execute("SELECT label FROM entity WHERE id = ?", (ident,)).fetchone()
    return r["label"] if r else ident


def record(iri, triples):
    """A record we coin (data/…), a dataset, a version, a term: its triples."""
    m = db().execute("SELECT id FROM member WHERE iri = ?", (iri,)).fetchone()
    title = label(iri) or next((o.value for s, p, o in triples if p in (PREFIXES["rdfs"] + "label",
                                                                       PREFIXES["skos"] + "prefLabel")
                                and hasattr(o, "value")), None) or short(iri)
    rows = []
    for s, p, o in sorted(triples, key=lambda t: (t[1] != PREFIXES["rdf"] + "type", t[1], str(t[2]))):
        if hasattr(o, "value"):
            v = esc(o.value) + (f' <span class="muted small">@{esc(o.lang)}</span>' if o.lang else "")
        elif str(o).startswith("http"):
            lab = label(str(o))
            v = link(str(o), f"{lab} ({short(str(o))})" if lab else None)
        else:
            v = esc(str(o))
        rows.append(f"<tr><th>{link(p, short(p))}</th><td>{v}</td></tr>")
    ident = ""
    if m:
        kind = "series" if m["id"][0] == "s" else "event"
        ident = (f'<p class="callout">This record is part of the confref {kind} '
                 f'{link(B + kind + "/" + m["id"], entity_label(m["id"]))}.</p>')
    body = (f'<section class="entity-head"><div class="wrap"><p class="eyebrow">Record <span class="beta">Beta</span></p>'
            f'<h1>{esc(title)}</h1><p><code class="ident">{esc(iri)}</code></p>{ident}</div></section>'
            f'<div class="wrap entity-body"><section class="block"><div class="table-wrap"><table class="triples">'
            + "".join(rows) + f"</table></div>{formats_block(local(iri))}</section>{beta_note()}</div>")
    return page(title, body, head=alternates(local(iri)), canonical=local(iri) + ".html", area="id")
