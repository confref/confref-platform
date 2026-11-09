"""The search of labs.confref.org (decision 0004): series and events of the identifier set by default; filters for
academic field, discipline, years, series, country, kind and attendance mode; the same as JSON for the API.

Full text by SQLite FTS5 (names, acronyms with and without the year, place and country, series and year), ranked by
BM25 with the names and acronyms weighted most; without a query the newest events first.
"""

import json
import re
import urllib.parse

import config
from common import db, esc, fmt_date, label, labs, local, num, page

B = config.BASE
PER_PAGE = 25
MODES = {"OfflineEventAttendanceMode": "on site", "OnlineEventAttendanceMode": "online",
         "MixedEventAttendanceMode": "hybrid"}


def fts_query(q):
    """An FTS5 query from user text: every word must occur (the last one as a prefix)."""
    words = re.findall(r"[\w]+", q.lower(), re.U)
    if not words:
        return None
    parts = [f'"{w}"' for w in words[:-1]] + [f'"{words[-1]}"*']
    return " ".join(parts)


def params(qs):
    g = lambda k: (qs.get(k) or [""])[0].strip()
    def year(k):
        v = g(k)
        return int(v) if v.isdigit() else None
    p = {"q": g("q"), "kind": g("kind") if g("kind") in ("event", "series") else "",
         "field": [v for v in qs.get("field", []) if re.fullmatch(r"[1-6](\.[0-9]{1,2})?", v)],
         "discipline": [v for v in qs.get("discipline", []) if re.fullmatch(r"Q[0-9]+", v)],
         "series": [v for v in qs.get("series", []) if re.fullmatch(r"s[0-9a-z]+", v)],
         "country": [v.upper() for v in qs.get("country", []) if re.fullmatch(r"[A-Za-z]{2}", v)],
         "mode": g("mode") if g("mode") in MODES else "",
         "from": year("from"), "to": year("to"),
         "sort": g("sort") if g("sort") in ("relevance", "newest", "oldest", "name") else "",
         "page": max(1, int(g("page"))) if g("page").isdigit() else 1}
    return p


def where(p, skip=None):
    """SQL conditions and arguments for the filters (without the facet skip)."""
    cond, args = [], []
    if p["q"]:
        fq = fts_query(p["q"])
        if fq:
            cond.append("e.id IN (SELECT id FROM entity_fts WHERE entity_fts MATCH ?)")
            args.append(fq)
    if p["kind"] and skip != "kind":
        cond.append("e.kind = ?")
        args.append(p["kind"])
    if p["field"] and skip != "field":
        for c in p["field"]:
            cond.append("e.id IN (SELECT id FROM entity_field WHERE code = ?)")
            args.append(c)
    if p["discipline"] and skip != "discipline":
        for d in p["discipline"]:
            cond.append("e.id IN (SELECT id FROM entity_discipline WHERE qid = ?)")
            args.append(d)
    if p["series"] and skip != "series":
        for s in p["series"]:
            cond.append("(e.id IN (SELECT id FROM entity_series WHERE series = ?) OR e.id = ?)")
            args += [s, s]
    if p["country"] and skip != "country":
        cond.append("e.country IN (" + ",".join("?" * len(p["country"])) + ")")
        args += p["country"]
    if p["mode"] and skip != "mode":
        cond.append("e.mode = ?")
        args.append(p["mode"])
    if p["from"] and skip != "years":
        cond.append("(e.year >= ? OR (e.kind = 'series' AND e.last >= ?))")
        args += [p["from"], p["from"]]
    if p["to"] and skip != "years":
        cond.append("(e.year <= ? OR (e.kind = 'series' AND e.first <= ?))")
        args += [p["to"], p["to"]]
    return (" AND ".join(cond) or "1"), args


def run(p):
    c = db()
    w, args = where(p)
    total = c.execute(f"SELECT COUNT(*) FROM entity e WHERE {w}", args).fetchone()[0]
    sort = p["sort"] or ("relevance" if p["q"] else "newest")
    off = (p["page"] - 1) * PER_PAGE
    if sort == "relevance" and p["q"] and fts_query(p["q"]):
        sql = (f"SELECT e.*, bm25(entity_fts, 0, 10.0, 8.0, 2.0, 1.0) AS score FROM entity_fts f JOIN entity e ON e.id = f.id "
               f"WHERE entity_fts MATCH ? AND {w} ORDER BY score, e.kind DESC, e.year DESC LIMIT ? OFFSET ?")
        rows = c.execute(sql, [fts_query(p["q"])] + args + [PER_PAGE, off]).fetchall()
    else:
        order = {"newest": "COALESCE(e.year, e.last) DESC, e.start DESC", "oldest": "COALESCE(e.year, e.first) ASC, e.start ASC",
                 "name": "e.label COLLATE NOCASE", "relevance": "COALESCE(e.year, e.last) DESC"}[sort]
        rows = c.execute(f"SELECT e.* FROM entity e WHERE {w} ORDER BY {order} LIMIT ? OFFSET ?",
                         args + [PER_PAGE, off]).fetchall()
    return total, rows, sort


def facets(p):
    c = db()
    out = {}
    w, a = where(p, "field")
    out["field"] = c.execute(f"SELECT f.code, COUNT(*) n FROM entity e JOIN entity_field f ON f.id = e.id WHERE {w} "
                             f"GROUP BY f.code ORDER BY f.code", a).fetchall()
    w, a = where(p, "discipline")
    out["discipline"] = c.execute(f"SELECT d.qid, COUNT(*) n FROM entity e JOIN entity_discipline d ON d.id = e.id "
                                  f"WHERE {w} GROUP BY d.qid ORDER BY n DESC LIMIT 25", a).fetchall()
    w, a = where(p, "country")
    out["country"] = c.execute(f"SELECT e.country, COUNT(*) n FROM entity e WHERE {w} AND e.country IS NOT NULL "
                               f"GROUP BY e.country ORDER BY n DESC LIMIT 25", a).fetchall()
    w, a = where(p, "series")
    out["series"] = c.execute(f"SELECT s.series, COUNT(*) n FROM entity e JOIN entity_series s ON s.id = e.id WHERE {w} "
                              f"GROUP BY s.series ORDER BY n DESC LIMIT 15", a).fetchall()
    w, a = where(p, "kind")
    out["kind"] = c.execute(f"SELECT e.kind, COUNT(*) n FROM entity e WHERE {w} GROUP BY e.kind", a).fetchall()
    w, a = where(p, "mode")
    out["mode"] = c.execute(f"SELECT e.mode, COUNT(*) n FROM entity e WHERE {w} AND e.mode IS NOT NULL GROUP BY e.mode", a).fetchall()
    w, a = where(p, "years")
    out["years"] = c.execute(f"SELECT (e.year / 10) * 10 AS d, COUNT(*) n FROM entity e WHERE {w} AND e.year IS NOT NULL "
                             f"GROUP BY d ORDER BY d", a).fetchall()
    return out


def country_label(iso):
    r = db().execute("SELECT iri FROM place WHERE iso = ?", (iso,)).fetchone()
    return label(r["iri"], iso) if r else iso


def result_json(r):
    kind = r["kind"]
    d = {"id": r["id"], "iri": B + kind + "/" + r["id"], "kind": kind, "label": r["label"], "acronyms": json.loads(r["alt"]),
         "fields": json.loads(r["fields"]), "disciplines": json.loads(r["disciplines"])}
    if kind == "event":
        d.update({"year": r["year"], "start": r["start"], "end": r["end"], "series": json.loads(r["series"]),
                  "place": r["place"], "country": r["country"], "lat": r["lat"], "lon": r["lon"],
                  "mode": MODES.get(r["mode"] or "")})
    else:
        d.update({"first": r["first"], "last": r["last"], "events": r["n"]})
    return d


def api(qs):
    p = params(qs)
    total, rows, sort = run(p)
    return {"query": {k: v for k, v in p.items() if v}, "total": total, "sort": sort, "page": p["page"],
            "per_page": PER_PAGE, "results": [result_json(r) for r in rows]}


# --- the page -------------------------------------------------------------------------------------------------------

def url_with(p, **change):
    q = dict(p)
    q.update(change)
    if "page" not in change:
        q["page"] = 1
    pairs = []
    for k, v in q.items():
        if k == "page" and v == 1:
            continue
        if isinstance(v, list):
            pairs += [(k, x) for x in v]
        elif v not in ("", None):
            pairs.append((k, v))
    return "/search/" + ("?" + urllib.parse.urlencode(pairs) if pairs else "")


def toggle(p, key, value):
    vals = list(p[key])
    if value in vals:
        vals.remove(value)
    else:
        vals.append(value)
    return url_with(p, **{key: vals})


def facet_list(title, items, p, key, name):
    if not items:
        return ""
    lis = []
    for value, n in items:
        on = value in p[key] if isinstance(p[key], list) else p[key] == value
        href = toggle(p, key, value) if isinstance(p[key], list) else url_with(p, **{key: "" if on else value})
        lis.append(f'<li><a href="{esc(href)}"{" aria-current=true" if on else ""}>{esc(name(value))}</a>'
                   f'<span class="n">{num(n)}</span></li>')
    return f'<details class="facet" open><summary>{esc(title)}</summary><ul>{"".join(lis)}</ul></details>'


def view(qs):
    p = params(qs)
    total, rows, sort = run(p)
    f = facets(p)
    fos = lambda c: label(B + "data/oecd-fos/" + c, c)
    majors = [(r["code"], r["n"]) for r in f["field"] if "." not in r["code"]]
    subs = [(r["code"], r["n"]) for r in f["field"] if "." in r["code"] and (
        any(r["code"].startswith(m + ".") for m in p["field"] if "." not in m) or r["code"] in p["field"])]
    side = [
        facet_list("Kind", [(r["kind"], r["n"]) for r in f["kind"]], p, "kind", lambda k: {"event": "Events", "series": "Series"}[k]),
        facet_list("Academic field", majors, p, "field", fos),
        facet_list("Field", subs, p, "field", fos) if subs else "",
        facet_list("Discipline", [(r["qid"], r["n"]) for r in f["discipline"]], p, "discipline",
                   lambda q: label("http://www.wikidata.org/entity/" + q, q)),
        facet_list("Country", [(r["country"], r["n"]) for r in f["country"]], p, "country", country_label),
        facet_list("Series", [(r["series"], r["n"]) for r in f["series"]], p, "series",
                   lambda s: (db().execute("SELECT label FROM entity WHERE id = ?", (s,)).fetchone() or {"label": s})["label"]),
        facet_list("Attendance", [(r["mode"], r["n"]) for r in f["mode"]], p, "mode", lambda m: MODES.get(m, m)),
    ]
    decades = "".join(f'<a class="decade" href="{esc(url_with(p, **{"from": r["d"], "to": r["d"] + 9}))}">'
                      f'{r["d"]}s <span class="n">{num(r["n"])}</span></a>' for r in f["years"])
    years = (f'<form class="years" method="get" action="/search/">' + hidden(p, exclude=("from", "to")) +
             f'<label>From <input name="from" inputmode="numeric" size="5" value="{p["from"] or ""}"></label>'
             f'<label>to <input name="to" inputmode="numeric" size="5" value="{p["to"] or ""}"></label>'
             f'<button class="button ghost small">Apply</button></form><div class="decades">{decades}</div>')
    side.insert(1, f'<details class="facet" open><summary>Years</summary>{years}</details>')
    items = "".join(result_html(r) for r in rows)
    pages_n = (total + PER_PAGE - 1) // PER_PAGE
    nav = ""
    if pages_n > 1:
        prev = f'<a href="{esc(url_with(p, page=p["page"] - 1))}">Previous</a>' if p["page"] > 1 else ""
        nxt = f'<a href="{esc(url_with(p, page=p["page"] + 1))}">Next</a>' if p["page"] < pages_n else ""
        nav = f'<nav class="pager">{prev}<span>Page {p["page"]} of {num(pages_n)}</span>{nxt}</nav>'
    active = any(p[k] for k in ("field", "discipline", "series", "country", "mode", "kind", "from", "to"))
    clear = f' · <a href="{esc(url_with(params({"q": [p["q"]]})))}">clear filters</a>' if active else ""
    sorts = " ".join(f'<a href="{esc(url_with(p, sort=s))}"{" aria-current=true" if s == sort else ""}>{n}</a>'
                     for s, n in (("relevance", "relevance"), ("newest", "newest"), ("oldest", "oldest"), ("name", "name"))
                     if s != "relevance" or p["q"])
    api_url = labs("/api/search" + url_with(p, page=p["page"])[len("/search/"):])
    body = f"""<section class="search-head"><div class="wrap">
<p class="eyebrow">Search <span class="beta">Beta</span></p>
<form class="searchbox" method="get" action="/search/" role="search">
{hidden(p, exclude=("q",))}
<input type="search" name="q" value="{esc(p["q"])}" placeholder="Name, acronym, place or year: ISWC 2020, Lisbon 2019" aria-label="Search" autofocus>
<button class="button primary">Search</button>
</form>
<p class="muted small">Series and events of the confref identifiers. <a href="{esc(labs("/api/"))}#lookup">Look up an identifier</a>
(dblp key, Wikidata, GND, DOI of the proceedings) through the API.</p>
</div></section>
<div class="wrap search-grid">
<aside class="facets" aria-label="Filters">{"".join(side)}</aside>
<div class="results">
<p class="result-count"><span><strong>{num(total)}</strong> {"result" if total == 1 else "results"}{clear}</span>
<span class="sort">Sort: {sorts}</span></p>
<ol class="hits">{items}</ol>
{nav}
<p class="muted small">As JSON: <a href="{esc(api_url)}">{esc(api_url)}</a></p>
</div></div>"""
    return page("Search", body, area="search", canonical=labs("/search/"))


def hidden(p, exclude=()):
    out = []
    for k, v in p.items():
        if k in exclude or k in ("page",):
            continue
        for x in (v if isinstance(v, list) else [v]):
            if x not in ("", None):
                out.append(f'<input type="hidden" name="{esc(k)}" value="{esc(str(x))}">')
    return "".join(out)


def result_html(r):
    kind = r["kind"]
    iri = B + kind + "/" + r["id"]
    alt = json.loads(r["alt"])
    bits = []
    if kind == "event":
        d = fmt_date(r["start"], r["end"]) or (str(r["year"]) if r["year"] else "")
        if d:
            bits.append(esc(d))
        if r["place"]:
            pl = label(r["place"], "")
            cl = country_label(r["country"]) if r["country"] and r["level"] != 3 else ""
            bits.append(esc(", ".join(x for x in (pl, cl) if x)))
        if r["mode"] == "OnlineEventAttendanceMode":
            bits.append("online")
    else:
        span = f'{r["first"]} to {r["last"]}' if r["first"] and r["last"] else ""
        bits.append(f'series, {num(r["n"] or 0)} events' + (f", {span}" if span else ""))
    fields = json.loads(r["fields"])
    chips = "".join(f'<span class="chip">{esc(label(B + "data/oecd-fos/" + c, c))}</span>' for c in fields if "." in c)
    acr = f' <span class="muted">({esc(", ".join(alt[:2]))})</span>' if alt else ""
    return (f'<li class="hit {kind}"><a class="hit-title" href="{esc(local(iri))}">{esc(r["label"])}</a>{acr}'
            f'<div class="hit-meta">{" · ".join(bits)}</div><div class="chips">{chips}</div>'
            f'<div class="hit-id mono">{esc(r["id"])}</div></li>')
