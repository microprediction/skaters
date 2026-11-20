"""Cross-port inverse-CDF cases: x accuracy, spread, atoms and reviewed regressions."""
import json
from pathlib import Path
import pytest
from skaters.dist import Dist

CASES = json.loads((Path(__file__).parents[1] / "parity/quantile_contract.json").read_text())

@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_quantile_contract(case):
    d = Dist(case["components"])
    q = d.quantile(case["p"])
    if "expected" in case:
        assert abs(q - case["expected"]) <= case.get("python_atol", case["atol"]), (q, case)
    else:
        assert case["lower"] < q < case["upper"], (q, case)
    if "cdf_tol" in case:
        assert abs(d.cdf(q) - case["p"]) <= case["cdf_tol"], (q, d.cdf(q), case)

def test_tiny_spread_is_preserved():
    d = Dist([(1, 0, 1e-11)])
    assert abs((d.quantile(.99) - d.quantile(.01)) - 4.6526957480816816e-11) < 2e-20


def test_explicit_budget_and_resolution_stop():
    d = Dist([(1, 0, 1)])
    assert d.quantile(.5, max_iter=0) == 0
    assert d.quantile(.5, max_iter=1) == -4
    for tol in [0, -1]:
        q = d.quantile(.5, tol=tol)
        assert abs(q) < 1e-15
        assert d.cdf(q) >= .5


def test_unit_scale_cdf_call_count_is_unchanged():
    class Counted(Dist):
        calls = 0
        def cdf(self, x):
            self.calls += 1
            return super().cdf(x)
    d = Counted([(1, 0, 1)])
    d.quantile(.9)
    assert d.calls == 36  # two bracket checks, 34 historical bisections


def test_variance_overflow_is_explicit():
    with pytest.raises(ArithmeticError, match="finite mixture variance"):
        Dist([(.5, -1e155, 1), (.5, 1e155, 1)]).quantile(.5)


@pytest.mark.parametrize("wrapper", ["residual", "homogenized"])
def test_identity_corrections_reach_narrow_component(wrapper):
    from skaters.residual_transform import CorrectedDist, IDENTITY_FAMILY
    from skaters.homogenize import HomogenizedDist
    base = Dist([(.5, 0, 1e-11), (.5, 1e20, 1)])
    d = (CorrectedDist(base, IDENTITY_FAMILY, {}) if wrapper == "residual"
         else HomogenizedDist(base, {"weights": [1.0], "scales": [1.0]}))
    q = d.quantile(.25)
    assert abs(q) < 1e-18
    assert abs(d.cdf(q) - .25) < 1e-8
