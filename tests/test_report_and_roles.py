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


def _ev(i, parent, to, func, role="action", ms=1.0, frm="entry"):
    return {"id": i, "parent": parent, "from": frm, "to": to, "func": func, "role": role, "ms": ms}


def test_tree_nests_calls_under_the_call_that_made_them_and_merges_repeats():
    events = [_ev(0, None, "pipeline", "analyse", ms=10),
              _ev(1, 0, "util", "total", frm="pipeline", ms=3),
              _ev(2, 0, "util", "total", frm="pipeline", ms=3),
              _ev(3, None, "triage", "triage", ms=2)]
    tree = report.build_tree(events)
    assert [(n["mod"], n["func"], n["n"]) for n in tree] == [("pipeline", "analyse", 1), ("triage", "triage", 1)]
    child = tree[0]["kids"][0]
    assert (child["mod"], child["func"], child["n"], child["ms"]) == ("util", "total", 2, 6.0)


def test_a_call_whose_parent_is_hidden_hangs_on_the_nearest_visible_ancestor():
    events = [_ev(0, None, "store", "add_row", role="setup"),
              _ev(1, 0, "util", "total", frm="store")]
    tree = report.build_tree(events, keep=lambda e: e["role"] != "setup")
    assert [(n["mod"], n["func"]) for n in tree] == [("util", "total")]


def test_a_deep_recursion_does_not_blow_up():
    events = [_ev(i, i - 1 if i else None, "m", "f", frm="m") for i in range(5000)]
    tree = report.build_tree(events)
    depth, node = 0, tree[0]
    while node["kids"]:
        depth, node = depth + 1, node["kids"][0]
    assert depth <= report.MAX_DEPTH


def _result(events, funcs=None):
    return {"name": "total is summed", "outcome": "passed", "events": events,
            "funcs": funcs or [], "internal": []}


def test_setup_is_hidden_by_default_and_shown_on_request():
    result = _result(
        [_ev(0, None, "store", "add_row", "setup", ms=9), _ev(1, None, "pipeline", "analyse", ms=1)],
        [{"mod": "store", "func": "add_row", "role": "setup", "calls": 1, "self_ms": 9.0},
         {"mod": "pipeline", "func": "analyse", "role": "action", "calls": 1, "self_ms": 1.0}])
    hidden = report.render(result)
    assert "1 setup calls hidden" in hidden and "store.add_row" not in hidden
    assert "pipeline.analyse()" in hidden and "100%" in hidden   # shares are of the visible time only
    assert "[setup] store.add_row()" in report.render(result, show_setup=True)


def test_a_test_with_only_setup_style_calls_still_shows_them():
    # e.g. "invalid budget rejected": the constructor is what is being tested
    result = _result([_ev(0, None, "config", "__init__", "setup")],
                     [{"mod": "config", "func": "__init__", "role": "setup", "calls": 1, "self_ms": 1.0}])
    out = report.render(result)
    assert "[setup] config.__init__()" in out
    assert "probably about one of them" in out and "hidden" not in out


def test_the_text_tree_indents_calls_made_inside_and_limits_depth():
    result = _result([_ev(0, None, "a", "one", ms=100), _ev(1, 0, "b", "two", frm="a", ms=10),
                      _ev(2, 1, "c", "three", frm="b", ms=1)])
    lines = report.render(result, depth=2).splitlines()
    two = next(l for l in lines if "b.two()" in l)
    assert two.startswith("    ") and "[+1 below]" in two          # one level in, deeper calls counted
    assert not any("c.three()" in l for l in lines)


def test_the_heavy_path_is_always_opened_up_past_the_depth_limit():
    # b is 60% of the time, so the call below it is shown even though depth=2 would hide it
    result = _result([_ev(0, None, "a", "one", ms=100), _ev(1, 0, "b", "two", frm="a", ms=60),
                      _ev(2, 1, "c", "three", frm="b", ms=55)])
    lines = report.render(result, depth=2).splitlines()
    assert any("c.three()" in l for l in lines)


def test_bottleneck_follows_the_heaviest_call_down_to_where_the_time_is_spent():
    result = _result([_ev(0, None, "a", "one", ms=100), _ev(1, 0, "b", "two", frm="a", ms=90),
                      _ev(2, 0, "d", "side", frm="a", ms=5), _ev(3, 1, "c", "three", frm="b", ms=20)])
    result["funcs"] = [{"mod": m, "func": f, "role": "action", "calls": 1, "self_ms": ms}
                       for m, f, ms in (("a", "one", 5.0), ("b", "two", 70.0), ("c", "three", 20.0), ("d", "side", 5.0))]
    out = report.render_bottleneck(result)
    path = out.split("Heaviest path")[1].split("The time ends up")[0]
    assert "a.one()" in path and "b.two()" in path     # 90 of 100: follow it
    assert "c.three()" not in path                      # 20 of 90 is under half: the time is b.two's own
    assert "b.two() itself: 70%" in out and "Most own time: b.two 70%" in out


def test_bottleneck_with_nothing_recorded_says_so():
    assert "no time to look at" in report.render_bottleneck(_result([]))


def test_time_formatting():
    assert report.fmt_ms(0.01) == "<0.1 ms"
    assert report.fmt_ms(1.26) == "1.3 ms"
    assert report.fmt_ms(48.7) == "49 ms"
    assert report.pct(0.2, 100) == "<1%" and report.pct(50, 100) == "50%"
