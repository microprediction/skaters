"""Checkpoints written before skaters#235 carry only the raw RLS coefficients
(``phi`` / ``theta``), not the projected cache ``phi_used``. Resuming such a
state must work in forward and in inverse_k, and must continue exactly as a
state that has the cache, because the cache is a function of the saved
coefficients. The JS port is checked through node where available."""
import copy
import json
import os
import shutil
import subprocess

import pytest

from skaters import laplace
from skaters.transform import ar, grouped_ar

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(os.path.dirname(HERE), "docs", "js", "skaters")


def _series(n=60):
    import math
    return [math.sin(i) + 0.1 * math.cos(3 * i) for i in range(n)]


def _strip(obj):
    """Remove every phi_used key, as a pre-#235 checkpoint would lack it."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k != "phi_used"}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


@pytest.mark.parametrize("factory", [lambda: ar(3), lambda: grouped_ar(8)],
                         ids=["ar3", "grouped_ar8"])
@pytest.mark.parametrize("warm", [2, 30], ids=["warmup", "settled"])
def test_transform_resumes_from_a_checkpoint_without_the_cache(factory, warm):
    fwd, inv = factory()
    ys = _series()
    st = None
    for y in ys[:warm]:
        _, st = fwd(y, st)
    old = _strip(copy.deepcopy(st))
    assert "phi_used" not in old
    # inverse first (the reviewer's warm-up case), then forward, on both copies
    from skaters.dist import Dist
    probe = [Dist.gaussian(0.0, 1.0), Dist.gaussian(0.1, 0.8), Dist.gaussian(-0.2, 1.3)]
    a = inv(probe, copy.deepcopy(st))
    b = inv(probe, copy.deepcopy(old))
    assert all(x.components == y.components for x, y in zip(a, b))
    st_full, st_old = copy.deepcopy(st), old
    for y in ys[warm:]:
        z1, st_full = fwd(y, st_full)
        z2, st_old = fwd(y, st_old)
        assert z1 == z2
    assert st_old["phi_used"] == st_full["phi_used"]
    a = inv(probe, st_full); b = inv(probe, st_old)
    assert all(x.components == y.components for x, y in zip(a, b))


def test_laplace_resumes_from_a_checkpoint_without_the_cache():
    f = laplace(1)
    ys = _series(80)
    st = None
    for y in ys[:40]:
        _, st = f(y, st)
    old = _strip(copy.deepcopy(st))
    st_full = copy.deepcopy(st)
    for y in ys[40:]:
        d1, st_full = f(y, st_full)
        d2, old = f(y, old)
        assert d1[0].components == d2[0].components


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_js_port_resumes_from_a_checkpoint_without_the_cache(tmp_path):
    script = r"""
import { ar, groupedAr } from "./transform.mjs";
const ys = Array.from({length: 60}, (_, i) => Math.sin(i) + 0.1 * Math.cos(3 * i));
const strip = (o) => Array.isArray(o) ? o.map(strip)
  : (o && typeof o === "object") ? Object.fromEntries(Object.entries(o).filter(([k]) => k !== "phiUsed").map(([k, v]) => [k, strip(v)]))
  : o;
for (const [name, mk] of [["ar3", () => ar(3)], ["groupedAr8", () => groupedAr(8)]]) {
  const t = mk();
  let st = null;
  for (const y of ys.slice(0, 30)) { const r = t.forward(y, st); st = r[1]; }
  let full = JSON.parse(JSON.stringify(st));
  let old = strip(JSON.parse(JSON.stringify(st)));
  if (old.phiUsed !== undefined) throw new Error("strip failed");
  for (const y of ys.slice(30)) {
    const a = t.forward(y, full); full = a[1];
    const b = t.forward(y, old); old = b[1];
    if (a[0] !== b[0]) throw new Error(name + ": emission differs after migration");
  }
  if (JSON.stringify(old.phiUsed) !== JSON.stringify(full.phiUsed)) throw new Error(name + ": cache differs");
}
console.log("ok");
"""
    p = tmp_path / "migrate_check.mjs"
    p.write_text(script)
    # run from the JS package directory so relative imports resolve
    shutil.copy(p, os.path.join(JS, "_migrate_check_tmp.mjs"))
    try:
        out = subprocess.run(["node", "_migrate_check_tmp.mjs"], cwd=JS, capture_output=True, text=True, timeout=120)
    finally:
        os.remove(os.path.join(JS, "_migrate_check_tmp.mjs"))
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout
