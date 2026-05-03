import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class Stats:
    median: float
    p95: float


def compute_stats(samples: list[float]) -> Stats:
    sorted_samples = sorted(samples)
    p95_index = math.ceil(0.95 * len(sorted_samples)) - 1
    return Stats(
        median=statistics.median(sorted_samples),
        p95=sorted_samples[p95_index],
    )
