import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class Stats:
    median: float
    p95: float


def compute_stats(samples: list[float]) -> Stats:
    sorted_samples = sorted(samples)
    return Stats(
        median=statistics.median(sorted_samples),
        p95=_p95(sorted_samples),
    )


def _p95(sorted_samples: list[float]) -> float:
    n = len(sorted_samples)
    index = 0.95 * (n - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_samples[lower]
    weight = index - lower
    return sorted_samples[lower] * (1 - weight) + sorted_samples[upper] * weight
