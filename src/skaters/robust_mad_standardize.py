import math

class RobustMADStandardize:
    """
    Streaming approximation of Median and Median Absolute Deviation (MAD)
    using stochastic quantile tracking.
    """
    def __init__(self, lr_median=0.01, lr_mad=0.01, initial_guess=0.0):
        self.median = initial_guess
        self.mad = 1.0
        self.lr_median = lr_median
        self.lr_mad = lr_mad
        
    def update(self, y: float) -> float:
        if not math.isfinite(y):
            return 0.0

        if y > self.median:
            self.median += self.lr_median * self.mad
        elif y < self.median:
            self.median -= self.lr_median * self.mad
            
        dev = abs(y - self.median)
        target_mad = dev * 1.4826
        
        if target_mad > self.mad:
            self.mad += self.lr_mad * self.mad
        elif target_mad < self.mad:
            self.mad -= self.lr_mad * self.mad
            
        if self.mad < 1e-4:
            self.mad = 1e-4
            
        return (y - self.median) / self.mad

    def inverse(self, y_prime: float) -> float:
        return (y_prime * self.mad) + self.median
