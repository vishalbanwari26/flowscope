"""JavaScript and TypeScript projects, with Jest and with Vitest.
Needs Node and `npm install` in examples/jsshop (Jest) and examples/tsshop-vitest (Vitest)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = str(ROOT / "src")


def _installed(name, tool):
    return bool(shutil.which("node") and (ROOT / "examples" / name / "node_modules" / ".bin" / tool).exists())


@pytest.fixture(params=[
    pytest.param("jsshop", id="jest", marks=pytest.mark.skipif(
        not _installed("jsshop", "jest"), reason="needs node and `npm install` in examples/jsshop")),
    pytest.param("tsshop-vitest", id="vitest", marks=pytest.mark.skipif(
        not _installed("tsshop-vitest", "vitest"), reason="needs node and `npm install` in examples/tsshop-vitest")),
])
def shop(request):
    return ROOT / "examples" / request.param


@pytest.fixture
def run(tmp_path, shop):
    def go(*args):
        env = {**os.environ, "PYTHONPATH": SRC, "FLOWSCOPE_CACHE": str(tmp_path / "cache")}
        return subprocess.run([sys.executable, "-m", "flowscope", *args, str(shop)], env=env,
                              capture_output=True, text=True, timeout=180)
    return go


def test_overview_finds_the_modules_and_the_slow_call(run):
    r = run("hld")
    assert r.returncode == 0, r.stderr
    for m in ("catalog", "orders", "pricing", "stock"):
        assert m in r.stdout
    assert "orders -> stock" in r.stdout and "pricing -> catalog" in r.stdout
    b = run("bottleneck")
    assert b.stdout.index("catalog.priceOf") < b.stdout.index("stock.reserve")


def test_gaps_lists_the_exported_function_no_test_runs(run):
    out = run("gaps").stdout
    assert "orders.cancel" in out and "src/orders.ts:" in out
    assert "orders.place" not in out                       # a test runs it


def test_brief_draws_the_calls_in_order(run, tmp_path):
    out = tmp_path / "p.html"
    r = run("brief", "--for", "learn", "--out", str(out))
    assert r.returncode == 0, r.stderr
    page = out.read_text()
    assert "1. place()" in page and "2. reserve()" in page and "4. priceOf()" in page
    assert "small order gets a total" in page


def test_one_test_view_says_it_is_not_there_yet(run):
    r = run("run", "small order")
    assert r.returncode != 0 and "JavaScript and TypeScript" in r.stderr
