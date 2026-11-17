"""The shared inverse-CDF cases (parity/quantile_contract.json) on the torch
port. ``TorchDist.quantile`` delegates to the reference search, so each case
must agree with ``Dist.quantile`` exactly, and the spliced wrapper must carry
the same default budget."""
import inspect
import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from skaters.dist import Dist                      # noqa: E402
from skaters.torch.dist import TorchDist           # noqa: E402
from skaters.torch.tails import TorchSplicedDist   # noqa: E402

CASES = json.loads((Path(__file__).parents[1] / "parity/quantile_contract.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_torch_quantile_contract(case):
    ref = Dist(case["components"])
    t = TorchDist.from_reference(ref)
    q = float(t.quantile(case["p"]))
    assert q == ref.quantile(case["p"]), (q, case)
    if "expected" in case:
        assert abs(q - case["expected"]) <= case.get("python_atol", case["atol"]), (q, case)
    else:
        assert case["lower"] < q < case["upper"], (q, case)


def test_torch_tiny_spread_is_preserved():
    d = TorchDist.from_components([(1.0, 0.0, 1e-11)])
    spread = float(d.quantile(.99)) - float(d.quantile(.01))
    assert abs(spread - 4.6526957480816816e-11) < 2e-20


def test_torch_default_budgets_match_reference():
    want = inspect.signature(Dist.quantile).parameters["max_iter"].default
    for cls in (TorchDist, TorchSplicedDist):
        assert inspect.signature(cls.quantile).parameters["max_iter"].default == want
