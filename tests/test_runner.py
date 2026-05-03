import sys

import pytest

from merf.runner import run_command


class TestExitCode:
    """The runner must faithfully report whatever exit code the command produced."""

    def test_successful_command_returns_zero(self) -> None:
        result = run_command((sys.executable, "-c", "pass"))
        assert result.exit_code == 0

    def test_failing_command_returns_nonzero(self) -> None:
        result = run_command((sys.executable, "-c", "raise SystemExit(1)"))
        assert result.exit_code == 1

    def test_exit_code_is_preserved_exactly(self) -> None:
        # Verify the runner passes through arbitrary exit codes, not just 0/1
        result = run_command((sys.executable, "-c", "raise SystemExit(42)"))
        assert result.exit_code == 42


class TestTiming:
    """Elapsed time must be a positive float that reflects actual command duration."""

    def test_elapsed_is_positive(self) -> None:
        result = run_command((sys.executable, "-c", "pass"))
        assert result.elapsed > 0

    def test_elapsed_reflects_command_duration(self) -> None:
        # A command that sleeps 0.1s must produce elapsed >= that duration.
        # The upper bound is generous to avoid flakiness on slow CI runners.
        result = run_command((sys.executable, "-c", "import time; time.sleep(0.1)"))
        assert 0.09 <= result.elapsed < 10.0

    def test_elapsed_is_float(self) -> None:
        result = run_command((sys.executable, "-c", "pass"))
        assert isinstance(result.elapsed, float)


class TestOutputSuppression:
    """stdout and stderr must be suppressed by default and visible when verbose=True.

    These tests use capfd (file-descriptor capture) rather than capsys because
    subprocess output goes directly to OS-level file descriptors, which capsys
    (Python-level capture) does not intercept.
    """

    def test_stdout_suppressed_by_default(self, capfd: pytest.CaptureFixture[str]) -> None:
        run_command((sys.executable, "-c", "print('hello')"))
        assert capfd.readouterr().out == ""

    def test_stderr_suppressed_by_default(self, capfd: pytest.CaptureFixture[str]) -> None:
        run_command((sys.executable, "-c", "import sys; sys.stderr.write('err\n')"))
        assert capfd.readouterr().err == ""

    def test_stdout_shown_when_verbose(self, capfd: pytest.CaptureFixture[str]) -> None:
        run_command((sys.executable, "-c", "print('hello')"), verbose=True)
        assert "hello" in capfd.readouterr().out

    def test_stderr_shown_when_verbose(self, capfd: pytest.CaptureFixture[str]) -> None:
        run_command((sys.executable, "-c", "import sys; sys.stderr.write('err\n')"), verbose=True)
        assert "err" in capfd.readouterr().err


class TestEdgeCases:
    def test_command_not_found_raises(self) -> None:
        # The runner does not swallow FileNotFoundError — the caller decides what to do
        with pytest.raises(FileNotFoundError):
            run_command(("__merf_nonexistent_command__",))

    def test_arguments_are_passed_to_command(self) -> None:
        # Verifies arguments beyond the executable name actually reach the subprocess
        result = run_command(
            (sys.executable, "-c", "import sys; sys.exit(int(sys.argv[1]))", "7")
        )
        assert result.exit_code == 7

    def test_command_producing_both_outputs_suppressed(
        self, capfd: pytest.CaptureFixture[str]
    ) -> None:
        # Both stdout and stderr must be suppressed simultaneously, not just one
        run_command((
            sys.executable,
            "-c",
            "import sys; print('out'); sys.stderr.write('err\n')",
        ))
        captured = capfd.readouterr()
        assert captured.out == ""
        assert captured.err == ""
