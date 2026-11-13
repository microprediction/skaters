"""examples/positive_series.py: the log-conjugated laplace keeps its quantiles positive."""
import importlib.util
import os

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "examples", "positive_series.py")
_spec = importlib.util.spec_from_file_location("positive_series", _PATH)
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)


def test_log_conjugated_laplace_stays_positive():
    from skaters import laplace
    from skaters.conjugate import conjugate

    f = conjugate(laplace(), ex.log_transform(), k=1)
    state = None
    for t, y in enumerate(ex.positive_series(n=300)):
        dists, state = f(y, state)
        if t > 50:
            d = dists[0]
            assert d.quantile(0.001) > 0.0
            assert d.cdf(0.0) < 1e-9    # table extrapolation, not mass


def test_exact_yeo_johnson_wraps_laplace():
    """exact=True used to read d.components, which laplace's SplicedDist lacks."""
    from skaters import laplace
    from skaters.conjugate import conjugate
    from skaters.transform import yeo_johnson

    f = conjugate(laplace(), yeo_johnson(0.0, exact=True), k=1)
    state = None
    for y in ex.positive_series(n=120):
        dists, state = f(y, state)
    d = dists[0]
    assert d.quantile(0.1) < d.quantile(0.5) < d.quantile(0.9)
    assert d.quantile(0.001) > -1.0
