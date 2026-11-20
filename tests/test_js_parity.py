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


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_state_roundtrip():
    """A skater is a fold: for every exported JS skater, state must survive
    stateFromJSON(JSON.parse(JSON.stringify(stateToJSON(state)))) bit-exactly,
    on the restore step and on every step after it, and hold nothing JSON
    would damage (functions, Map, Set, foreign classes, non-finite numbers).
    See parity/roundtrip.mjs."""
    result = subprocess.run(
        ["node", os.path.join(ROOT, "parity", "roundtrip.mjs")],
        capture_output=True, text=True, cwd=ROOT,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
    assert result.returncode == 0, "JS state round-trip gate failed"


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
def test_rust_parity():
    """The Rust core (rust/) must reproduce the Python numerics: regenerate
    the vectors, then run the crate's parity gate against them. Same
    lockstep contract as the JS twin: a numerics change cannot merge
    without its Rust mirror."""
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "parity", "gen_vectors.py")],
        check=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")})
    subprocess.run(
        ["cargo", "test", "--release", "--test", "parity"],
        check=True, cwd=os.path.join(ROOT, "rust"))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_quantile_contract():
    subprocess.run(["node", os.path.join(ROOT, "parity", "quantile_contract.mjs")], check=True, cwd=ROOT)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_spliced_affine():
    subprocess.run(["node", os.path.join(ROOT, "parity", "spliced_affine.mjs")], check=True, cwd=ROOT)


def _spliced_nonaffine_reference(path):
    """A Python SplicedDist and its transforms' outputs, for the JS checker."""
    import json
    import math
    import random
    from skaters import laplace
    from skaters.tails import SplicedDist
    from skaters.transform import ema_transform, power_transform, yeo_johnson

    rng, x, st, d = random.Random(5), 0.0, None, None
    for t in range(1500):
        x = 0.9 * x + rng.gauss(0.0, 1.0) * (1.0 + 0.5 * math.sin(t / 7.0))
        d, st = laplace()(x, st)
    sd = d[0]
    assert isinstance(sd, SplicedDist)
    ps = (0.001, 0.05, 0.5, 0.95, 0.999)
    pushforward = {}
    for key, t in (("power_transform", power_transform(0.5)),
                   ("yeo_johnson_0", yeo_johnson(0.0)),
                   ("yeo_johnson_half", yeo_johnson(0.5))):
        e = t[1]([sd], {})[0]
        xs = [e.quantile(p) for p in (0.01, 0.3, 0.5, 0.7, 0.99)]
        pushforward[key] = {
            "quantile": [[p, e.quantile(p)] for p in ps],
            "cdf": [[v, e.cdf(v)] for v in xs],
            "logpdf": [[v, e.logpdf(v)] for v in xs],
            "crps": [[v, e.crps(v)] for v in xs],
            "mean": e.mean, "std": e.std,
        }
    level, alpha = 2.0, 0.05
    w = ema_transform(alpha)[1]([sd, sd], {"level": level})[1]
    ref = {"dist": sd.to_dict(), "pushforward": pushforward,
           "widen": {"level": level, "alpha": alpha, "mean": w.mean,
                     "quantile": [[p, w.quantile(p)] for p in ps]}}
    with open(path, "w") as f:
        json.dump(ref, f)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_spliced_nonaffine(tmp_path):
    ref = str(tmp_path / "spliced_nonaffine.json")
    _spliced_nonaffine_reference(ref)
    subprocess.run(["node", os.path.join(ROOT, "parity", "spliced_nonaffine.mjs"), ref],
                   check=True, cwd=ROOT)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_pushforward_affine():
    subprocess.run(["node", os.path.join(ROOT, "parity", "pushforward_affine.mjs")], check=True, cwd=ROOT)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_spec_json_is_byte_identical():
    """JS toJson(spec) must be Python's to_json(spec) byte for byte, and
    specName must agree, so a spec hashes the same in both ports."""
    import json
    from skaters import spec as S
    specs = [
        S.leaf_spec(1),
        S.ema_spec(0.05, 1),
        S.ema_spec(1.0, 3),
        S.ema_spec(1e-05, 1),
        S.std_spec(0.0001),
        S.frac_spec(0.4, 30),
        S.frac_spec(1.5e-07, 50),
        S.conjugate_spec(S.ensemble_spec(S.ema_spec(0.01, 1), S.ema_spec(0.1, 1), k=1), S.diff_spec()),
        S.conjugate_spec(S.conjugate_spec(S.leaf_spec(2), S.ema_t_spec(0.3)), S.frac_spec(0.25, 20)),
        {"op": "ensemble", "k": 2, "floor": 1e-06, "skaters": [S.ema_spec(123.456, 2), S.leaf_spec(2)]},
    ]
    from pathlib import Path
    url = Path(ROOT, "docs", "js", "skaters", "spec.mjs").as_uri()
    src = (
        f"import {{ toJson, fromJson, name }} from '{url}';"
        "import { readFileSync } from 'node:fs';"
        "const specs = JSON.parse(readFileSync(0, 'utf8'));"
        "process.stdout.write(JSON.stringify(specs.map((t) => {"
        "  const s = fromJson(t); let n = null; try { n = name(s); } catch (e) {}"
        "  return [toJson(s), n]; })));"
    )
    texts = [S.to_json(s) for s in specs]
    result = subprocess.run(["node", "--input-type=module", "-e", src], input=json.dumps(texts),
                            capture_output=True, text=True, cwd=ROOT, check=True)
    for spec, text, (js_text, js_name) in zip(specs, texts, json.loads(result.stdout)):
        assert js_text == text, f"toJson differs: {js_text} vs {text}"
        if spec["op"] in ("leaf", "ema", "ensemble", "conjugate"):     # transform specs have no name
            assert js_name == S.name(spec)
