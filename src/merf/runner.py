import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RunResult:
    elapsed: float
    exit_code: int


def run_command(command: tuple[str, ...], verbose: bool = False) -> RunResult:
    stdout = None if verbose else subprocess.DEVNULL
    stderr = None if verbose else subprocess.DEVNULL

    start = time.perf_counter()
    result = subprocess.run(command, stdout=stdout, stderr=stderr)
    elapsed = time.perf_counter() - start

    return RunResult(elapsed=elapsed, exit_code=result.returncode)
