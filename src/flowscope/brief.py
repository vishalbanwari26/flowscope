"""A one-page brief for people who do not read code: what the system does, how its parts
fit, where it is slow, what no test covers, and what fails.

It is built from the saved overview (survey.Index) and the source scan (gaps), so it
needs no new run. The output is one HTML file with everything inline: it can be sent
by mail, opened offline, and printed to PDF.
"""
from __future__ import annotations

import datetime
from html import escape

from .report import error_lines, pct
from .survey import Index

MAX_NODES = 12       # modules drawn in the diagram; more than this gets crowded
MAX_CLAUSES = 4      # "a calls b" clauses per use case sentence
NODE_W, NODE_H, COL_GAP, ROW_GAP = 128, 40, 96, 22


def sentence(edges: list) -> str:
    """One use case in words: 'orders calls stock and pricing; pricing calls catalog'."""
    calls: dict = {}
    for a, b, _n in edges:
        if a != "entry" and a != b:
            calls.setdefault(a, [])
            if b not in calls[a]:
                calls[a].append(b)
    clauses = []
    for a, bs in calls.items():
        who = bs[0] if len(bs) == 1 else ", ".join(bs[:-1]) + " and " + bs[-1]
        clauses.append(f"{a} calls {who}")
    if not clauses:
        return "Runs inside a single module."
    more = f" (and {len(clauses) - MAX_CLAUSES} more steps)" if len(clauses) > MAX_CLAUSES else ""
    return "; ".join(clauses[:MAX_CLAUSES]) + more + "."


def layers(nodes: list, edges: list) -> dict:
    """Column per module: how many calls away from a module nobody calls."""
    depth = {n: 0 for n in nodes}
    for _ in range(len(nodes)):                      # enough passes to settle; cycles just stop growing
        for a, b in edges:
            if depth[b] < depth[a] + 1 and depth[a] + 1 < len(nodes):
                depth[b] = depth[a] + 1
    return depth


def diagram(ix: Index) -> str:
    """The modules as boxes in columns, arrows for 'calls', shade for the share of time."""
    ranked = sorted(ix.mod_tests, key=lambda m: (-ix.mod_self.get(m, 0.0), -len(ix.mod_tests[m]), m))
    nodes = ranked[:MAX_NODES]
    if len(nodes) < 2:
        return ""
    edges = [(a, b) for (a, b) in ix.edge_tests if a in nodes and b in nodes and a != b]
    depth = layers(nodes, edges)
    cols: dict = {}
    for n in sorted(nodes):
        cols.setdefault(depth[n], []).append(n)
    pos = {n: (c * (NODE_W + COL_GAP) + 10, r * (NODE_H + ROW_GAP) + 10)
           for c, members in cols.items() for r, n in enumerate(members)}
    width = (max(cols) + 1) * (NODE_W + COL_GAP) - COL_GAP + 20
    height = max(len(m) for m in cols.values()) * (NODE_H + ROW_GAP) - ROW_GAP + 20
    total = sum(ix.mod_self.values()) or 1.0
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="How the modules call each other">',
           '<defs><marker id="ar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" '
           'orient="auto"><path d="M0 0L8 4L0 8z" class="arrow"/></marker></defs>']
    for a, b in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        sx, sy, ex, ey = x1 + NODE_W, y1 + NODE_H / 2, x2, y2 + NODE_H / 2
        mid = (sx + ex) / 2
        out.append(f'<path d="M{sx} {sy} C{mid} {sy} {mid} {ey} {ex - 2} {ey}" class="edge" marker-end="url(#ar)"/>')
    for n, (x, y) in pos.items():
        share = ix.mod_self.get(n, 0.0) / total
        out.append(f'<g><rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="8" class="node" '
                   f'style="--heat:{min(1.0, share * 1.2):.2f}"/>'
                   f'<text x="{x + NODE_W / 2}" y="{y + 17}" class="nm">{escape(n)}</text>'
                   f'<text x="{x + NODE_W / 2}" y="{y + 32}" class="sub">{pct(ix.mod_self.get(n, 0.0), total)} of time</text></g>')
    out.append("</svg>")
    hidden = len(ix.mod_tests) - len(nodes)
    note = f"<p class='hint'>{hidden} smaller modules are not drawn.</p>" if hidden > 0 else ""
    return "".join(out) + note


def use_cases(ix: Index) -> str:
    rows = []
    for t in ix.tests:
        icon = {"passed": "✓", "failed": "✕", "error": "✕", "skipped": "–"}.get(t["outcome"], "?")
        cls = "ok" if t["outcome"] == "passed" else "skip" if t["outcome"] == "skipped" else "bad"
        rows.append(f'<li><span class="st {cls}" title="{escape(t["outcome"])}">{icon}</span>'
                    f'<div><b>{escape(t["name"])}</b><div class="flow">{escape(sentence(t["edges"]))}</div></div></li>')
    return "<ul class='cases'>" + "".join(rows) + "</ul>"


def slow_parts(ix: Index) -> str:
    total = sum(ix.func_ms.values())
    if not total:
        return "<p class='hint'>No time was recorded for the tests' own actions.</p>"
    rows = []
    for (m, fn), ms in ix.func_ms.most_common(5):
        share = ms / total
        rows.append(f'<div class="bar"><span>{escape(m)}.{escape(fn)}</span>'
                    f'<i style="width:{max(2, share * 100):.0f}%"></i><b>{pct(ms, total)}</b></div>')
    return "".join(rows)


def not_covered(ix: Index, items: list | None) -> str:
    untouched = sorted(set(ix.modules) - set(ix.mod_tests))
    out = []
    if untouched:
        out.append(f"<p>{len(untouched)} of {len(ix.modules)} parts of the code are never run by a test: "
                   + ", ".join(f"<code>{escape(m)}</code>" for m in untouched[:12])
                   + ("…" if len(untouched) > 12 else "") + ".</p>")
    tested = {(m, f) for m, f in ix.func_tests}
    entries = [i for i in (items or []) if i["entry"] and (i["module"], i["name"]) not in tested]
    if entries:
        out.append("<p>Entry points no test uses: "
                   + ", ".join(f"<code>{escape(i['module'])}.{escape(i['qual'])}</code>" for i in entries[:8]) + ".</p>")
    return "".join(out) or "<p>Every part of the code is run by at least one test.</p>"


def failures(ix: Index) -> str:
    bad = ix.failing()
    if not bad:
        return "<p>Nothing fails.</p>"
    rows = []
    for t in bad[:10]:
        first = (error_lines(t["output"], 1) or ["(no error line captured)"])[0]
        rows.append(f"<li><b>{escape(t['name'])}</b><div class='flow'>{escape(first[:140])}</div></li>")
    return "<ul class='cases'>" + "".join(rows) + "</ul>"


AUDIENCES = {
    "stakeholders": ("how it works", "What the system does", "Points to raise"),
    "learn": ("architecture guide", "What the system does", "Where to start reading"),
    "interview": ("architecture walkthrough", "Use cases to walk through", "Talking points"),
}
TOP_FUNCS = 5


def parts(ix: Index) -> str:
    """Each module and its busiest functions: the 'what lives where' view an engineer learns from."""
    ranked = sorted(ix.mod_tests, key=lambda m: (-len(ix.mod_tests[m]), m))[:MAX_NODES]
    cards = []
    for m in ranked:
        funcs = sorted(((f, calls) for (mod, f), calls in ix.func_calls.items() if mod == m),
                       key=lambda fc: -fc[1])[:TOP_FUNCS]
        names = ", ".join(f"<code>{escape(f)}</code>" for f, _ in funcs) or "<span class='hint'>nothing recorded</span>"
        callers = sorted({a for (a, b) in ix.edge_tests if b == m and a != "entry"})
        used_by = ("used by " + ", ".join(escape(c) for c in callers)) if callers else "called straight from the tests"
        cards.append(f"<div class='part'><b>{escape(m)}</b><span class='hint'> · {len(ix.mod_tests[m])} {'test' if len(ix.mod_tests[m]) == 1 else 'tests'} · {used_by}</span>"
                     f"<div>{names}</div></div>")
    return "".join(cards)


def notes_html(notes: str) -> str:
    """Paragraphs, and lines that start with '- ' as a list."""
    out, items = [], []
    for line in notes.splitlines() + [""]:
        if line.startswith("- "):
            items.append(f"<li>{escape(line[2:])}</li>")
            continue
        if items:
            out.append("<ul class='notes'>" + "".join(items) + "</ul>")
            items = []
        if line.strip():
            out.append(f"<p>{escape(line)}</p>")
    return "".join(out)


def build(ix: Index, summary: str = "", items: list | None = None,
          audience: str = "stakeholders", notes: str = "") -> str:
    title_tail, cases_h, notes_h = AUDIENCES[audience]
    n, bad = len(ix.tests), len(ix.failing())
    passed = sum(1 for t in ix.tests if t["outcome"] == "passed")
    paras = "".join(f"<p>{escape(p)}</p>" for p in summary.split("\n\n") if p.strip())
    head = f'<section class="sum">{paras}</section>' if paras else ""
    stats = (f"<div class='stats'><div><b>{n}</b>use cases checked</div><div><b>{passed}</b>pass</div>"
             f"<div><b>{bad}</b>fail</div><div><b>{len(ix.modules)}</b>parts of the code</div></div>")
    dia = diagram(ix)
    when = datetime.date.today().isoformat()
    inside = (f"<section><h2>What lives where</h2><p class='hint'>Each part, how many tests run it, who calls it, "
              f"and its busiest functions.</p>{parts(ix)}</section>") if audience != "stakeholders" else ""
    tail = f"<section><h2>{notes_h}</h2>{notes_html(notes)}</section>" if notes.strip() else ""
    return TEMPLATE.format(
        title=escape(ix.data["project"]), tail_title=title_tail, cases_h=cases_h, inside=inside, tail=tail,
        when=when, head=head, stats=stats, cases=use_cases(ix),
        diagram=f"<section><h2>How the parts fit</h2><p class='hint'>An arrow means one part calls another. "
                f"Darker means more of the running time.</p>{dia}</section>" if dia else "",
        slow=slow_parts(ix), gaps=not_covered(ix, items), fails=failures(ix))


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}: {tail_title}</title>
<style>
:root{{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#f0883e;--ok:#3fb950;--bad:#f85149}}
@media (prefers-color-scheme:light){{:root{{--bg:#fff;--card:#f6f8fa;--line:#d0d7de;--fg:#1f2328;--mut:#59636e}}}}
@media print{{:root{{--bg:#fff;--card:#fff;--line:#d0d7de;--fg:#000;--mut:#444}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:32px 16px 64px}}h1{{margin:0;font-size:28px}}
h2{{font-size:18px;margin:36px 0 8px}}.hint,.when{{color:var(--mut);font-size:14px}}
section{{break-inside:avoid}}.sum{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 18px;margin:20px 0}}
.stats{{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}}.stats div{{flex:1 1 120px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;color:var(--mut);font-size:14px}}
.stats b{{display:block;font-size:26px;color:var(--fg)}}
.cases{{list-style:none;margin:0;padding:0}}.cases li{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--line)}}
.flow{{color:var(--mut);font-size:14px}}.st{{flex:none;width:22px;height:22px;border-radius:50%;text-align:center;line-height:22px;font-size:13px;color:#fff}}
.st.ok{{background:var(--ok)}}.st.bad{{background:var(--bad)}}.st.skip{{background:var(--mut)}}
svg{{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px}}
.node{{fill:color-mix(in srgb,var(--acc) calc(var(--heat)*80%),var(--card));stroke:var(--line)}}
.nm{{fill:var(--fg);font:600 12px system-ui;text-anchor:middle}}.sub{{fill:var(--mut);font:10px system-ui;text-anchor:middle}}
.edge{{fill:none;stroke:var(--mut);stroke-width:1.4;opacity:.8}}.arrow{{fill:var(--mut)}}
.bar{{display:grid;grid-template-columns:minmax(120px,240px) 1fr 52px;gap:10px;align-items:center;margin:6px 0;font-size:14px}}
.bar i{{display:block;height:10px;border-radius:5px;background:var(--acc)}}.bar b{{text-align:right}}
  .part{{padding:10px 0;border-bottom:1px solid var(--line)}}.notes{{padding-left:20px}}
code{{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:13px}}
footer{{margin-top:40px;color:var(--mut);font-size:13px}}
</style></head><body><main>
<h1>{title}: {tail_title}</h1><div class="when">Built from the project's own tests on {when}.</div>
{head}{stats}
<section><h2>{cases_h}</h2><p class="hint">Each line is something the tests make the system do, with the parts it uses.</p>{cases}</section>
{diagram}
{inside}
<section><h2>Where it spends its time</h2><p class="hint">Share of the running time while the tests do their work, by function.</p>{slow}</section>
<section><h2>What no test covers</h2>{gaps}</section>
<section><h2>What fails</h2>{fails}</section>
{tail}
<footer>Made with flowscope. A use case is a test. "No test covers it" means untested, not unused. Times are shares
measured with tracing on, which slows the code; read them as shares, not as seconds.</footer>
</main></body></html>
"""
