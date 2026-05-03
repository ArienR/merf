import sys

from click.testing import CliRunner

from merf.cli import _derive_name, main


class TestDeriveName:
    def test_is_deterministic(self) -> None:
        cmd = (sys.executable, "-c", "pass")
        assert _derive_name(cmd) == _derive_name(cmd)

    def test_returns_12_hex_characters(self) -> None:
        result = _derive_name((sys.executable, "-c", "pass"))
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_differs_for_different_commands(self) -> None:
        a = _derive_name((sys.executable, "-c", "pass"))
        b = _derive_name((sys.executable, "-c", "import sys; sys.exit(0)"))
        assert a != b


class TestCheckMissingBaseline:
    def test_exits_nonzero_when_no_baseline(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["check", "--name", "no-such-baseline", "--", sys.executable, "-c", "pass"])
        assert result.exit_code != 0

    def test_error_message_names_the_baseline(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["check", "--name", "no-such-baseline", "--", sys.executable, "-c", "pass"])
        assert "no-such-baseline" in result.output

    def test_error_message_hints_at_fix(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["check", "--name", "no-such-baseline", "--", sys.executable, "-c", "pass"])
        assert "merf baseline" in result.output
