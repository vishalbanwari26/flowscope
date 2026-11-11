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
    # a call inside one module is counted, not replayed
    assert {"mod": "pipeline", "from": "analyse", "to": "_score", "role": "action", "n": 1} in data["internal"]
    # self times add up per function, and the test files are not modules
    assert {f["mod"] for f in data["funcs"]} == {"store", "pipeline", "util"}


def test_failure_and_skip_are_reported_as_such(project):
    failed = json.loads(flowscope("run", "wrong total", str(project), "--json").stdout)
    assert failed["outcome"] == "failed" and "assert" in failed["output"]
    skipped = json.loads(flowscope("run", "skipped one", str(project), "--json").stdout)
    assert skipped["outcome"] == "skipped" and not skipped["passed"]


def test_text_report_hides_setup(project):
    out = flowscope("run", "total is summed", str(project)).stdout
    assert "entry -> pipeline.analyse()" in out
    assert "3 setup calls hidden" in out and "store.add_row" not in out
    assert "Inside pipeline:" in out and "analyse -> _score" in out


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
    r = launcher(project, "total", "is", "summed")
    assert r.returncode == 0, r.stderr
    assert "entry -> pipeline.analyse()" in r.stdout and "[passed]" in r.stdout


def test_launcher_prefers_the_projects_own_venv(project):
    py = project / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    marker = project / "venv-was-used"
    py.write_text(f'#!/bin/sh\ntouch "{marker}"\nexec "{sys.executable}" "$@"\n')
    py.chmod(0o755)
    r = launcher(project, "total is summed", env_extra={"FLOWSCOPE_PYTHON": ""})
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
