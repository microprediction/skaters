"""JS <-> Python parity: the JS port must reproduce the Python numerics.

Generates probe vectors from the Python implementation, then runs the Node
checker (parity/check.mjs) which reruns the JS port on the identical series
and asserts agreement to 1e-6. Skipped if Node is not installed.
"""

import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_python_parity():
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "parity", "gen_vectors.py")],
        check=True, cwd=ROOT,
    )
    result = subprocess.run(
        ["node", os.path.join(ROOT, "parity", "check.mjs")],
        capture_output=True, text=True, cwd=ROOT,
    )
    if result.returncode != 0:
        # Surface the mismatch detail in the pytest failure output.
        print(result.stdout)
        print(result.stderr)
    assert result.returncode == 0, "JS/Python parity check failed"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_adversarial_gate():
    """The JS twin must survive the deployment pathologies (constant,
    lattice, monster spike, scale collapse, vol whiplash) — the release
    gate mirroring tests/test_tails_robustness.py."""
    subprocess.run(
        ["node", os.path.join(ROOT, "parity", "adversarial.mjs")],
        check=True, cwd=ROOT)
