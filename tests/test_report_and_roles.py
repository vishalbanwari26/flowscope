from flowscope import hook, report


def teardown_function(_):
    hook.set_phase(None)


def test_constructors_and_builders_are_setup():
    for name in ("__init__", "add_request", "generate", "load_slices", "seed_data", "build_index"):
        assert hook.role_for(name) == "setup", name


def test_everything_else_is_action():
    for name in ("investigate", "detect_low_util", "resolve", "get_order", "percentile"):
        assert hook.role_for(name) == "action", name


def test_fixture_phase_is_always_setup():
    hook.set_phase("setup")
    assert hook.role_for("investigate") == "setup"
    hook.set_phase("call")
    assert hook.role_for("investigate") == "action"


def _ev(frm, to, func, role="action", ms=1.0):
    return {"from": frm, "to": to, "func": func, "role": role, "ms": ms}


def test_collapse_merges_only_identical_neighbours():
    steps = report.collapse([_ev("a", "b", "f"), _ev("a", "b", "f"), _ev("a", "c", "g"), _ev("a", "b", "f")])
    assert [(s["to"], s["n"]) for s in steps] == [("b", 2), ("c", 1), ("b", 1)]
    assert steps[0]["ms"] == 2.0


def test_setup_is_hidden_by_default_and_shown_on_request():
    result = {
        "name": "total is summed", "outcome": "passed",
        "events": [_ev("entry", "store", "add_row", "setup"), _ev("entry", "pipeline", "analyse")],
        "funcs": [{"mod": "store", "func": "add_row", "role": "setup", "calls": 1, "self_ms": 9.0},
                  {"mod": "pipeline", "func": "analyse", "role": "action", "calls": 1, "self_ms": 1.0}],
        "internal": [],
    }
    hidden = report.render(result)
    assert "1 setup calls hidden" in hidden and "store.add_row" not in hidden.split("Own time")[0]
    assert "100%" in hidden                  # shares are of the visible time only
    shown = report.render(result, show_setup=True)
    assert "[setup] entry -> store.add_row()" in shown


def test_time_formatting():
    assert report.fmt_ms(0.01) == "<0.1 ms"
    assert report.fmt_ms(1.26) == "1.3 ms"
    assert report.fmt_ms(48.7) == "49 ms"
    assert report.pct(0.2, 100) == "<1%" and report.pct(50, 100) == "50%"
