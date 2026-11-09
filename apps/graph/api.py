"""The APIs of labs.confref.org (decision 0005), all read-only, JSON with CORS:

- /api/lookup?id=<identifier>: the confref identifiers of a record of a source, given as IRI, key or page URL (dblp
  keys conf/x/y, Wikidata QIDs, GND numbers, ConfIDent and portal pages, Springer IRIs), of the proceedings of an
  event (dblp record, DOI, ISBN), or of a former confref identifier. /api/resolve?id=… answers 303 to the identifier.
- /api/search?…: the search (search.py) as JSON.
- /api/entity/<id>: the facts of a series or event as JSON.
- /reconcile: a reconciliation service (W3C Entity Reconciliation Community Group, API 0.2, as OpenRefine uses it):
  the manifest, queries (GET or POST, queries=…), suggest and preview.
- /feeds/upcoming.ics, /feeds/series/<id>.ics, /feeds/field/<code>.ics: coming events as iCalendar.
"""

import datetime
import json
import re

import config
import search
from common import Response, db, esc, label, local, redirect

B = config.BASE
JSON = "application/json; charset=utf-8"
CORS = {"Access-Control-Allow-Origin": "*"}


def j(data, status=200):
    return Response(status, json.dumps(data, ensure_ascii=False, indent=1) + "\n", JSON, CORS)


def norm(s):
    import index   # the same normalisation as when the keys were made
    return index.norm(s)


def lookup_ids(q):
    k = norm(q)
    rows = db().execute("SELECT DISTINCT id, how FROM lookup WHERE key = ?", (k,)).fetchall()
    if not rows and k.startswith("doi.org/"):
        rows = db().execute("SELECT DISTINCT id, how FROM lookup WHERE key = ?", (k[len("doi.org/"):],)).fetchall()
    return k, rows


def current(ident):
    """(identifier now standing for it, how): follows merges."""
    seen = set()
    while ident not in seen:
        seen.add(ident)
        h = db().execute("SELECT kind, targets FROM history WHERE id = ?", (ident,)).fetchone()
        if not h or h["kind"] != "merged":
            break
        ident = json.loads(h["targets"])[0]
    return ident


def entity_json(ident):
    r = db().execute("SELECT * FROM entity WHERE id = ?", (ident,)).fetchone()
    if not r:
        h = db().execute("SELECT * FROM history WHERE id = ?", (ident,)).fetchone()
        if h:
            return {"id": ident, "status": h["kind"], "date": h["date"], "replaced_by": json.loads(h["targets"])}
        return None
    d = search.result_json(r)
    doc = json.loads(r["doc"])
    d["sources"] = [{"iri": m["iri"], "dataset": m["dataset"], **({"page": m["page"]} if m.get("page") else {})}
                    for m in doc["members"]]
    if r["kind"] == "event":
        d["proceedings"] = doc.get("proceedings", [])
        d["place_label"] = label(r["place"], None) if r["place"] else doc.get("place_name")
    d["url"] = doc.get("url")
    d["ratings"] = doc.get("ratings", [])
    d["fields"] = [{"code": c, "label": label(B + "data/oecd-fos/" + c, c)} for c in json.loads(r["fields"])]
    d["disciplines"] = [{"iri": k, "label": v} for k, v in doc.get("disciplines", {}).items()]
    d["landing_page"] = local(d["iri"])
    return d


def lookup(qs):
    q = (qs.get("id") or qs.get("q") or [""])[0]
    if not q:
        return j({"error": "give id=<identifier>"}, 400)
    key, rows = lookup_ids(q)
    out = []
    for r in rows:
        ident = current(r["id"])
        e = db().execute("SELECT id, kind, label, year FROM entity WHERE id = ?", (ident,)).fetchone()
        if e:
            out.append({"id": e["id"], "iri": B + e["kind"] + "/" + e["id"], "kind": e["kind"], "label": e["label"],
                        "year": e["year"], "matched": r["how"] + ("" if ident == r["id"] else f", merged from {r['id']}")})
    return j({"query": q, "key": key, "matches": out})


def resolve(qs):
    q = (qs.get("id") or [""])[0]
    _key, rows = lookup_ids(q)
    ids = sorted({current(r["id"]) for r in rows})
    if len(ids) == 1:
        e = db().execute("SELECT kind FROM entity WHERE id = ?", (ids[0],)).fetchone()
        if e:
            return redirect(303, local(B + e["kind"] + "/" + ids[0]))
    if len(ids) > 1:
        return j({"query": q, "error": "several identifiers", "ids": ids}, 300)
    return j({"query": q, "error": "not found"}, 404)


def entity(ident):
    d = entity_json(ident)
    return j(d) if d else j({"error": "not found"}, 404)


# --- reconciliation -------------------------------------------------------------------------------------------------

TYPES = [{"id": "event", "name": "Event"}, {"id": "series", "name": "Conference series"}]
PROPERTIES = [{"id": "year", "name": "Year"}, {"id": "country", "name": "Country (ISO code)"},
              {"id": "acronym", "name": "Acronym"}]


def manifest():
    return {
        "versions": ["0.2"],
        "name": "confref (beta)",
        "identifierSpace": B,
        "schemaSpace": config.ONTOLOGY,
        "defaultTypes": TYPES,
        "view": {"url": config.ID + "/{{id}}"},
        "preview": {"url": config.LABS + "/reconcile/preview?id={{id}}", "width": 420, "height": 180},
        "suggest": {"entity": {"service_url": config.LABS + "/reconcile", "service_path": "/suggest/entity"}},
        "documentation": config.LABS + "/api/#reconcile",
    }


def score_candidates(q):
    """[(entity row, score 0..100)] for one reconciliation query."""
    text = (q.get("query") or "").strip()
    typ = q.get("type") if isinstance(q.get("type"), str) else None
    limit = min(int(q.get("limit") or 5), 25)
    props = {p.get("pid"): str(p.get("v", "")).strip() for p in q.get("properties", []) if isinstance(p, dict)}
    year = props.get("year") or next(iter(re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", text)), None)
    fq = search.fts_query(text)
    if not fq:
        return []
    cond, args = ["entity_fts MATCH ?"], [fq]
    if typ in ("event", "series"):
        cond.append("e.kind = ?")
        args.append(typ)
    rows = db().execute("SELECT e.*, bm25(entity_fts, 0, 10.0, 8.0, 2.0, 1.0) AS rank FROM entity_fts f "
                        "JOIN entity e ON e.id = f.id WHERE " + " AND ".join(cond) + " ORDER BY rank LIMIT 50", args).fetchall()
    low = text.lower()
    out = []
    for r in rows:
        s = 50.0
        names = [r["label"].lower()] + [a.lower() for a in json.loads(r["alt"])]
        if low in names or (year and low.replace(year, "").strip() in names):
            s += 30
        if year and r["year"] and str(r["year"]) == str(year):
            s += 15
        elif year and r["year"]:
            s -= 25
        if props.get("country") and r["country"] and r["country"] == props["country"].upper():
            s += 5
        if props.get("acronym") and props["acronym"].lower() in [a.lower() for a in json.loads(r["alt"])]:
            s += 10
        s += max(0, 10 + r["rank"]) / 2   # BM25 is negative, better is lower
        out.append((r, max(0.0, min(100.0, s))))
    out.sort(key=lambda x: -x[1])
    out = out[:limit]
    if len(out) > 1 and out[0][1] - out[1][1] < 10:
        return [(r, sc, False) for r, sc in out]
    return [(r, sc, i == 0 and sc >= 85) for i, (r, sc) in enumerate(out)]


def reconcile_results(q):
    return {"result": [{"id": f'{r["kind"]}/{r["id"]}', "name": r["label"] + (f' ({r["year"]})' if r["year"] else ""),
                        "type": [next(t for t in TYPES if t["id"] == r["kind"])], "score": round(sc, 1), "match": m}
                       for r, sc, m in score_candidates(q)]}


def reconcile(qs, body=None):
    raw = (qs.get("queries") or [None])[0]
    if body and not raw:
        import urllib.parse
        form = urllib.parse.parse_qs(body)
        raw = (form.get("queries") or [None])[0]
    if not raw:
        cb = (qs.get("callback") or [None])[0]
        data = manifest()
        if cb and re.fullmatch(r"[A-Za-z0-9_.$]+", cb):
            return Response(200, f"{cb}({json.dumps(data)})", "application/javascript", CORS)
        return j(data)
    try:
        queries = json.loads(raw)
    except ValueError:
        return j({"error": "queries is not JSON"}, 400)
    return j({k: reconcile_results(v) for k, v in queries.items() if isinstance(v, dict)})


def suggest(qs):
    prefix = (qs.get("prefix") or [""])[0]
    fq = search.fts_query(prefix)
    if not fq:
        return j({"result": []})
    rows = db().execute("SELECT e.* FROM entity_fts f JOIN entity e ON e.id = f.id WHERE entity_fts MATCH ? "
                        "ORDER BY bm25(entity_fts, 0, 10.0, 8.0, 2.0, 1.0) LIMIT 10", (fq,)).fetchall()
    return j({"result": [{"id": f'{r["kind"]}/{r["id"]}', "name": r["label"],
                          "description": " · ".join(x for x in (str(r["year"] or ""), label(r["place"], "") if r["place"] else "") if x)}
                         for r in rows]})


def preview(qs):
    ident = (qs.get("id") or [""])[0].rsplit("/", 1)[-1]
    d = entity_json(ident)
    if not d:
        return Response(404, "not found", "text/plain")
    bits = [str(d.get("year") or ""), d.get("place_label") or ""]
    html = (f'<html><body style="font:14px system-ui;margin:8px"><a href="{esc(d["landing_page"])}" target="_blank">'
            f'<strong>{esc(d["label"])}</strong></a><br>{esc(" · ".join(b for b in bits if b))}<br>'
            f'<code>{esc(d["iri"])}</code></body></html>')
    return Response(200, html, "text/html; charset=utf-8", CORS)


# --- calendar -------------------------------------------------------------------------------------------------------

def ics_escape(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def feed(kind, value):
    today = datetime.date.today().isoformat()
    base = "SELECT e.* FROM entity e WHERE e.kind = 'event' AND e.start >= ?"
    if kind == "series":
        rows = db().execute(base + " AND e.id IN (SELECT id FROM entity_series WHERE series = ?) ORDER BY e.start",
                            (today, value)).fetchall()
        name = (db().execute("SELECT label FROM entity WHERE id = ?", (value,)).fetchone() or {"label": value})["label"]
    elif kind == "field":
        rows = db().execute(base + " AND e.id IN (SELECT id FROM entity_field WHERE code = ?) ORDER BY e.start LIMIT 2000",
                            (today, value)).fetchall()
        name = label(B + "data/oecd-fos/" + value, value)
    else:
        rows = db().execute(base + " ORDER BY e.start LIMIT 2000", (today,)).fetchall()
        name = "all"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//confref//labs//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:confref: {ics_escape(name)}"]
    for r in rows:
        end = r["end"] or r["start"]
        try:
            dtend = (datetime.date.fromisoformat(end) + datetime.timedelta(days=1)).strftime("%Y%m%d")
        except ValueError:
            continue
        place = label(r["place"], "") if r["place"] else ""
        lines += ["BEGIN:VEVENT", f"UID:{r['id']}@id.confref.org", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{r['start'].replace('-', '')}", f"DTEND;VALUE=DATE:{dtend}",
                  f"SUMMARY:{ics_escape(r['label'])}", f"URL:{local(B + 'event/' + r['id'])}"]
        if place:
            lines.append(f"LOCATION:{ics_escape(place)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return Response(200, "\r\n".join(fold(l) for l in lines) + "\r\n", "text/calendar; charset=utf-8", CORS)


def fold(line):
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 74:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)
