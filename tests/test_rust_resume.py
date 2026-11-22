"""Cross-language resume between Python and the Rust core, both directions.

A skater is a fold, and its state has one plain-JSON layout (docs/STATE.md),
so a checkpoint written by one port must resume in the other.

- Python to Rust: parity/gen_resume.py writes Python's canonical states of
  every parity scenario at three points of a fixed series plus the next
  steps' probes; rust/tests/resume.rs loads each into the same-named Rust
  skater, steps, and matches the probes to 1e-6. It also requires the loaded
  state to write back exactly as Python wrote it, and Rust's own state after
  the same observations to have Python's layout field by field.
- Rust to Python: the same Rust test writes Rust's own checkpoints to
  parity/resume_rust.json, and parity/check_resume.py resumes them here.
- granger likewise, on parity/gen_granger_resume.py's streams.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_ENV = {**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")}

needs_cargo = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")


def _py(script, *args):
    subprocess.run([sys.executable, os.path.join(ROOT, "parity", script), *args],
                   check=True, cwd=ROOT, env=PY_ENV)


def _cargo_test(name):
    subprocess.run(["cargo", "test", "--release", "--test", name],
                   check=True, cwd=os.path.join(ROOT, "rust"))


@needs_cargo
def test_rust_resume_both_directions():
    _py("gen_resume.py")
    _cargo_test("resume")              # Python -> Rust, and writes resume_rust.json
    _py("check_resume.py", os.path.join(ROOT, "parity", "resume_rust.json"))   # Rust -> Python


@needs_cargo
def test_rust_granger_resume_both_directions():
    _py("gen_granger_vectors.py")
    _py("gen_granger_resume.py")
    _cargo_test("granger_parity")      # Python -> Rust, and writes resume_granger_rust.json
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from skaters.granger import granger
    from skaters.state import state_from_json

    ref = json.load(open(os.path.join(ROOT, "parity", "granger_resume.json")))
    theirs = json.load(open(os.path.join(ROOT, "parity", "resume_granger_rust.json")))
    checked = 0
    for key, st in ref.items():
        freq = key.split("/")[0]
        ys = [float("nan") if v is None else v for v in st["ys"]]
        for t, cp in st["checkpoints"].items():
            g = granger(1, frequency=freq)
            s = state_from_json(theirs[key][t])
            for j, row in enumerate(cp["rows"]):
                d, s = g(ys[int(t) + j], s)
                m = d[0]
                nxt = ys[int(t) + j + 1]
                got = [m.logpdf(nxt) if nxt == nxt else None, m.mean, m.std, m.w[0],
                       m.quantile(0.1), m.quantile(0.9)]
                for a, b in zip(got, row):
                    if b is None:
                        continue
                    checked += 1
                    assert abs(a - b) <= 1e-6 + 1e-6 * abs(b), f"{key}@{t} step {j}: {a} vs {b}"
    assert checked > 0
