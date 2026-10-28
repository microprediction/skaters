"""The torch port against the standard parity vectors, through the same
checker the release gates use (parity/check_torch.py). Generates the
vectors from the Python reference first if they are not on disk, exactly
as the JS parity test does. Skipped where torch is absent."""
import os
import subprocess
import sys

import pytest

torch = pytest.importorskip("torch")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS = os.path.join(ROOT, "parity", "vectors.json")


def test_torch_port_passes_the_parity_vectors():
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    if not os.path.exists(VECTORS):
        subprocess.run([sys.executable, os.path.join(ROOT, "parity", "gen_vectors.py")],
                       check=True, env=env, timeout=1800)
    out = subprocess.run([sys.executable, os.path.join(ROOT, "parity", "check_torch.py"), "-q"],
                         capture_output=True, text=True, env=env, timeout=3600)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-1000:]
    assert "PARITY OK" in out.stdout
