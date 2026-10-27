"""Tests that the package has zero external dependencies (Pyodide-safe)."""

import importlib
import pkgutil
import sys

# skaters.torch is the one optional subpackage (pip install skaters[torch]);
# it needs torch by design and is never imported by `import skaters`, so the
# dependency-free guards walk past it. test_base_import_is_torch_free checks
# the other half of that contract.
OPTIONAL = ("skaters.torch",)


def _modules():
    import skaters
    for _, modname, _ in pkgutil.walk_packages(skaters.__path__, prefix="skaters."):
        if not modname.startswith(OPTIONAL):
            yield modname


def test_no_third_party_imports():
    """Walk every module and verify no non-stdlib imports sneak in."""
    for modname in _modules():
        importlib.import_module(modname)


def test_base_import_is_torch_free():
    """The optional subpackage must not be pulled in by the base package.
    Checked in a fresh interpreter, so nothing else in this session (a
    plugin, an earlier test) can have imported torch first."""
    import subprocess
    code = "import sys, skaters; assert 'torch' not in sys.modules; assert 'skaters.torch' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_no_numpy():
    """Explicitly verify numpy is not required."""
    import skaters
    deps = set()
    for modname in _modules():
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
