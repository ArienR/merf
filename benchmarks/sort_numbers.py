import random

random.seed(42)
data = [random.randint(0, 1_000_000) for _ in range(100_000)]
data.sort()
assert data[0] <= data[-1]
