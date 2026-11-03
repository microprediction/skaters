"""The torch port against the standard parity vectors, through the same
checker the release gates use (parity/check_torch.py). Regenerates the vectors
from the Python reference when they are missing or older than any
reference source, so a stale file cannot report PARITY OK. Skipped where
torch is absent."""
import os
import subprocess
import sys

import pytest

torch = pytest.importorskip("torch")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS = os.path.join(ROOT, "parity", "vectors.json")


def _vectors_stale():
    """Missing, or older than any reference source or the generator itself."""
    if not os.path.exists(VECTORS):
        return True
    age = os.path.getmtime(VECTORS)
    srcs = [os.path.join(ROOT, "parity", "gen_vectors.py")]
    for root, _dirs, files in os.walk(os.path.join(ROOT, "src", "skaters")):
        if os.sep + "torch" in root:
            continue
        srcs += [os.path.join(root, f) for f in files if f.endswith(".py")]
    return any(os.path.getmtime(p) > age for p in srcs)


def test_torch_port_passes_the_parity_vectors():
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    if _vectors_stale():
        subprocess.run([sys.executable, os.path.join(ROOT, "parity", "gen_vectors.py")],
                       check=True, env=env, timeout=1800)
    out = subprocess.run([sys.executable, os.path.join(ROOT, "parity", "check_torch.py"), "-q"],
                         capture_output=True, text=True, env=env, timeout=3600)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-1000:]
    assert "PARITY OK" in out.stdout
