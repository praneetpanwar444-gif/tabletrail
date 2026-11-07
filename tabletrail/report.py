"""A portable report: no CDN, analytics, network requests, or server required."""

from html import escape
from decimal import Decimal
from importlib.resources import files
import json
from urllib.parse import quote


def _e(value) -> str:
    return escape(str(value) if value is not None else "—", quote=True)


def _table(headers, rows, *, name):
    head = "".join(f"<th scope='col'>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_e(v)}</td>" for v in row) + "</tr>" for row in rows)
    return (f"<div class='table-wrap'><table data-searchable='{name}'><thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def render_html(report: dict) -> str:
    comparison = report["kind"] == "comparison"
    count = report["change_count"] if comparison else report["issue_count"]
    title = {"profile": "Know your data.", "validation": "Trust, then ship.",
             "comparison": "See what changed."}[report["kind"]]
    description = (f"Compared against {report['baseline']}" if comparison else
                   f"Contract: {report['contract']}" if report["contract"] else
                   "A complete first look at structure, completeness, and repeated records.")
    status = "Review changes" if comparison and count else "Needs attention" if count else "Checks complete"
    metrics = [("Records scanned", f"{report['rows']:,}", "Every non-blank data record"),
               ("Columns", report["column_count"], "Named fields in the CSV"),
               ("Changes detected" if comparison else "Rule violations", count,
                "Beyond configured thresholds" if comparison else "Full count, including omitted examples"),
               ("Baseline records" if comparison else "Repeated records",
                report.get("baseline_rows", report.get("duplicate_rows", 0)),
                "Reference dataset" if comparison else "Occurrences after the first matching record")]
    cards = "".join(f"<article class='metric'><span>{_e(label)}</span><strong>{_e(value)}</strong>"
                    f"<small>{_e(note)}</small></article>" for label, value, note in metrics)
    columns = []
    for col in report["columns"]:
        rate = col["null_rate"] * 100
        top = ", ".join(f"{v['value']} ({v['count']})" for v in col["top_values"][:3]) or "—"
        columns.append((col["name"], col["inferred_type"], f"{rate:.1f}%",
                        col["distinct_count"], format(Decimal(col["numeric_mean"]), ".6g") if col["numeric_mean"] else None, top))
    column_table = _table(["Column", "Detected type", "Missing", "Distinct", "Numeric mean", "Frequent values"],
                          columns, name="columns")
    quality_bars = "".join(
        f"<div class='bar-row'><span>{_e(c['name'])}</span><div class='track'>"
        f"<div style='width:{(1-c['null_rate'])*100:.4f}%'></div></div>"
        f"<strong>{(1-c['null_rate'])*100:.1f}%</strong></div>" for c in report["columns"])
    if comparison:
        detail_table = _table(["Column", "Change", "Before", "After", "Explanation"],
                              [(c["column"] or "Dataset", c["code"], c["before"], c["after"], c["message"])
                               for c in report["changes"]], name="details")
        detail_note = ("Null threshold is an absolute fraction increase; means and record counts use relative change. "
                       f"Thresholds: {report['thresholds']}")
    else:
        detail_table = _table(["Record", "Ending line", "Column", "Rule", "Observed", "Explanation"],
                              [(i["record"], i["line"], i["column"] or "Dataset", i["code"], i["value"], i["message"])
                               for i in report["issues"]], name="details")
        detail_note = (f"{report['failed_records']} records failed. {report['omitted_issues']} additional issue examples "
                       "were omitted by the configured limit. Header issues have no record number.")
    empty = "<div class='empty'><b>No findings to review.</b><p>This run found no violations or changes.</p></div>" if not count else ""
    payload = json.dumps(report, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    css = files("tabletrail").joinpath("report.css").read_text(encoding="utf-8")
    js = files("tabletrail").joinpath("report.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<meta name="color-scheme" content="light"><title>TableTrail · {_e(report['source'])}</title><style>{css}</style></head>
<body><aside><a class="brand" href="#overview"><span class="mark">▥</span> TableTrail<span class="version">0.1</span></a>
<p class="side-label">DATA WORKSPACE</p><nav aria-label="Report sections"><a href="#overview" class="active">◫ &nbsp; Overview</a>
<a href="#columns">▤ &nbsp; Column profiles</a><a href="#findings">⌕ &nbsp; Findings <span>{count}</span></a></nav>
<div class="side-footer"><i></i> Offline by design<p>Your file stays on your machine.<br>No accounts. No cloud uploads.</p></div></aside>
<main><header><span>WORKSPACE <b>/</b> {_e(report['kind'].title())}</span><a id="download" download="tabletrail-report.json" href="data:application/json;charset=utf-8,{quote(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + chr(10), safe='')}">↓ Export JSON</a></header>
<section id="overview" class="hero"><div><p class="eyebrow">A CLEARER PICTURE</p><h1>{title}</h1>
<p class="subtitle">{_e(description)}</p><div class="file"><span>CSV</span> {_e(report['source'])}</div></div>
<span class="status {'warn' if count else 'good'}"><i></i>{status}</span></section>
<div class="metrics">{cards}</div>
<section class="card completeness"><div><p class="eyebrow">COVERAGE AT A GLANCE</p><h2>Completeness, column by column</h2>
<p class="muted">Non-missing values as a share of all records.</p></div><div class="bars">{quality_bars}</div></section>
<section id="columns" class="card"><div class="section-heading"><div><p class="eyebrow">THE SHAPE OF YOUR DATA</p><h2>Column profiles</h2></div>
<label class="search"><span>⌕</span><input data-filter="columns" type="search" aria-label="Filter column profiles" placeholder="Find a column or value…"></label></div>
{column_table}<p class="table-note">Distinct counts are exact. Numeric statistics describe parseable numeric cells only. Values are trimmed; zero-padded IDs stay strings.</p></section>
<section id="findings" class="card"><div class="section-heading"><div><p class="eyebrow">YOUR NEXT STEP</p><h2>{'Dataset changes' if comparison else 'Validation findings'}</h2></div>
<label class="search"><span>⌕</span><input data-filter="details" type="search" aria-label="Filter findings" placeholder="Filter findings…"></label></div>
<p class="muted detail-note">{_e(detail_note)}</p>{empty}{detail_table if count else ''}</section>
<footer>TableTrail <span>·</span> Local analysis. Clear decisions. <a href="#overview">Back to top ↑</a></footer></main>
<script id="report-data" type="application/json">{payload}</script><script>{js}</script></body></html>"""
