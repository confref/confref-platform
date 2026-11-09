"""The dashboard of labs.confref.org (decision 0006): what the loaded data covers, per source and per fact, and where
the sources disagree. Computed from the index once per index file; /status.json gives the same as JSON."""

import json

import config
from common import db, esc, labs, num, page

_cache = {}


def status():
    c = db()
    key = c.execute("SELECT value FROM meta WHERE key = 'build'").fetchone()[0]
    if _cache.get("key") == key:
        return _cache["data"]
    build = json.loads(key)
    q = lambda sql: c.execute(sql).fetchone()[0]
    ev = q("SELECT COUNT(*) FROM entity WHERE kind = 'event'")
    se = q("SELECT COUNT(*) FROM entity WHERE kind = 'series'")
    facts = {
        "events with a date": q("SELECT COUNT(*) FROM entity WHERE kind = 'event' AND start IS NOT NULL"),
        "events with a year": q("SELECT COUNT(*) FROM entity WHERE kind = 'event' AND year IS NOT NULL"),
        "events placed in a city": q("SELECT COUNT(*) FROM entity WHERE kind = 'event' AND level = 1"),
        "events placed in a region": q("SELECT COUNT(*) FROM entity WHERE kind = 'event' AND level = 2"),
        "events placed in a country only": q("SELECT COUNT(*) FROM entity WHERE kind = 'event' AND level = 3"),
        "events with an academic field": q("SELECT COUNT(DISTINCT f.id) FROM entity_field f JOIN entity e ON e.id = f.id WHERE e.kind = 'event'"),
        "events with a discipline": q("SELECT COUNT(DISTINCT d.id) FROM entity_discipline d JOIN entity e ON e.id = d.id WHERE e.kind = 'event'"),
        "events in a series": q("SELECT COUNT(DISTINCT s.id) FROM entity_series s"),
        "events online": q("SELECT COUNT(*) FROM entity WHERE mode = 'OnlineEventAttendanceMode'"),
    }
    per_dataset = {r["dataset"]: r["n"] for r in c.execute(
        "SELECT dataset, COUNT(*) n FROM member GROUP BY dataset ORDER BY n DESC")}
    by_decade = {r["d"]: r["n"] for r in c.execute(
        "SELECT (year / 10) * 10 d, COUNT(*) n FROM entity WHERE kind = 'event' AND year IS NOT NULL GROUP BY d ORDER BY d")}
    data = {"built": build["built"], "versions": build["versions"], "series": se, "events": ev, "facts": facts,
            "records per dataset": per_dataset, "events per decade": by_decade, "counts": build["counts"]}
    _cache.update(key=key, data=data)
    return data


def bar(n, total):
    pct = 100 * n / total if total else 0
    return (f'<div class="meter" role="img" aria-label="{pct:.0f}%"><span style="width:{pct:.1f}%"></span></div>'
            f'<span class="pct">{pct:.0f}%</span>')


def view():
    s = status()
    ev = s["events"]
    rows = "".join(f"<tr><th>{esc(k)}</th><td class='num'>{num(v)}</td><td class='bar'>{bar(v, ev)}</td></tr>"
                   for k, v in s["facts"].items())
    src = "".join(f"<tr><th>{esc(k)}</th><td class='num'>{num(v)}</td></tr>" for k, v in s["records per dataset"].items())
    mx = max(s["events per decade"].values() or [1])
    dec = "".join(f'<div class="dec"><span style="height:{100 * v / mx:.0f}%" title="{k}s: {v:,}"></span><i>{k}</i></div>'
                  for k, v in s["events per decade"].items())
    vers = "".join(f'<li><a href="{esc(config.WWW)}/datasets/{esc(k)}/"><code>{esc(k)}</code></a> {esc(v)}</li>'
                   for k, v in sorted(s["versions"].items()))
    conflicts = s["counts"].get("conflicts", 0)
    archive = config.ARCHIVE + "ids/" + s["versions"].get("ids", "") + "/ids-conflicts.tsv.gz"
    body = f"""<section class="search-head"><div class="wrap">
<p class="eyebrow">Dashboard <span class="beta">Beta</span></p>
<h1>The loaded data</h1>
<p class="lead">{num(s["series"])} series and {num(ev)} events from the datasets below, loaded {esc(s["built"])}.</p>
</div></section>
<div class="wrap dash">
<section class="block"><h2>Facts of the events</h2><div class="table-wrap"><table class="list dash-table">{rows}</table></div></section>
<section class="block"><h2>Events per decade</h2><div class="decades-chart">{dec}</div></section>
<section class="block"><h2>Records per source</h2><p class="muted small">Records of the sources joined into the identifiers.</p>
<div class="table-wrap"><table class="list dash-table">{src}</table></div></section>
<section class="block"><h2>Where the sources disagree</h2>
<p>{num(conflicts)} facts of events on which their sources disagree: start dates more than two days apart, years,
edition numbers, places more than 50 km apart. The list: <a href="{esc(archive)}">ids-conflicts.tsv.gz</a>.
The landing page of an event shows its disagreements.</p></section>
<section class="block"><h2>Versions loaded</h2><ul class="cols">{vers}</ul>
<p class="muted small">As JSON: <a href="{esc(labs("/status.json"))}">/status.json</a>.
Quality of the links: <a href="https://github.com/confref/confref-data/tree/main/docs/reports">reports</a>.</p></section>
</div>"""
    return page("Dashboard", body, area="dashboard")
