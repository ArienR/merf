import click


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
    pass


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
    pass
