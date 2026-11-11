"""A plain-text version of one run, for the terminal and for reading without a browser."""
from __future__ import annotations


def collapse(events: list) -> list:
    """Merge consecutive identical calls into one step."""
    steps: list = []
    for e in events:
        s = steps[-1] if steps else None
        if s and (s["from"], s["to"], s["func"], s["role"]) == (e["from"], e["to"], e["func"], e["role"]):
            s["n"] += 1
            s["ms"] += e.get("ms", 0.0)
        else:
            steps.append({"from": e["from"], "to": e["to"], "func": e["func"],
                          "role": e["role"], "n": 1, "ms": e.get("ms", 0.0)})
    return steps


def fmt_ms(v: float) -> str:
    if v < 0.05:
        return "<0.1 ms"
    return f"{v:.1f} ms" if v < 10 else f"{round(v)} ms"


def pct(v: float, total: float) -> str:
    p = 100 * v / total if total else 0
    return "<1%" if p < 1 else f"{round(p)}%"


def render(result: dict, show_setup: bool = False) -> str:
    keep = (lambda x: True) if show_setup else (lambda x: x["role"] != "setup")
    events = [e for e in result["events"] if keep(e)]
    funcs = [f for f in result["funcs"] if keep(f)]
    internal = [i for i in result["internal"] if keep(i)]
    total = sum(f["self_ms"] for f in funcs) or 1.0
    steps = collapse(events)

    lines = [f"{result['name']}  [{result['outcome']}]"]
    hidden = len(result["events"]) - len(events)
    lines.append(f"{len(events)} calls, {len(steps)} steps"
                 + (f"  ({hidden} setup calls hidden, use --setup to show)" if hidden else ""))
    lines.append("")
    for i, s in enumerate(steps, 1):
        tag = "[setup] " if s["role"] == "setup" else ""
        times = f"  x{s['n']}" if s["n"] > 1 else ""
        lines.append(f"  {i:>2}. {tag}{s['from']} -> {s['to']}.{s['func']}(){times}"
                     f"   {fmt_ms(s['ms'])} {pct(s['ms'], total)}")

    mods: dict = {}
    for f in funcs:
        mods[f["mod"]] = mods.get(f["mod"], 0.0) + f["self_ms"]
    if mods:
        lines += ["", "Own time by module (share of traced time):"]
        for m, ms in sorted(mods.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {m:<20} {pct(ms, total)}")

    inside: dict = {}
    for i in internal:
        if i["from"] != i["to"]:
            inside.setdefault(i["mod"], []).append(i)
    for m, edges in inside.items():
        lines += ["", f"Inside {m}:"]
        for i in edges:
            lines.append(f"  {i['from']} -> {i['to']}" + (f"  x{i['n']}" if i["n"] > 1 else ""))

    if result.get("output"):
        lines += ["", "pytest output (tail):", result["output"]]
    lines += ["", "Times are measured with tracing on, which slows the code. Read them as shares."]
    return "\n".join(lines)
