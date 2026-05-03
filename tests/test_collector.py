import os
import sys

import pytest

from merf.collector import MIN_REPEAT, collect_samples


class TestSampleCount:
    """collect_samples must return exactly `repeat` samples — not repeat + warmup."""

    def test_returns_exactly_repeat_samples(self) -> None:
        samples = collect_samples((sys.executable, "-c", "pass"), repeat=5)
        assert len(samples) == 5


    def test_larger_repeat_returns_correspondingly_more_samples(self) -> None:
        samples = collect_samples((sys.executable, "-c", "pass"), repeat=8)
        assert len(samples) == 8


class TestMinimumRepeat:
    """Fewer than MIN_REPEAT samples produces unreliable percentiles; enforce the floor."""

    def test_below_floor_raises(self) -> None:
        # The error message must mention the minimum so the user knows what to change
        with pytest.raises(ValueError, match=str(MIN_REPEAT)):
            collect_samples((sys.executable, "-c", "pass"), repeat=MIN_REPEAT - 1)

    def test_at_floor_succeeds(self) -> None:
        samples = collect_samples((sys.executable, "-c", "pass"), repeat=MIN_REPEAT)
        assert len(samples) == MIN_REPEAT

    def test_zero_repeat_raises(self) -> None:
        with pytest.raises(ValueError):
            collect_samples((sys.executable, "-c", "pass"), repeat=0)


class TestSampleValues:
    """Each returned sample must be a positive float (wall-clock seconds)."""

    def test_all_samples_are_positive_floats(self) -> None:
        samples = collect_samples((sys.executable, "-c", "pass"), repeat=5)
        assert all(isinstance(s, float) and s > 0 for s in samples)


class TestVerbosePassthrough:
    """The verbose flag must be forwarded to every runner invocation, including warmup."""

    def test_output_suppressed_by_default(self, capfd: pytest.CaptureFixture[str]) -> None:
        collect_samples((sys.executable, "-c", "print('hello')"), repeat=5)
        assert capfd.readouterr().out == ""

    def test_output_shown_when_verbose(self, capfd: pytest.CaptureFixture[str]) -> None:
        # With verbose=True each run (including warmup) prints "hello",
        # so we expect it to appear at least once
        collect_samples((sys.executable, "-c", "print('hello')"), repeat=5, verbose=True)
        assert "hello" in capfd.readouterr().out


class TestLoadCheck:
    """A high system load must produce a warning on stderr before sampling begins.

    Uses monkeypatch to control os.getloadavg() without needing a genuinely busy machine.
    The load warning is written by Python code (not a subprocess), so capsys captures it.
    """

    def test_warns_on_stderr_when_load_is_high(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Patch both values so the test is fully self-contained regardless of machine.
        # 4 cores, load of 8.0 → always 200% capacity, always above the threshold.
        monkeypatch.setattr(os, "cpu_count", lambda: 4)
        monkeypatch.setattr(os, "getloadavg", lambda: (8.0, 0.0, 0.0))
        collect_samples((sys.executable, "-c", "pass"), repeat=MIN_REPEAT)
        assert "load" in capsys.readouterr().err.lower()

    def test_no_warning_when_load_is_normal(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Patch both for symmetry with the high-load test.
        # 4 cores, load of 0.1 → always well below the threshold.
        monkeypatch.setattr(os, "cpu_count", lambda: 4)
        monkeypatch.setattr(os, "getloadavg", lambda: (0.1, 0.1, 0.1))
        collect_samples((sys.executable, "-c", "pass"), repeat=MIN_REPEAT)
        assert capsys.readouterr().err == ""


class TestCommandFailure:
    """If any run exits with a non-zero code, collect_samples must raise immediately."""

    def test_nonzero_exit_raises(self) -> None:
        with pytest.raises(RuntimeError, match="exit code 1"):
            collect_samples((sys.executable, "-c", "raise SystemExit(1)"), repeat=5)

    def test_exit_code_included_in_error(self) -> None:
        # The specific exit code must appear in the message so the user knows what failed
        with pytest.raises(RuntimeError, match="exit code 42"):
            collect_samples(
                (sys.executable, "-c", "raise SystemExit(42)"), repeat=5
            )
