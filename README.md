# merf

merf times a shell command over multiple runs, stores a baseline, and exits non-zero when a subsequent run regresses beyond a configured threshold. It is intended to be the smallest useful piece of performance infrastructure: repeatable measurement, baseline storage, and CI-style pass/fail gating.

## Install

Requires Python 3.12+.

```bash
git clone https://github.com/ArienR/merf.git
cd merf
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Usage

**Record a baseline:**

```bash
merf baseline --name sort-numbers --repeat 20 -- python3 benchmarks/sort_numbers.py
```

```
merf baseline  |  sort-numbers
command        |  python3 benchmarks/sort_numbers.py
runs           |  20 (+ 2 warmup discarded)

  median       0.048s
  p95          0.051s

Baseline saved to .merf/sort-numbers.json
```

**Check for regression** (exits 1 if median degrades by more than 10%):

```bash
merf check --name sort-numbers --repeat 20 -- python3 benchmarks/sort_numbers.py
```

```
merf check  |  sort-numbers
command     |  python3 benchmarks/sort_numbers.py
runs        |  20 (+ 2 warmup discarded)

             baseline    current    delta
  median     0.048s      0.049s     +2.1%
  p95        0.051s      0.052s     +2.0%

  threshold  10%
  result     PASS
```

Baselines are stored as JSON in `.merf/` and should be committed to version control so the whole team checks against the same reference point.

### Flags

| Flag | Command | Default | Description |
|---|---|---|---|
| `--name` | both | SHA256 of command | Identifies the baseline file. Explicit names are preferred. |
| `--repeat` | both | `10` | Timed samples to collect. Minimum: 5. |
| `--max-regression` | `check` | `10` | Fail if median degrades by more than this percentage. |
| `--json` | `check` | off | Emit structured JSON to stdout alongside normal output. |
| `--verbose` | both | off | Stream the benchmarked command's stdout/stderr. |

The `--` separator is required before the benchmarked command. It prevents merf from interpreting the command's own flags as its own.

## CI Integration

```yaml
# .github/workflows/perf.yml
- name: Check for performance regression
  run: merf check --name sort-numbers --repeat 20 --json -- python3 benchmarks/sort_numbers.py
```

The `--json` flag emits structured output after the human-readable table. A CI step can forward it to a metrics store or post results as a PR comment.

```json
{
  "name": "sort-numbers",
  "result": "pass",
  "threshold_percent": 10.0,
  "baseline_median": 0.048,
  "current_median": 0.049,
  "delta_percent": 2.1,
  "baseline_p95": 0.051,
  "current_p95": 0.052
}
```

## Measurement Reliability

merf measures wall-clock time. Results are only meaningful when conditions are consistent between the `baseline` and `check` runs.

**What introduces variance:** other processes competing for CPU, background I/O, thermal throttling, and power management. merf warns on stderr if system load is high before collecting samples, but cannot prevent interference.

**How to minimise variance:**
- Run on a quiet machine with other applications closed
- Use `--repeat 20` or higher — merf uses the median, which absorbs isolated outliers
- In CI, use a dedicated runner with no competing workloads

**Machine specificity:** a baseline recorded on one machine is not a reliable reference on another. The intended use is a single consistent environment — your laptop, or a fixed CI runner — where both baseline and check run on the same hardware.

**On Docker:** On certain operating systems, Docker runs inside a Linux VM, adding scheduling overhead that makes timing *less* reliable. merf does not support container isolation.
