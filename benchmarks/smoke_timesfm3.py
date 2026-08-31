"""Preflight for the TimesFM-3 arm. Two modes:

    PYTHONPATH=src:benchmarks python benchmarks/smoke_timesfm3.py --fake
        No weights, no torch: injects a stand-in timesfm3 module and checks
        the adapter's windowing, alignment, output count, and that the
        resulting Dists score. Runs on any machine; run it after editing
        the adapter.

    PYTHONPATH=src:benchmarks python benchmarks/smoke_timesfm3.py
        Loads the real checkpoint (google/timesfm-3.0-pytorch; ~1.3GB on
        first run) and scores one synthetic series end to end. Run once on
        the study machine before ARM_METHODS=TimesFM3. FM_DEVICE selects
        cpu | mps | cuda.

License note: the 3.0 weights are timesfm-non-commercial-license-v1.0,
research benchmarking only.
"""
from __future__ import annotations
import math
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np


def install_fake_timesfm3():
    """A stand-in that mimics the 3.0 API shape: predict_batch yields one
    output per context with .forecast [h] and .quantiles [h, 9], where the
    quantiles are deciles of a Gaussian centered on the context's last value.
    The center encodes the LAST CONTEXT VALUE so the test can prove which
    window each output came from (the alignment property the adapter must
    preserve: for horizon h the context ends h steps before the target)."""
    mod = types.ModuleType("timesfm3")

    class ModelConfig:
        def __init__(self, checkpoint_path, per_core_batch_size=32, device="cpu"):
            self.checkpoint_path = checkpoint_path
            self.device = device

    class _Out:
        def __init__(self, forecast, quantiles):
            self.forecast = forecast
            self.quantiles = quantiles

    class TimesFM3Evaluator:
        def __init__(self, config):
            self.config = config

    # symmetric deciles of a unit Gaussian, hardcoded (no scipy dependency)
    DECILE_Z = [-1.2815515655446004, -0.8416212335729143, -0.5244005127080407,
                -0.2533471031357997, 0.0, 0.2533471031357997,
                0.5244005127080407, 0.8416212335729143, 1.2815515655446004]

    def predict_batch(self, contexts, horizon, past_only_covariates=None,
                      past_future_covariates=None, return_quantiles=True,
                      use_symmetric_averaging=False):
        for c in contexts:
            c = np.asarray(c, dtype=np.float32)
            assert c.ndim == 1, "adapter must send univariate 1-D contexts"
            center = float(c[-1])
            fc = np.full((horizon,), center, dtype=np.float32)
            q = np.array([[center + z for z in DECILE_Z]] * horizon,
                         dtype=np.float32)
            yield _Out(fc, q)

    TimesFM3Evaluator.predict_batch = predict_batch
    mod.ModelConfig = ModelConfig
    mod.TimesFM3Evaluator = TimesFM3Evaluator
    sys.modules["timesfm3"] = mod


def main():
    fake = "--fake" in sys.argv
    if fake:
        install_fake_timesfm3()

    import foundation_study as fs
    from skaters.dist import Dist  # noqa: F401

    # long enough for the sandwich arms, which extend TEST by a warmup
    n = fs.CTX + fs.TEST + 300
    rng = np.random.default_rng(7)
    ch = list(np.cumsum(rng.standard_normal(n)) * 0.01 + np.sin(np.arange(n) / 9))

    for h in (1, 3):
        fs._timesfm3 = None
        dists = fs.timesfm3_dists(ch, h=h)
        assert dists is not None, f"adapter returned None at h={h}"
        assert len(dists) == fs.TEST, (len(dists), fs.TEST)
        y = ch[len(ch) - fs.TEST:]
        lps = [d.logpdf(v) for d, v in zip(dists, y)]
        assert all(math.isfinite(v) for v in lps), "non-finite log scores"
        if fake:
            # Alignment proof: the fake centers each predictive on the last
            # context value, which for target index t is ch[t - h]. The
            # median of dists[i] must equal ch[start + i - h] to float32.
            start = len(ch) - fs.TEST
            for i in (0, fs.TEST // 2, fs.TEST - 1):
                med = dists[i].quantile(0.5)
                want = ch[start + i - h]
                assert abs(med - want) < 1e-4, (h, i, med, want)
        print(f"h={h}: {len(dists)} dists, mean logpdf {np.mean(lps):+.3f}"
              + (", alignment verified" if fake else ""))

    if fake:
        import arm_adapters as aa
        reg = aa.make_registry(1)
        for name in ("TimesFM3", "TimesFM3+lap", "TimesFM3~lap",
                     "TimesFM3@lap", "TimesFM3&lap"):
            assert name in reg, name
            out = reg[name](ch)
            assert out is not None and len(out) == fs.TEST, name
            print(f"registry {name}: ok ({len(out)} dists)")

    print("SMOKE OK" + (" (fake backend)" if fake else " (real checkpoint)"))


if __name__ == "__main__":
    main()
