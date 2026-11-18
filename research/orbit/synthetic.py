"""Reproduce the conditional-centering and long-path mechanism checks.

This is a transform diagnostic, not a distributional forecasting benchmark.
The noisy orbit and white-noise controls expose the cost of analog fitting
when state recurrence is imperfect or absent. Parameters are fixed in advance.
"""

import csv
import math
from pathlib import Path
import random

from research.orbit import orbit_transform


def main():
    rng = random.Random(702)
    streams = {
        "orbit64": [10.0 + 3.0 * math.sin(2.0 * math.pi * i / 64.0) for i in range(896)],
        "noisy_orbit64": [10.0 + 3.0 * math.sin(2.0 * math.pi * i / 64.0)
                          + rng.gauss(0.0, 0.15) for i in range(896)],
        "white_noise": [rng.gauss(0.0, 1.0) for _ in range(896)],
        "random_walk": [],
    }
    value = 0.0
    for _ in range(896):
        value += rng.gauss(0.0, 1.0)
        streams["random_walk"].append(value)
    path = Path(__file__).with_name("results_transform.csv")
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["stream", "memory", "n_test", "center_rmse", "last_value_rmse",
                         "zero_center_rmse", "zero_residual_path128_max_error"])
        for name, ys in streams.items():
            for memory in (16, 512):
                transform = orbit_transform(memory=memory)
                state = None
                residuals = []
                for y in ys:
                    z, state = transform.forward(y, state)
                    residuals.append(z)
                n = 256
                rmse = math.sqrt(math.fsum(z * z for z in residuals[-n:]) / n)
                last = math.sqrt(math.fsum((ys[i] - ys[i - 1]) ** 2
                                          for i in range(len(ys) - n, len(ys))) / n)
                zero = math.sqrt(math.fsum(y * y for y in ys[-n:]) / n)
                error = ""
                if name == "orbit64":
                    future = transform.inverse_path([0.0] * 128, state)
                    error = max(abs(y - (10.0 + 3.0 * math.sin(2.0 * math.pi * i / 64.0)))
                                for i, y in enumerate(future, start=len(ys)))
                writer.writerow([name, memory, n, f"{rmse:.10g}", f"{last:.10g}",
                                 f"{zero:.10g}", "" if error == "" else f"{error:.10g}"])
    print(path)


if __name__ == "__main__":
    main()
