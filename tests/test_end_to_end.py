"""Run the real command line on a tiny project built in a temp folder."""
import http.client
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

FILES = {
    "store.py": '''
class Store:
    def __init__(self):
        self.rows = []

    def add_row(self, x):
        self.rows.append(x)
''',
    "util.py": '''
def total(rows):
    return sum(rows)
''',
    "pipeline.py": '''
from util import total


def analyse(store):
    return _score(store.rows)


def _score(rows):
    return total(rows)
''',
    "tests/test_flow.py": '''
import pytest
from pipeline import analyse
from store import Store


def test_total_is_summed():
    s = Store()
    s.add_row(1)
    s.add_row(2)
    assert analyse(s) == 3


def test_wrong_total_fails():
    s = Store()
    s.add_row(1)
    assert analyse(s) == 99


@pytest.mark.skip(reason="not now")
def test_skipped_one():
    assert analyse(Store()) == 0
''',
}


@pytest.fixture()
def project(tmp_path):
    for rel, text in FILES.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return tmp_path


SRC = str(Path(__file__).resolve().parents[1] / "src")


def flowscope(*args):
    # PYTHONPATH, not an installed copy, so these tests do not depend on how the package got here
    env = {**os.environ, "PYTHONPATH": SRC}
    return subprocess.run([sys.executable, "-m", "flowscope", *args], env=env,
                          capture_output=True, text=True, timeout=120)


def test_list_finds_every_test(project):
    r = flowscope("list", str(project))
    assert r.returncode == 0, r.stderr
    ids = [line.split("\t")[0] for line in r.stdout.splitlines()]
    assert ids == ["tests/test_flow.py::test_total_is_summed", "tests/test_flow.py::test_wrong_total_fails",
                   "tests/test_flow.py::test_skipped_one"]


def test_flow_is_split_into_setup_and_action_and_timed(project):
    r = flowscope("run", "total is summed", str(project), "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["outcome"] == "passed"
    calls = [(e["role"], e["from"], e["to"], e["func"]) for e in data["events"]]
    assert calls == [
        ("setup", "entry", "store", "__init__"),
        ("setup", "entry", "store", "add_row"),
        ("setup", "entry", "store", "add_row"),
        ("action", "entry", "pipeline", "analyse"),
        ("action", "pipeline", "util", "total"),
    ]
    assert all(e["ms"] >= 0 for e in data["events"])
    # each call knows which call made it, so the calls form a tree
    by_func = {e["func"]: e for e in data["events"] if e["role"] == "action"}
    assert by_func["analyse"]["parent"] is None and by_func["total"]["parent"] == by_func["analyse"]["id"]
    assert [n["func"] for n in data["tree"]["action"]] == ["analyse"]
    assert [k["func"] for k in data["tree"]["action"][0]["kids"]] == ["total"]
    # a call inside one module is counted, not replayed
    assert {"mod": "pipeline", "from": "analyse", "to": "_score", "role": "action", "n": 1} in data["internal"]
    # self times add up per function, and the test files are not modules
    assert {f["mod"] for f in data["funcs"]} == {"store", "pipeline", "util"}


def test_dataclass_methods_are_not_invisible(tmp_path):
    # a dataclass __init__ is generated from a string, so its file name is "<string>"
    (tmp_path / "models.py").write_text(
        "from dataclasses import dataclass\n\n@dataclass\nclass Point:\n    x: int\n    y: int = 0\n")
    (tmp_path / "geometry.py").write_text(
        "from models import Point\n\ndef shifted(x):\n    return Point(x + 1)\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_g.py").write_text(
        "from geometry import shifted\n\ndef test_shift():\n    assert shifted(1).x == 2\n")
    data = json.loads(flowscope("run", "shift", str(tmp_path), "--json").stdout)
    calls = [(e["from"], e["to"], e["func"]) for e in data["events"]]
    assert ("geometry", "models", "__init__") in calls


def test_failure_and_skip_are_reported_as_such(project):
    failed = json.loads(flowscope("run", "wrong total", str(project), "--json").stdout)
    assert failed["outcome"] == "failed" and "assert" in failed["output"]
    skipped = json.loads(flowscope("run", "skipped one", str(project), "--json").stdout)
    assert skipped["outcome"] == "skipped" and not skipped["passed"]


def test_text_report_hides_setup(project):
    out = flowscope("run", "total is summed", str(project)).stdout
    assert "pipeline.analyse()" in out and "util.total()" in out
    assert "3 setup calls hidden" in out and "store.add_row" not in out
    assert "flowscope lld <module>" in out            # inside a module is a separate question


def test_ambiguous_or_unknown_name_is_an_error_not_a_guess(project):
    r = flowscope("run", "total", str(project))
    assert r.returncode != 0 and "be more specific" in r.stderr
    r = flowscope("run", "nothing like this", str(project))
    assert r.returncode != 0 and "no use case matches" in r.stderr


def test_server_needs_the_token_and_a_local_host():
    from flowscope.server import make_server
    server = make_server(".", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        def status(path, host=None):
            c = http.client.HTTPConnection("127.0.0.1", port)
            c.request("GET", path, headers={"Host": host or f"localhost:{port}"})
            return c.getresponse().status

        assert status("/api/modules") == 403
        assert status("/api/modules?t=wrong") == 403
        assert status(f"/api/modules?t={server.token}", host="evil.example.com") == 403
        assert status(f"/api/modules?t={server.token}") == 200
        assert status(f"/?t={server.token}") == 200
    finally:
        server.shutdown()
        server.server_close()


def launcher(project, *args, env_extra=None, cwd=None):
    script = Path(__file__).resolve().parents[1] / "bin" / "flow"
    env = {**os.environ, "FLOWSCOPE_PYTHON": sys.executable, **(env_extra or {})}
    env.pop("PYTHONPATH", None)
    return subprocess.run([str(script), *args], cwd=cwd or project, env=env,
                          capture_output=True, text=True, timeout=120)


def test_launcher_prints_a_flow_without_installing_anything(project):
    # flowscope is read from the plugin folder through PYTHONPATH, not from site-packages
    r = launcher(project, "run", "total is summed")
    assert r.returncode == 0, r.stderr
    assert "pipeline.analyse()" in r.stdout and "[passed]" in r.stdout


def test_launcher_prefers_the_projects_own_venv(project):
    py = project / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    marker = project / "venv-was-used"
    py.write_text(f'#!/bin/sh\ntouch "{marker}"\nexec "{sys.executable}" "$@"\n')
    py.chmod(0o755)
    r = launcher(project, "run", "total is summed", env_extra={"FLOWSCOPE_PYTHON": ""})
    assert r.returncode == 0, r.stderr
    assert marker.exists()


def test_missing_pytest_gives_a_clear_message(monkeypatch):
    monkeypatch.setitem(sys.modules, "pytest", None)           # makes "import pytest" fail
    monkeypatch.delitem(sys.modules, "flowscope.runner", raising=False)
    import flowscope
    monkeypatch.delattr(flowscope, "runner", raising=False)    # else "from . import runner" reuses it
    from flowscope import cli
    with pytest.raises(SystemExit) as e:
        cli._runner()
    assert "pytest is not installed" in str(e.value)


# ---- the project-wide commands: hld, lld, scope, debug ----

@pytest.fixture()
def cached(tmp_path_factory, monkeypatch):
    # keep the saved overviews out of the real home directory
    monkeypatch.setenv("FLOWSCOPE_CACHE", str(tmp_path_factory.mktemp("cache")))


def test_hld_ranks_modules_and_shows_the_main_links(project, cached):
    r = flowscope("hld", str(project))
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "3 tests (1 fail), 3 modules" in out
    assert "Modules, by how many tests reach them:" in out
    assert "pipeline" in out and "util" in out and "Main links" in out and "pipeline -> util" in out


def test_lld_lists_the_functions_that_ran_and_who_called_them(project, cached):
    out = flowscope("lld", "pipeline", str(project)).stdout
    assert "pipeline: reached by 2 of 3 tests" in out
    assert "analyse" in out and "2 tests" in out and "called by outside" in out
    assert "_score" in out and "called by pipeline.analyse" in out
    assert "It calls into: util" in out


def test_scope_lists_the_tests_that_reach_a_function_with_their_result(project, cached):
    out = flowscope("scope", "util.total", str(project)).stdout
    assert "Tests that reach util.total (2 of 3):" in out
    assert "[ok  ] test_flow.py: total is summed" in out and "[FAIL] test_flow.py: wrong total fails" in out


def test_scope_says_untested_and_not_unused(project, cached):
    out = flowscope("scope", "store.nothing", str(project)).stdout
    assert "No test runs" in out
    (project / "orphan.py").write_text("def lonely():\n    return 1\n")
    out = flowscope("scope", "orphan", str(project)).stdout
    assert "Nothing called" in out or "No test runs" in out


def test_debug_lists_failing_tests_with_the_reason(project, cached):
    out = flowscope("debug", str(project)).stdout          # one folder argument means "this project"
    assert "1 of 3 tests fail:" in out and "wrong total fails" in out and "assert" in out


def test_debug_one_test_shows_the_error_and_the_last_calls(project, cached):
    out = flowscope("debug", "wrong total", str(project)).stdout
    assert "[failed]" in out and "What went wrong:" in out
    assert "util.total()" in out.split("The last calls")[1]
    assert "[passed]" not in out


def test_debug_of_a_passing_test_says_so(project, cached):
    out = flowscope("debug", "total is summed", str(project)).stdout
    assert "This test passes" in out


def test_the_overview_is_saved_and_rebuilt_when_the_code_changes(project, cached):
    first = flowscope("hld", str(project))
    assert "running 3 tests once" in first.stderr
    again = flowscope("hld", str(project))
    assert "running" not in again.stderr and again.stdout == first.stdout      # from the saved copy
    (project / "util.py").write_text("def total(rows):\n    return sum(rows) + 0\n")
    assert "running 3 tests once" in flowscope("hld", str(project)).stderr     # an edit invalidates it


def test_bottleneck_ranks_functions_and_names_the_slowest_tests(project, cached):
    out = flowscope("bottleneck", str(project)).stdout
    assert "Where the time goes across 3 tests" in out
    assert "pipeline.analyse" in out and "util.total" in out
    assert "Slowest tests" in out and "total is summed" in out
    assert "outside the project" in out              # the caution about waiting on other things


def test_bottleneck_of_one_test_shows_the_heaviest_path(project, cached):
    out = flowscope("bottleneck", "total is summed", str(project)).stdout
    assert "Heaviest path" in out and "pipeline.analyse()" in out and "Most own time:" in out


def test_gaps_with_no_tests_lists_entry_points_first(tmp_path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\n\n"
        "def helper(x):\n    return x\n\n"
        "def _private():\n    pass\n\n"
        "@app.route('/orders')\ndef orders():\n    return 'ok'\n\n"
        "class Cart:\n    def add(self, item):\n        pass\n")
    r = flowscope("gaps", str(tmp_path))
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("No tests.")
    assert "entry" in lines[1] and "app.orders" in lines[1]       # the route comes first
    assert "app.helper" in r.stdout and "app.Cart.add" in r.stdout
    assert "_private" not in r.stdout


def test_gaps_with_tests_leaves_out_what_the_tests_run(project, cached):
    r = flowscope("gaps", str(project))
    assert r.returncode == 0, r.stderr
    assert "analyse" not in r.stdout and "total" not in r.stdout   # both are run
    assert "store.Store.add_row" not in r.stdout                   # run, in setup
