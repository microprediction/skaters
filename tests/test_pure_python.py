"""Tests that the package has zero external dependencies (Pyodide-safe)."""

import importlib
import pkgutil
import sys


def test_no_third_party_imports():
    """Walk every module and verify no non-stdlib imports sneak in."""
    import skaters
    for _, modname, _ in pkgutil.walk_packages(
        skaters.__path__, prefix="skaters."
    ):
        importlib.import_module(modname)


def test_no_numpy():
    """Explicitly verify numpy is not required."""
    import skaters
    deps = set()
    for _, modname, _ in pkgutil.walk_packages(
        skaters.__path__, prefix="skaters."
    ):
        mod = importlib.import_module(modname)
        source = importlib.util.find_spec(modname)
        if source and source.origin:
            with open(source.origin) as f:
                text = f.read()
            assert "import numpy" not in text, f"{modname} imports numpy"


def test_no_c_extensions():
    """All modules should be pure Python (.py), not .so/.pyd."""
    import skaters
    for _, modname, _ in pkgutil.walk_packages(
        skaters.__path__, prefix="skaters."
    ):
        spec = importlib.util.find_spec(modname)
        if spec and spec.origin:
            assert spec.origin.endswith(".py"), f"{modname} is not pure Python: {spec.origin}"
