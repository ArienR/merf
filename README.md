# merf

A minimal CLI tool for performance regression detection. It times a shell command over multiple runs, stores a baseline, and fails with a non-zero exit code when a subsequent run regresses beyond a configured threshold.

## Measurement Reliability

merf measures wall-clock time. Results are only meaningful when the machine is quiet and consistent between the `baseline` and `check` runs.

**What introduces variance:**

- Other processes competing for CPU
- Background I/O (Spotlight indexing, Time Machine, antivirus scans)
- Thermal throttling under sustained load
- Power management (laptop on battery vs. plugged in)

**How to minimise variance today:**

- Run on a quiet machine — close other applications before recording a baseline
- Use `--repeat 20` or higher; merf uses the median, which absorbs isolated slow outliers
- For CI, use a **dedicated runner** with no competing workloads scheduled alongside it
- merf will warn you on stderr if system load is high before collecting samples
- Record the baseline on the same machine class you intend to run checks on — a baseline from a MacBook M3 is not meaningful when checked on a CI runner with different CPU characteristics

**On Docker:** Docker on macOS runs your process inside a Linux VM, which adds its own scheduling overhead and makes timing _less_ reliable, not more. merf does not support container isolation for this reason.

**Plans for reduced variability:** Recording hardware context (CPU model, core count) alongside the baseline, so merf can warn when a `check` is run on a meaningfully different machine than where the baseline was recorded.
