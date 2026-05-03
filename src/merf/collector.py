import os
import sys

from merf.runner import run_command

MIN_REPEAT = 5
WARMUP_RUNS = 2
_LOAD_THRESHOLD = 0.8


def collect_samples(
    command: tuple[str, ...],
    repeat: int,
    verbose: bool = False,
) -> list[float]:
    if repeat < MIN_REPEAT:
        raise ValueError(
            f"--repeat must be at least {MIN_REPEAT}. "
            "Fewer samples produce unreliable percentiles."
        )

    _check_load()

    samples: list[float] = []
    for i in range(WARMUP_RUNS + repeat):
        result = run_command(command, verbose=verbose)
        if result.exit_code != 0:
            raise RuntimeError(
                f"Command exited with exit code {result.exit_code}. "
                "merf requires all runs to succeed."
            )
        if i >= WARMUP_RUNS:
            samples.append(result.elapsed)

    return samples


def _check_load() -> None:
    cpu_count = os.cpu_count() or 1
    load = os.getloadavg()[0]
    if load > cpu_count * _LOAD_THRESHOLD:
        print(
            f"⚠  System load is high ({load:.1f} on {cpu_count} cores). "
            "Measurements may be noisy.",
            file=sys.stderr,
        )
