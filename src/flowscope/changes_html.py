"""The behavior diff as one page: a verdict, what to read first, and each use case before and
after, side by side, with the calls lined up like a text diff."""
from __future__ import annotations

import datetime
from html import escape

FOLD_AT = 6          # a run of unchanged calls longer than this is folded
FIRST_LABEL = {"broke": "BROKE", "blind": "NO TEST", "edge": "NEW LINK", "changed": "CHANGED", "api": "API"}
BADGE = {"broke": "BROKE", "changed": "CHANGED", "new": "NEW", "fixed": "FIXED", "removed": "REMOVED"}


def _cell(row, kind: str, side: str) -> str:
    if row is None:
        return '<div class="c empty"></div>'
    who = "test" if row[0] == "entry" else row[0]
    n = f'<i>×{row[4]}</i>' if row[4] > 1 else ""
    cls = {"same": "same", "count": "count", "del": "del", "add": "add",
           "chg": "del" if side == "l" else "add"}[kind]
    return (f'<div class="c {cls}"><span style="margin-left:{min(row[3], 5) * 14}px">{escape(who)} → '
            f'<b>{escape(row[1])}.{escape(row[2])}</b></span>{n}</div>')


def _fold(rows: list) -> list:
    """Turn long runs of unchanged rows into one 'N unchanged calls' marker."""
    out, run = [], []

    def flush():
        if len(run) > FOLD_AT:
            out.extend(run[:2])
            out.append(("fold", len(run) - 4))
            out.extend(run[-2:])
        else:
            out.extend(run)
        run.clear()

    for r in rows:
        if r[2] == "same":
            run.append(r)
        else:
            flush()
            out.append(r)
    flush()
    return out


def _grid(rows: list) -> str:
    """The rows as pairs of cells in one grid, so the two sides always line up."""
    cells = []
    for r in _fold(rows):
        if r[0] == "fold":
            note = f'<div class="c fold">{r[1]} unchanged calls</div>'
            cells += [note, note]
        else:
            cells += [_cell(r[0], r[2], "l"), _cell(r[1], r[2], "r")]
    return "".join(cells)


def _pill(outcome) -> str:
    if outcome is None:
        return '<span class="pill gone">not there</span>'
    ok = outcome == "passed"
    return f'<span class="pill {"ok" if ok else "skip" if outcome == "skipped" else "bad"}">{"passes" if ok else escape(outcome)}</span>'


def _card(c: dict, base: str, head: str, i: int) -> str:
    st = c["status"]
    rows = c["rows"]
    cut = len(rows) - 10 if c["status"] in ("new", "removed") and len(rows) > 14 else 0
    if cut:                                           # a whole new or removed test: show how it starts
        rows = rows[:10]
    body = _grid(rows) if rows else '<div class="c fold">no calls between modules</div>' * 2
    if cut:
        body += f'<div class="c fold">{cut} more calls</div>' * 2
    if c.get("inside"):                               # calls that stay inside one module: counted, not drawn as arrows
        body += '<div class="c fold">inside the modules</div>' * 2
        for m, f, x, y in c["inside"]:
            kind = "add" if not x else "del" if not y else "count"
            name = f"{escape(m)}.<b>{escape(f)}</b>"
            body += (f'<div class="c {"empty" if kind == "add" else kind}"><span>{name}</span><i>×{x}</i></div>'
                     f'<div class="c {"empty" if kind == "del" else kind}"><span>{name}</span><i>×{y}</i></div>')
    says = "".join(f"<li>{escape(p)}</li>" for p in c["phrases"][:6])
    says = f'<ul class="says">{says}</ul>' if says else ""
    more = ""
    if c.get("same_as"):
        names = "".join(f"<li>{escape(n)}</li>" for n in c["same_as"])
        more = (f'<details class="more"><summary>The same first change in {len(c["same_as"])} more '
                f'behavior{"s" if len(c["same_as"]) > 1 else ""}</summary><p class="hint">Same first change: {escape(c["phrases"][0])}. '
                f'The calls around it can differ slightly.</p><ul>{names}</ul></details>')
    err = f'<pre class="err">{escape(c["error"].strip().splitlines()[0][:200])}</pre>' if c.get("error", "").strip() else ""
    return (f'<article class="card {st}" id="c{i}"><header><span class="badge {st}">{BADGE.get(st, st.upper())}</span>'
            f'<h3>{escape(c["name"])}</h3><span class="file">{escape(c["file"])}</span></header>{says}{err}'
            f'<div class="side"><div class="lab">BEFORE <em>{escape(base)}</em> {_pill(c["before"])}</div>'
            f'<div class="lab">AFTER <em>{escape(head)}</em> {_pill(c["after"])}</div>{body}</div>'
            f'{more}<div class="why" contenteditable="true" data-ph="Why did this change? The author fills this in."></div></article>')


def _first(r: dict, ids: dict) -> str:
    if not r["first"]:
        return ""
    items = []
    for n, x in enumerate(r["first"], 1):
        link = f'#c{ids[x["id"]]}' if x.get("id") in ids else ""
        text = escape(x["text"])
        text = f'<a href="{link}">{text}</a>' if link else text
        items.append(f'<li><span class="k {x["kind"]}">{FIRST_LABEL[x["kind"]]}</span><span>{text}</span></li>')
    return f'<section class="first"><h2>Read these first</h2><ol>{"".join(items)}</ol></section>'


def _drift(r: dict) -> str:
    chips = [f'<span class="chip add">+ {escape(a)} → {escape(b)}</span>' for a, b in r["new_edges"]]
    chips += [f'<span class="chip del">− {escape(a)} → {escape(b)}</span>' for a, b in r["gone_edges"]]
    chips += [f'<span class="chip add">+ module {escape(m)}</span>' for m in r["new_modules"]]
    chips += [f'<span class="chip del">− module {escape(m)}</span>' for m in r["gone_modules"]]
    if not chips:
        return ""
    return ('<section><h2>Architecture drift</h2><p class="hint">Which module calls which, compared with the base. '
            f'A new arrow is a new dependency.</p><div class="chips">{"".join(chips)}</div></section>')


def _blind(r: dict) -> str:
    if not r["blind"]:
        return ""
    rows = "".join(f'<li><code>{escape(b["module"])}.{escape(b["name"])}</code> <span class="file">{escape(b["where"])}'
                   f'  {b["size"]} lines{"  entry point" if b["entry"] else ""}</span></li>' for b in r["blind"][:20])
    return ('<section><h2>Changed, and no test runs it</h2><p class="hint">These functions have changed lines and none of the '
            f'tests reach them. Nobody has seen them work.</p><ul class="nolist">{rows}</ul></section>')


def _api(r: dict) -> str:
    chips = [f'<span class="chip add">+ {escape(m)}.{escape(q)}</span>' for m, q in r["added_api"]]
    chips += [f'<span class="chip del">− {escape(m)}.{escape(q)}</span>' for m, q in r["removed_api"]]
    if not chips:
        return ""
    return f'<section><h2>Public functions</h2><div class="chips">{"".join(chips)}</div></section>'


def _same(r: dict) -> str:
    same = [c for c in r["cases"] if c["status"] == "same"]
    if not same:
        return ""
    names = "".join(f"<li>{escape(c['name'])}</li>" for c in same)
    return (f'<details class="unch"><summary>{len(same)} behaviors did not change</summary><ul>{names}</ul></details>')


def hero(r: dict) -> tuple:
    """The big sentence and the count chips."""
    n = r["counts"]
    moved = sum(n.get(k, 0) for k in BADGE)
    if not moved and not r["blind"]:
        big = "No behavior changed."
    elif n.get("broke"):
        big = f'{n["broke"]} behavior{"s" if n["broke"] > 1 else ""} broke.'
    else:
        big = f'{moved} behavior{"s" if moved != 1 else ""} moved.' if moved else f'{len(r["blind"])} changes nobody has seen run.'
    chips = [(n.get("broke", 0), "broke", "broke"), (n.get("changed", 0), "changed", "changed"),
             (n.get("new", 0), "new", "new"), (n.get("fixed", 0), "fixed", "fixed"),
             (n.get("removed", 0), "removed", "removed"), (len(r["blind"]), "no test", "blind"),
             (n.get("same", 0), "unchanged", "same")]
    return big, "".join(f'<div class="stat {k}"><b>{v}</b>{label}</div>' for v, label, k in chips if v or k == "same")


def build(r: dict, base_label: str, head_label: str) -> str:
    big, stats = hero(r)
    ids = {c["id"]: i for i, c in enumerate(r["cases"])}
    shown = [c for c in r["cases"] if c["status"] != "same" and not c.get("dup")]
    base_short = base_label.split(" ")[0]
    cards = "".join(_card(c, base_short, head_label, ids[c["id"]]) for c in shown)
    body = [_first(r, ids), f'<section><h2>Behaviors, before and after</h2><p class="hint">Each side is a run of the same test. '
            f'Calls are lined up like a text diff. Red is gone, green is new, amber is a count that changed.</p>{cards}</section>'
            if shown else "", _same(r), _drift(r), _blind(r), _api(r)]
    total = sum(r["counts"].values())
    return (TEMPLATE.replace("{{title}}", escape(r["project"])).replace("{{big}}", escape(big))
            .replace("{{base}}", escape(base_label)).replace("{{head}}", escape(head_label))
            .replace("{{total}}", str(total)).replace("{{files}}", str(r["files_changed"]))
            .replace("{{stats}}", stats).replace("{{body}}", "\n".join(b for b in body if b))
            .replace("{{when}}", datetime.date.today().isoformat()))


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}}: behavior diff</title>
<style>
:root{--bg:#0b0f14;--card:#141a22;--line:#27313d;--fg:#e8eef5;--mut:#8b98a8;--red:#ff5d6c;--grn:#3ddc84;--amb:#ffb84d;--blu:#5aa9ff;--pur:#b98cff;
--redb:#3a1b21;--grnb:#143324;--ambb:#3a2d14}
@media (prefers-color-scheme:light){:root{--bg:#fff;--card:#f6f8fa;--line:#d0d7de;--fg:#1f2328;--mut:#59636e;--red:#cf222e;--grn:#1a7f37;--amb:#9a6700;--blu:#0969da;--pur:#8250df;--redb:#ffebe9;--grnb:#dafbe1;--ambb:#fff8c5}}
@media print{:root{--bg:#fff;--card:#fff;--line:#d0d7de;--fg:#000;--mut:#444;--redb:#ffebe9;--grnb:#dafbe1;--ambb:#fff8c5}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:36px 16px 72px}
.eyebrow{font:700 12px ui-monospace,monospace;letter-spacing:.18em;color:var(--mut)}
h1{font-size:clamp(34px,7vw,64px);line-height:1.04;margin:8px 0 10px;letter-spacing:-.02em;
background:linear-gradient(90deg,var(--fg),var(--amb) 70%,var(--red));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{color:var(--mut);font-size:15px}.sub b{color:var(--fg);font-weight:600}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0 8px}
.stat{flex:1 1 110px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;color:var(--mut);font-size:13px;border-top:3px solid var(--line)}
.stat b{display:block;font-size:30px;color:var(--fg);line-height:1.1}
.stat.broke{border-top-color:var(--red)}.stat.changed{border-top-color:var(--amb)}.stat.new{border-top-color:var(--blu)}
.stat.fixed{border-top-color:var(--grn)}.stat.blind{border-top-color:var(--pur)}.stat.removed{border-top-color:var(--mut)}
h2{font-size:20px;margin:44px 0 6px}.hint{color:var(--mut);font-size:14px;margin:0 0 14px}
.first ol{list-style:none;margin:10px 0 0;padding:0;counter-reset:n}
.first li{display:flex;gap:12px;align-items:baseline;padding:11px 14px;background:var(--card);border:1px solid var(--line);border-radius:10px;margin:8px 0;counter-increment:n}
.first li:before{content:counter(n);font:700 13px ui-monospace,monospace;color:var(--mut);width:16px;flex:none}
.first a{color:var(--fg);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px}
.k{flex:none;font:700 11px ui-monospace,monospace;letter-spacing:.08em;padding:2px 8px;border-radius:99px;color:#0b0f14}
.k.broke{background:var(--red)}.k.blind{background:var(--pur)}.k.edge{background:var(--blu)}.k.changed{background:var(--amb)}.k.api{background:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:16px 0;border-left:4px solid var(--line)}
.card.broke{border-left-color:var(--red)}.card.changed{border-left-color:var(--amb)}.card.new{border-left-color:var(--blu)}.card.fixed{border-left-color:var(--grn)}
.card header{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.card h3{margin:0;font-size:17px}
.badge{font:700 11px ui-monospace,monospace;letter-spacing:.08em;padding:3px 9px;border-radius:99px;color:#0b0f14;background:var(--mut)}
.badge.broke{background:var(--red)}.badge.changed{background:var(--amb)}.badge.new{background:var(--blu)}.badge.fixed{background:var(--grn)}
.file{color:var(--mut);font:12px ui-monospace,monospace;margin-left:auto}
.says{margin:10px 0 4px;padding-left:20px;color:var(--fg);font-size:14.5px}.says li{margin:2px 0}
.err{background:var(--redb);color:var(--red);border-radius:8px;padding:8px 10px;font-size:12.5px;white-space:pre-wrap;margin:10px 0}
.side{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:10px;margin-top:12px}
.lab{font:700 11px ui-monospace,monospace;letter-spacing:.1em;color:var(--mut);margin-bottom:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.lab em{font-style:normal;font-weight:400;letter-spacing:0;text-transform:none;opacity:.8}
.pill{font:600 11px system-ui;letter-spacing:0;padding:1px 8px;border-radius:99px;border:1px solid var(--line)}
.pill.ok{color:var(--grn);border-color:var(--grn)}.pill.bad{color:var(--red);border-color:var(--red)}.pill.gone{color:var(--mut)}
.c{font:12.5px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;padding:5px 9px;border-radius:6px;margin:2px 0;display:flex;justify-content:space-between;gap:8px;min-height:27px;overflow:hidden}
.c span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.c i{font-style:normal;color:var(--mut)}
.c.same{color:var(--mut)}.c.del{background:var(--redb);color:var(--red)}.c.add{background:var(--grnb);color:var(--grn)}
.c.count{background:var(--ambb);color:var(--amb)}.c.empty{background:transparent}.c.fold{color:var(--mut);font-style:italic;justify-content:center;border:1px dashed var(--line)}
.why{margin-top:12px;border:1px dashed var(--line);border-radius:8px;padding:8px 10px;color:var(--fg);font-size:14px;min-height:38px}
.why:empty:before{content:attr(data-ph);color:var(--mut)}
.chips{display:flex;flex-wrap:wrap;gap:8px}.chip{font:13px ui-monospace,monospace;padding:4px 10px;border-radius:99px}
.chip.add{background:var(--grnb);color:var(--grn)}.chip.del{background:var(--redb);color:var(--red)}
.nolist{list-style:none;padding:0;margin:0}.nolist li{padding:9px 0;border-bottom:1px solid var(--line)}
code{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:13px}
.more{margin-top:10px;color:var(--mut);font-size:14px}.more summary{cursor:pointer}.more ul{margin:6px 0}
.unch{margin-top:28px;color:var(--mut)}.unch summary{cursor:pointer}.unch ul{font-size:14px}
footer{margin-top:56px;color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:16px}
footer a{color:var(--fg)}
@media (max-width:700px){.file{margin-left:0}.c{font-size:11px;padding:4px 6px}}
</style></head><body><main>
<div class="eyebrow">BEHAVIOR DIFF · {{title}}</div>
<h1>{{big}}</h1>
<div class="sub"><b>{{base}}</b> → <b>{{head}}</b> · {{total}} behaviors checked · {{files}} files changed · {{when}}</div>
<div class="stats">{{stats}}</div>
{{body}}
<footer>Made with <a href="https://github.com/vishalbanwari26/flowscope">flowscope</a>. A behavior is a test run with tracing on.
This page shows what the tests ran, not whether the change is right or why it was made. Code no test runs cannot appear
here except under "changed, and no test runs it". Times are not compared as seconds, only as shares.</footer>
</main></body></html>
"""
