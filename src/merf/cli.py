import hashlib
import json as json_module
import sys
from datetime import datetime, timezone

import click

from merf.collector import WARMUP_RUNS, collect_samples
from merf.stats import compute_stats
from merf.storage import SCHEMA_VERSION, BaselineData, load_baseline, save_baseline


def _derive_name(command: tuple[str, ...]) -> str:
    return hashlib.sha256(" ".join(command).encode()).hexdigest()[:12]


@click.group()
def main() -> None:
    """merf — minimal performance regression detector."""


@main.command()
@click.option("--name", default=None, help="Baseline name. Defaults to a hash of the command.")
@click.option("--repeat", default=10, show_default=True, help="Number of timed samples (minimum 5).")
@click.option("--verbose", is_flag=True, default=False, help="Stream the command's stdout/stderr.")
@click.argument("command", nargs=-1, type=click.UNPROCESSED, required=True)
def baseline(name: str | None, repeat: int, verbose: bool, command: tuple[str, ...]) -> None:
    """Record a performance baseline for COMMAND."""
    if name is None:
        name = _derive_name(command)
        click.echo(f"No --name given; using hash-derived name: {name}", err=True)

    command_str = " ".join(command)

    try:
        samples = collect_samples(command, repeat=repeat, verbose=verbose)
    except (ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    stats = compute_stats(samples)

    data = BaselineData(
        version=SCHEMA_VERSION,
        name=name,
        command=command_str,
        repeat=repeat,
        warmup_runs=WARMUP_RUNS,
        samples_seconds=samples,
        median=stats.median,
        p95=stats.p95,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    save_baseline(name, data)

    w = len("merf baseline")
    click.echo(f"{'merf baseline':{w}}  |  {name}")
    click.echo(f"{'command':{w}}  |  {command_str}")
    click.echo(f"{'runs':{w}}  |  {repeat} (+ {WARMUP_RUNS} warmup discarded)")
    click.echo()
    click.echo(f"  median       {stats.median:.3f}s")
    click.echo(f"  p95          {stats.p95:.3f}s")
    click.echo()
    click.echo(f"Baseline saved to .merf/{name}.json")


@main.command()
@click.option("--name", default=None, help="Baseline name to compare against.")
@click.option("--repeat", default=10, show_default=True, help="Number of timed samples (minimum 5).")
@click.option("--max-regression", default=10.0, show_default=True, help="Fail threshold as a percentage.")
@click.option("--json", "output_json", is_flag=True, default=False, help="Emit structured JSON result.")
@click.option("--verbose", is_flag=True, default=False, help="Stream the command's stdout/stderr.")
@click.argument("command", nargs=-1, type=click.UNPROCESSED, required=True)
def check(
    name: str | None,
    repeat: int,
    max_regression: float,
    output_json: bool,
    verbose: bool,
    command: tuple[str, ...],
) -> None:
    """Check COMMAND for performance regression against a stored baseline."""
    if name is None:
        name = _derive_name(command)

    command_str = " ".join(command)

    try:
        stored = load_baseline(name)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        samples = collect_samples(command, repeat=repeat, verbose=verbose)
    except (ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    stats = compute_stats(samples)

    if stored.median == 0.0:
        raise click.ClickException("Baseline median is zero — cannot compute regression percentage.")

    delta_percent = (stats.median - stored.median) / stored.median * 100
    p95_delta_percent = (stats.p95 - stored.p95) / stored.p95 * 100 if stored.p95 != 0.0 else 0.0
    passed = delta_percent <= max_regression

    w = len("merf check")
    click.echo(f"{'merf check':{w}}  |  {name}")
    click.echo(f"{'command':{w}}  |  {command_str}")
    click.echo(f"{'runs':{w}}  |  {repeat} (+ {WARMUP_RUNS} warmup discarded)")
    click.echo()
    click.echo(f"             baseline    current    delta")
    click.echo(f"  median     {stored.median:.3f}s      {stats.median:.3f}s     {delta_percent:+.1f}%")
    click.echo(f"  p95        {stored.p95:.3f}s      {stats.p95:.3f}s     {p95_delta_percent:+.1f}%")
    click.echo()
    click.echo(f"  threshold  {max_regression:.0f}%")

    if passed:
        click.echo("  result     PASS")
    else:
        click.echo(f"  result     FAIL  ({delta_percent:+.1f}% exceeds {max_regression:.0f}% threshold)")

    if output_json:
        click.echo(json_module.dumps({
            "name": name,
            "result": "pass" if passed else "fail",
            "threshold_percent": max_regression,
            "baseline_median": stored.median,
            "current_median": stats.median,
            "delta_percent": round(delta_percent, 1),
            "baseline_p95": stored.p95,
            "current_p95": stats.p95,
        }, indent=2))

    if not passed:
        sys.exit(1)
