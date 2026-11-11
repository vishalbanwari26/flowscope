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


def action_edges(t: dict) -> list:
    """Module-to-module calls the test made, without the setup (fixtures, app start-up) that
    the saved edges include. Falls back to all edges for an older saved overview."""
    seq = t.get("seq")
    if seq is None:
        return t["edges"]
    counts: dict = {}
    for a, b, _f, _d in seq:
        counts[(a, b)] = counts.get((a, b), 0) + 1
    return [[a, b, n] for (a, b), n in counts.items()]


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
    box_h = height + 24                              # room for the captions under the boxes
    total = sum(ix.mod_self.values()) or 1.0
    out = [f'<svg viewBox="0 0 {width} {box_h}" role="img" aria-label="How the modules call each other">',
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
    last = max(cols)
    for c in cols:                                   # name the first and last column; the middle speaks for itself
        cap = "ENTRY" if c == 0 else "LOWEST LEVEL" if c == last else ""
        if cap and last > 0:
            out.append(f'<text x="{c * (NODE_W + COL_GAP) + 10}" y="{height + 14}" class="cap">{cap}</text>')
    out.append("</svg>")
    hidden = len(ix.mod_tests) - len(nodes)
    note = f"<p class='hint'>{hidden} smaller modules are not drawn.</p>" if hidden > 0 else ""
    return "".join(out) + note


GROUP_AT = 12     # more use cases than this are grouped by test file, closed unless one fails


def _case_rows(tests: list) -> str:
    """One row per use case. Tests that differ only by a [parameter] become one row."""
    merged: dict = {}
    for t in tests:
        base, _, rest = t["name"].partition("[")
        row = merged.setdefault(base, {"t": t, "outcomes": [], "params": []})
        row["outcomes"].append(t["outcome"])
        if rest:
            row["params"].append(rest.rstrip("]"))
    rows = []
    for base, row in merged.items():
        oc = row["outcomes"]
        worst = next((o for o in ("failed", "error") if o in oc), "passed" if "passed" in oc else oc[0])
        icon = {"passed": "✓", "failed": "✕", "error": "✕", "skipped": "–"}.get(worst, "?")
        cls = "ok" if worst == "passed" else "skip" if worst == "skipped" else "bad"
        label = escape(base.strip())
        if row["params"]:
            label += f' <span class="par">{escape(", ".join(row["params"]))}</span>'
        rows.append(f'<li><span class="st {cls}" title="{escape(worst)}">{icon}</span>'
                    f'<div><b>{label}</b><div class="flow">{escape(sentence(action_edges(row["t"])))}</div></div></li>')
    return "<ul class='cases'>" + "".join(rows) + "</ul>"


def use_cases(ix: Index) -> str:
    if len(ix.tests) <= GROUP_AT:
        return _case_rows(ix.tests)
    groups: dict = {}
    for t in ix.tests:
        groups.setdefault(t["file"], []).append(t)
    out = []
    for file, tests in groups.items():
        bad = sum(t["outcome"] in ("failed", "error") for t in tests)
        state = f"{bad} fail" if bad else "all pass" if all(t["outcome"] == "passed" for t in tests) else "mixed"
        name = file.split("/")[-1]
        out.append(f'<details class="grp"{" open" if bad else ""}><summary><b>{escape(name)}</b> '
                   f'<span class="par">{len(tests)} tests, {state}</span></summary>{_case_rows(tests)}</details>')
    return "".join(out)


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
    "stakeholders": ("how it works", "What the system does"),
    "learn": ("architecture guide", "Use cases"),
    "interview": ("architecture walkthrough", "Use cases"),
}
TOP_FUNCS = 5
SEQ_USE_CASES, SEQ_MAX_CALLS, SEQ_COL, SEQ_ROW = 3, 22, 150, 30


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
        n = len(ix.mod_tests[m])
        cards.append(f"<div class='part'><b>{escape(m)}</b><span class='hint'> · {n} {'test' if n == 1 else 'tests'}"
                     f" · {used_by}</span><div>{names}</div></div>")
    return "".join(cards)


def sequence(t: dict) -> str:
    """One use case as a sequence diagram: who calls whom, in the order it happened."""
    first: dict = {}
    for c in t.get("seq", []):
        if c[0] != c[1]:
            k = tuple(c[:3])
            first.setdefault(k, [c, 0])[1] += 1      # a call repeated in a loop is drawn once
    total = len(first)
    reps = {k: v[1] for k, v in first.items()}
    calls = [v[0] for v in first.values()][:SEQ_MAX_CALLS]
    if not calls:
        return ""
    who = []
    for a, b, _f, _d in calls:
        for m in ("test" if a == "entry" else a, b):
            if m not in who:
                who.append(m)
    x = {m: i * SEQ_COL + SEQ_COL / 2 for i, m in enumerate(who)}
    width, height = len(who) * SEQ_COL, 52 + len(calls) * SEQ_ROW + 14
    out = [f'<svg viewBox="0 0 {width} {height}" style="max-width:{max(width * 1.5, 480):.0f}px" '
           f'role="img" aria-label="Calls in order for {escape(t["name"])}">',
           '<defs><marker id="sa" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" '
           'orient="auto"><path d="M0 0L8 4L0 8z" class="arrow"/></marker></defs>']
    for m in who:
        out.append(f'<rect x="{x[m] - 56}" y="6" width="112" height="28" rx="6" class="node" style="--heat:0"/>'
                   f'<text x="{x[m]}" y="25" class="nm">{escape(m)}</text>'
                   f'<line x1="{x[m]}" y1="34" x2="{x[m]}" y2="{height - 6}" class="life"/>')
    for i, (a, b, fn, _d) in enumerate(calls):
        a0 = a
        a = "test" if a == "entry" else a
        y = 58 + i * SEQ_ROW + 8
        x1, x2 = x[a], x[b]
        out.append(f'<line x1="{x1}" y1="{y}" x2="{x2 - (6 if x2 > x1 else -6)}" y2="{y}" class="edge" marker-end="url(#sa)"/>'
                   f'<text x="{(x1 + x2) / 2}" y="{y - 5}" class="msg">{i + 1}. {escape(fn)}(){f" x{reps[(a0, b, fn)]}" if reps[(a0, b, fn)] > 1 else ""}</text>')
    out.append("</svg>")
    more = total - len(calls)
    note = f"<p class='hint'>{more} more different calls are not drawn.</p>" if more > 0 else ""
    return "".join(out) + note


def request_flows(ix: Index) -> str:
    """Sequence diagrams for the use cases that touch the most parts of the system."""
    ok = [t for t in ix.tests if t["outcome"] == "passed" and any(c[0] != c[1] for c in t.get("seq", []))]
    ok.sort(key=lambda t: -len({c[1] for c in t["seq"]}))
    blocks = [f"<h3>{escape(t['name'])}</h3><p class='hint'>{escape(sentence(action_edges(t)))}</p>{sequence(t)}"
              for t in ok[:SEQ_USE_CASES]]
    return "".join(blocks)


def _inline(text: str) -> str:
    """Escape, then turn `code` into <code>."""
    parts_ = escape(text).split("`")
    return "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts_))


def notes_html(notes: str) -> str:
    """'## Heading' starts a section, '- ' lines become a list, other lines are paragraphs, `code` is code."""
    out, items = [], []
    for line in notes.splitlines() + [""]:
        if line.startswith("- "):
            items.append(f"<li>{_inline(line[2:])}</li>")
            continue
        if items:
            out.append("<ul class='notes'>" + "".join(items) + "</ul>")
            items = []
        if line.startswith("## "):
            out.append(f"<h3>{_inline(line[3:])}</h3>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
    return "".join(out)


def _section(title: str, body: str, hint: str = "") -> str:
    return f"<section><h2>{title}</h2>{f'<p class=hint>{hint}</p>' if hint else ''}{body}</section>" if body else ""


def build(ix: Index, summary: str = "", items: list | None = None,
          audience: str = "stakeholders", notes: str = "") -> str:
    title_tail, cases_h = AUDIENCES[audience]
    n, bad = len(ix.tests), len(ix.failing())
    passed = sum(1 for t in ix.tests if t["outcome"] == "passed")
    paras = "".join(f"<p>{_inline(p)}</p>" for p in summary.split("\n\n") if p.strip())
    head = f'<section class="sum">{paras}</section>' if paras else ""
    stats = (f"<div class='stats'><div><b>{n}</b>use cases checked</div><div><b>{passed}</b>pass</div>"
             f"<div><b>{bad}</b>fail</div><div><b>{len(ix.modules)}</b>parts of the code</div></div>")
    dia = diagram(ix)
    arrow_hint = "An arrow means one part calls another. Darker means more of the running time."
    arch = _section("Architecture" if audience != "stakeholders" else "How the parts fit", dia, arrow_hint)
    flows = _section("Request flow", request_flows(ix),
                     "The calls between parts, in the order they happened. Calls inside one part are not drawn.")
    cases = _section(cases_h, use_cases(ix), "Each line is something the tests make the system do, with the parts it uses.")
    where = _section("What lives where", parts(ix), "Each part, how many tests run it, who calls it, and its busiest functions.")
    slow = _section("Where it spends its time", slow_parts(ix), "Share of the running time while the tests do their work, by function.")
    cover, fails = _section("What no test covers", not_covered(ix, items)), _section("What fails", failures(ix))
    written = f"<section class='written'>{notes_html(notes)}</section>" if notes.strip() else ""
    if audience == "stakeholders":
        body = [cases, arch, slow, cover, fails, _section("Points to raise", notes_html(notes)) if notes.strip() else ""]
    else:        # learn and interview: system design first, the numbers after
        body = [arch, flows, written, cases, where, slow, cover, fails]
    return TEMPLATE.format(title=escape(ix.data["project"]), tail_title=title_tail,
                           when=datetime.date.today().isoformat(), head=head, stats=stats, body="\n".join(body))


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}: {tail_title}</title>
<style>
:root{{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#f0883e;--ok:#3fb950;--bad:#f85149}}
@media (prefers-color-scheme:light){{:root{{--bg:#fff;--card:#f6f8fa;--line:#d0d7de;--fg:#1f2328;--mut:#59636e}}}}
@media print{{:root{{--bg:#fff;--card:#fff;--line:#d0d7de;--fg:#000;--mut:#444}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:32px 16px 64px}}h1{{margin:0;font-size:28px}}
h2{{font-size:18px;margin:36px 0 8px}}h3{{font-size:15px;margin:22px 0 4px}}.hint,.when{{color:var(--mut);font-size:14px}}
section{{break-inside:avoid}}.sum{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 18px;margin:20px 0}}
.stats{{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}}.stats div{{flex:1 1 120px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;color:var(--mut);font-size:14px}}
.stats b{{display:block;font-size:26px;color:var(--fg)}}
.cases{{list-style:none;margin:0;padding:0}}.cases li{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--line)}}
.flow{{color:var(--mut);font-size:14px}}.st{{flex:none;width:22px;height:22px;border-radius:50%;text-align:center;line-height:22px;font-size:13px;color:#fff}}
.par{{color:var(--mut);font-size:13px;font-weight:400}}.grp{{border-bottom:1px solid var(--line);padding:6px 0}}.grp>summary{{cursor:pointer;padding:6px 0}}.grp .cases{{margin-left:8px}}
.st.ok{{background:var(--ok)}}.st.bad{{background:var(--bad)}}.st.skip{{background:var(--mut)}}
svg{{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px}}
.node{{fill:color-mix(in srgb,var(--acc) calc(var(--heat)*80%),var(--card));stroke:var(--line)}}
.nm{{fill:var(--fg);font:600 12px system-ui;text-anchor:middle}}.sub{{fill:var(--mut);font:10px system-ui;text-anchor:middle}}
.cap{{fill:var(--mut);font:600 9px system-ui;letter-spacing:.08em}}.msg{{fill:var(--fg);font:11px ui-monospace,monospace;text-anchor:middle}}
.life{{stroke:var(--line);stroke-dasharray:4 4}}
.edge{{fill:none;stroke:var(--mut);stroke-width:1.4;opacity:.8}}.arrow{{fill:var(--mut)}}
.bar{{display:grid;grid-template-columns:minmax(120px,240px) 1fr 52px;gap:10px;align-items:center;margin:6px 0;font-size:14px}}
.bar i{{display:block;height:10px;border-radius:5px;background:var(--acc)}}.bar b{{text-align:right}}
.part{{padding:10px 0;border-bottom:1px solid var(--line)}}.notes{{padding-left:20px;margin:4px 0}}
.written{{margin-top:8px}}.written h3{{font-size:17px;margin:30px 0 6px;padding-top:6px;border-top:1px solid var(--line)}}
code{{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:13px}}
footer{{margin-top:40px;color:var(--mut);font-size:13px}}
</style></head><body><main>
<h1>{title}: {tail_title}</h1><div class="when">Built from the project's own tests on {when}.</div>
{head}{stats}
{body}
<footer>Made with flowscope. A use case is a test. "No test covers it" means untested, not unused. Times are shares
measured with tracing on, which slows the code; read them as shares, not as seconds.</footer>
</main></body></html>
"""
