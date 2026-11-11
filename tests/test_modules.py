from pathlib import Path

import pytest

from flowscope.modules import ModuleMap, is_project_file


@pytest.mark.parametrize("rel", [
    "app.py",
    "pkg/store.py",
    "src/pkg/agent.py",
])
def test_project_code_is_included(rel):
    assert is_project_file(Path(rel))


@pytest.mark.parametrize("rel", [
    "tests/test_a.py",
    "test/helpers.py",
    "pkg/test_helpers.py",
    "pkg/store_test.py",
    "conftest.py",
    "setup.py",
    ".venv/lib/python3.12/site-packages/requests/api.py",
    "venv/lib/x.py",
    "node_modules/pkg/tool.py",
    "build/lib/pkg/a.py",
    "pkg.egg-info/a.py",
    "readme.md",
])
def test_libraries_tests_and_build_output_are_excluded(rel):
    assert not is_project_file(Path(rel))


def test_root_under_a_folder_called_build_still_works(tmp_path):
    root = tmp_path / "build" / "proj"
    root.mkdir(parents=True)
    (root / "a.py").write_text("x = 1\n")
    assert ModuleMap(root).names == {str(root.resolve() / "a.py"): "a"}


def test_names_are_short_unless_two_files_clash(tmp_path):
    for rel in ("a/utils.py", "b/utils.py", "c.py", "pkg/__init__.py", "src/pkg2/mod.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n")
    m = ModuleMap(tmp_path)
    names = {Path(k).relative_to(tmp_path.resolve()).as_posix(): v for k, v in m.names.items()}
    assert names == {
        "a/utils.py": "a.utils",
        "b/utils.py": "b.utils",
        "c.py": "c",
        "pkg/__init__.py": "pkg",      # a package is named after its folder
        "src/pkg2/mod.py": "mod",      # a src/ layout does not show up in the name
    }


def test_files_outside_the_project_are_not_modules(tmp_path):
    m = ModuleMap(tmp_path)
    assert m.lookup("/usr/lib/python3/json/__init__.py") is None
    assert m.lookup(str(tmp_path / "later.py")) == "later"      # created after the walk
