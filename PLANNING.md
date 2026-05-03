# merf — Planning Document

## Problem Statement

`merf` is a minimal CLI tool for performance regression detection. It times a shell
command over multiple runs, stores a baseline, and fails with a non-zero exit code
when a subsequent run regresses beyond a configured threshold. It is not a
profiler, a load tester, or a cross-platform calibration tool — it is the smallest
useful slice of performance infrastructure: repeatable measurement, baseline
storage, and CI-style pass/fail regression gating.

## CLI Interface

```
merf baseline [--name <name>] [--repeat <n>] -- <command>
merf check   [--name <name>] [--repeat <n>] [--max-regression <percent>] [--json] -- <command>
```

### Flags

| Flag               | Command | Default                | Notes                                                                            |
| ------------------ | ------- | ---------------------- | -------------------------------------------------------------------------------- |
| `--name`           | both    | hash of command string | Identifies the baseline. Explicit names are preferred for readability.           |
| `--repeat`         | both    | `10`                   | Number of timed samples. Minimum enforced: `5`.                                  |
| `--max-regression` | `check` | `10` (percent)         | Applied to median. Regression if `(new - old) / old > threshold`.                |
| `--json`           | `check` | off                    | Emit structured JSON result to stdout alongside normal output. For CI consumers. |
| `--verbose`        | both    | off                    | Stream the benchmarked command's stdout/stderr. Suppressed by default.           |

### Examples

```bash
# Record a baseline
merf baseline --name parse-csv --repeat 20 -- python scripts/parse.py data.csv

# Check for regression (fails with exit 1 if median degrades >10%)
merf check --name parse-csv --repeat 20 --max-regression 10 -- python scripts/parse.py data.csv

# Omitting --name: derived from command hash (less readable, but works)
merf baseline --repeat 10 -- python scripts/parse.py data.csv

# CI-friendly structured output
merf check --name parse-csv --json -- python scripts/parse.py data.csv
```

### Behaviour decisions

- The `--` separator is required before the command. This avoids ambiguity between
  merf flags and flags belonging to the benchmarked command.
- If `--name` is omitted, the name is derived as a short SHA256 of the full command
  string. This is deterministic and portable but opaque — using `--name` explicitly
  is always recommended.
- If `merf check` is run with no stored baseline for the given name, it exits with a
  clear error message: `No baseline found for "parse-csv". Run merf baseline first.`
  It does not fall back to recording a new baseline silently.
- The benchmarked command's stdout and stderr are suppressed by default so they don't
  pollute timing output or CI logs. Pass `--verbose` to see them.
- If the benchmarked command exits with a non-zero code on any run, merf aborts
  immediately and does not record or compare results.

## Data Model

Baselines are stored as JSON files in a `.merf/` directory at the project root (i.e.
wherever merf is invoked from). Each baseline is one file: `.merf/<name>.json`.

```json
{
  "version": 1,
  "name": "parse-csv",
  "command": "python scripts/parse.py data.csv",
  "repeat": 20,
  "warmup_runs": 2,
  "samples_seconds": [0.312, 0.298, 0.305, 0.301, 0.309],
  "median": 0.301,
  "p95": 0.318,
  "recorded_at": "2026-05-02T10:00:00Z"
}
```

Notes:

- `version` allows silent format incompatibility to be detected in future. On load,
  if `version` doesn't match the current schema version, merf exits with an error
  rather than silently misreading the data.
- `warmup_runs` records how many runs were discarded, for transparency.
- Raw `samples_seconds` are stored so future versions of merf can recompute stats
  (e.g. add p99) without re-running the benchmark.
- The `.merf/` directory should be committed to version control so baselines are
  shared across the team and trackable over time.

## Statistics

| Statistic | How computed                                | Used for                                           |
| --------- | ------------------------------------------- | -------------------------------------------------- |
| Median    | `statistics.median()`                       | Regression gate. Robust to outlier runs.           |
| p95       | Sort samples, take index at 95th percentile | Reported only. Not used as regression gate in MVP. |

Minimum sample floor: `5`. merf refuses to run with `--repeat` below this and
explains why. Fewer than 5 samples produces unreliable percentiles.

Warmup: the first 2 runs are always discarded before samples are collected. This
accounts for filesystem cache cold starts and interpreter startup jitter. Warmup
runs are not configurable in MVP — this is intentional simplicity.

## Environment Checks

merf cannot provide true process isolation on macOS without root privileges —
CPU frequency pinning, core affinity, and container-level isolation are all out
of scope (see Explicitly Deferred). What it can do is warn the user when
conditions are likely to produce noisy results.

**Pre-run load check** (implemented in the sample collector, step 2):

Before collecting any samples, merf reads `os.getloadavg()[0]` (1-minute load
average) and compares it to `os.cpu_count()`. If load exceeds 80% of available
cores, merf prints a warning to stderr and continues — it does not abort.

```
⚠  System load is high (6.4 on 8 cores). Measurements may be noisy.
```

This uses stdlib only (`os` module). The threshold is `cpu_count * 0.8`.

The same check runs for both `baseline` and `check`. A warning during `check`
but not during `baseline` (or vice versa) is itself a signal that the
comparison may not be reliable.

## Build Order

Each step should be independently runnable/testable before moving to the next.

1. **Subprocess runner** — given a command string, run it once, return wall-clock elapsed time and exit code. Suppress stdout/stderr (with optional passthrough).

2. **Sample collector** — call the runner N+warmup times, discard warmup results, return a list of float timings. Enforce minimum repeat floor here. Run pre-run load check and emit warning to stderr if load is high.

3. **Stats module** — given a list of samples, return median and p95. Unit-testable with fixed inputs.

4. **Storage module** — `save_baseline(name, data)` and `load_baseline(name)`. Handles `.merf/` directory creation, JSON serialisation, version checking, and missing-file errors.

5. **`baseline` command** — wire up collector + stats + storage. Print a summary table to stdout.

6. **`check` command** — load baseline, run collector + stats, compute regression delta, print comparison, exit 1 if threshold exceeded. Add `--json` output here.

7. **CLI layer** — `click` wiring, `--` separator handling, `--verbose` passthrough, help text.

8. **Error handling and edge cases** — non-zero command exit, missing baseline, version mismatch, repeat below floor, empty command.

9. **README and `.mise.toml`** — document setup, usage, and the CI integration pattern.

## Output Format

### `merf baseline` (stdout)

```
merf baseline  |  parse-csv
command        |  python scripts/parse.py data.csv
runs           |  20 (+ 2 warmup discarded)

  median       0.301s
  p95          0.318s

Baseline saved to .merf/parse-csv.json
```

### `merf check` (stdout, passing)

```
merf check  |  parse-csv
command     |  python scripts/parse.py data.csv
runs        |  20 (+ 2 warmup discarded)

             baseline    current    delta
  median     0.301s      0.308s     +2.3%
  p95        0.318s      0.331s     +4.1%

  threshold  10%
  result     PASS
```

### `merf check` (stdout, failing)

```
  result     FAIL  (+14.2% exceeds 10% threshold)
exit 1
```

### `merf check --json` (additional structured output)

```json
{
  "name": "parse-csv",
  "result": "pass",
  "threshold_percent": 10,
  "baseline_median": 0.301,
  "current_median": 0.308,
  "delta_percent": 2.3,
  "baseline_p95": 0.318,
  "current_p95": 0.331
}
```

## Environment Setup

Use `mise` to pin the Python version. `.mise.toml` at the project root:

```toml
[tools]
python = "3.12"
```

Dependencies managed with a standard `pyproject.toml`. No framework beyond the
stdlib is required for MVP — `argparse`, `subprocess`, `statistics`, `json`, and
`pathlib` cover everything.

If `click` is preferred over `argparse` for CLI ergonomics, that's a reasonable
choice — decide before starting the CLI layer (step 7) and don't switch mid-build.

## Explicitly Deferred (V2+)

These are known omissions, not oversights.

- **Docker / container isolation** — overhead is inconsistent and not worth the
  complexity for local and CI use cases merf targets.
- **Environmental calibration** — noise correction derived from a reference workload doesn't transfer reliably across different program types. Warmup + sufficient samples is the right answer at this scale. (Note: a pre-run load *warning* is in scope for MVP; full calibration is not.)
- **Process isolation** — CPU frequency pinning, core affinity, and container-level isolation all require root or a Linux VM on macOS, and add overhead that can make timing *less* reliable. The load check warning is the practical boundary of what merf can offer here.
- **Statistical significance testing** (t-tests, Mann-Whitney) — valuable for large sample sets, overkill for an MVP with N=10–50.
- **Parallel benchmark execution** — complicates timing reliability. Explicitly out of scope.
- **Multiple baselines per name** (history tracking) — storing only the latest baseline is sufficient for regression gating. History is a separate concern.
- **Windows support** — not tested or guaranteed. Linux and macOS only for MVP.

## Open Questions

These were raised during planning and have been resolved with a stated decision.
Revisit if requirements change.

| Question                                     | Decision                                                                                    |
| -------------------------------------------- | ------------------------------------------------------------------------------------------- |
| What if `--name` is omitted?                 | Derive from SHA256 of command string. Warn user that explicit `--name` is preferred.        |
| What if `merf check` has no stored baseline? | Hard fail with a clear message. No silent fallback.                                         |
| Apply regression threshold to median or p95? | Median only. p95 reported but not gated in MVP.                                             |
| Commit `.merf/` to version control?          | Yes. Baselines are shared team artefacts. Add `.merf/*.json` to the repo, not `.gitignore`. |
