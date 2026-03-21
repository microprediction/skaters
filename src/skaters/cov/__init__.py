"""Online covariance and correlation estimation.

Streaming estimators that process one observation vector at a time.
Inspired by the precise package (github.com/microprediction/precise).

API pattern:
    mean, cov, state = f(y, state)

where y is a list of floats and cov is a flat list (row-major n x n).
"""

from skaters.cov.running import running_cov
from skaters.cov.ema_cov import ema_cov
from skaters.cov.shrinkage import ledoit_wolf_cov

__all__ = ["running_cov", "ema_cov", "ledoit_wolf_cov"]
