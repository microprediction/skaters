import math

class ResidualVarianceLens:
    """
    Tracks the running log variance ratio between a short-term adaptive 
    window and a longer historical baseline window.
    """
    def __init__(self, alpha_short=0.05, alpha_long=0.005):
        self.alpha_short = alpha_short
        self.alpha_long = alpha_long
        self.mean_short = 0.0
        self.var_short = 1.0
        self.mean_long = 0.0
        self.var_long = 1.0
        
    def update(self, epsilon: float) -> float:
        if not math.isfinite(epsilon):
            v_short = max(self.var_short, 1e-9)
            v_long = max(self.var_long, 1e-9)
            return math.log(v_short / v_long)

        diff_short = epsilon - self.mean_short
        self.mean_short += self.alpha_short * diff_short
        self.var_short = (1.0 - self.alpha_short) * (self.var_short + self.alpha_short * diff_short * diff_short)
        
        diff_long = epsilon - self.mean_long
        self.mean_long += self.alpha_long * diff_long
        self.var_long = (1.0 - self.alpha_long) * (self.var_long + self.alpha_long * diff_long * diff_long)
        
        v_short = max(self.var_short, 1e-9)
        v_long = max(self.var_long, 1e-9)
        return math.log(v_short / v_long)

    def inverse(self, y_prime: float) -> float:
        return y_prime
