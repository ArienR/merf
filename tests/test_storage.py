import dataclasses
import json
from pathlib import Path

import pytest

from merf.storage import SCHEMA_VERSION, BaselineData, load_baseline, save_baseline


def _baseline(name: str = "test") -> BaselineData:
    """Return a valid BaselineData instance with a configurable name."""
    return BaselineData(
        version=SCHEMA_VERSION,
        name=name,
        command="python scripts/parse.py data.csv",
        repeat=5,
        warmup_runs=2,
        samples_seconds=[0.301, 0.298, 0.305, 0.312, 0.309],
        median=0.305,
        p95=0.312,
        recorded_at="2026-05-02T10:00:00Z",
    )


class TestRoundTrip:
    """save_baseline followed by load_baseline must reproduce the original data exactly.

    These tests verify the serialisation/deserialisation contract — every field
    that goes in must come back out unchanged, including nested lists and floats.
    """

    def test_all_fields_preserved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The loaded object must be equal to the saved one field-for-field.
        monkeypatch.chdir(tmp_path)
        original = _baseline("parse-csv")
        save_baseline("parse-csv", original)
        assert load_baseline("parse-csv") == original

    def test_samples_list_preserved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Raw samples are stored so future merf versions can recompute stats
        # (e.g. add p99). Verify the list survives the JSON round-trip intact.
        monkeypatch.chdir(tmp_path)
        original = _baseline()
        save_baseline("test", original)
        loaded = load_baseline("test")
        assert loaded.samples_seconds == pytest.approx(original.samples_seconds)

    def test_float_precision_preserved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Python's json module round-trips IEEE 754 doubles accurately.
        # Verify that a value with many decimal places is not truncated.
        precise = BaselineData(
            version=SCHEMA_VERSION,
            name="precision",
            command="test",
            repeat=5,
            warmup_runs=2,
            samples_seconds=[0.123456789],
            median=0.123456789,
            p95=0.123456789,
            recorded_at="2026-05-02T10:00:00Z",
        )
        monkeypatch.chdir(tmp_path)
        save_baseline("precision", precise)
        loaded = load_baseline("precision")
        assert loaded.median == pytest.approx(0.123456789)

    def test_overwrite_replaces_previous_baseline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Saving under an existing name is how merf updates a baseline.
        # The old data must not bleed through after an overwrite.
        monkeypatch.chdir(tmp_path)
        save_baseline("parse-csv", _baseline("parse-csv"))

        newer = BaselineData(
            version=SCHEMA_VERSION,
            name="parse-csv",
            command="python scripts/parse.py data.csv",
            repeat=5,
            warmup_runs=2,
            samples_seconds=[0.250, 0.255, 0.260, 0.248, 0.252],
            median=0.252,
            p95=0.260,
            recorded_at="2026-05-03T10:00:00Z",
        )
        save_baseline("parse-csv", newer)

        loaded = load_baseline("parse-csv")
        assert loaded.median == pytest.approx(0.252)
        assert loaded.recorded_at == "2026-05-03T10:00:00Z"


class TestFileLayout:
    """Baselines must be stored as .merf/<name>.json relative to the working directory.

    The .merf/ directory is created on first save if it doesn't already exist.
    The file must be valid JSON so it can be inspected, diffed, and committed.
    """

    def test_creates_merf_directory_if_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A fresh project has no .merf/ yet. The first save must create it.
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / ".merf").exists()
        save_baseline("test", _baseline())
        assert (tmp_path / ".merf").is_dir()

    def test_does_not_fail_if_merf_directory_already_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Subsequent saves must not error because the directory already exists.
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".merf").mkdir()
        save_baseline("test", _baseline())
        assert (tmp_path / ".merf" / "test.json").is_file()

    def test_file_path_matches_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        save_baseline("parse-csv", _baseline("parse-csv"))
        assert (tmp_path / ".merf" / "parse-csv.json").is_file()

    def test_saved_file_is_valid_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Baselines are committed to version control and may be read by
        # other tools or humans. The file must be valid, readable JSON.
        monkeypatch.chdir(tmp_path)
        save_baseline("parse-csv", _baseline("parse-csv"))
        raw = (tmp_path / ".merf" / "parse-csv.json").read_text()
        data = json.loads(raw)
        assert data["name"] == "parse-csv"
        assert data["version"] == SCHEMA_VERSION

    def test_different_names_produce_separate_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Multiple baselines must coexist in .merf/ without overwriting each other.
        monkeypatch.chdir(tmp_path)
        save_baseline("benchmark-a", _baseline("benchmark-a"))
        save_baseline("benchmark-b", _baseline("benchmark-b"))
        assert (tmp_path / ".merf" / "benchmark-a.json").is_file()
        assert (tmp_path / ".merf" / "benchmark-b.json").is_file()
        assert load_baseline("benchmark-a").name == "benchmark-a"
        assert load_baseline("benchmark-b").name == "benchmark-b"


class TestLoadErrors:
    """load_baseline must fail clearly when data is missing, incompatible, or corrupt.

    Silent failure (returning None, returning wrong data) is worse than raising,
    so each error condition must raise with a message that tells the user what to do.
    """

    def test_missing_baseline_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The name must appear in the error so the user knows which baseline is missing.
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match="parse-csv"):
            load_baseline("parse-csv")

    def test_missing_baseline_hints_at_fix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The error message should point the user toward the fix rather than
        # just saying the file was not found.
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match="merf baseline"):
            load_baseline("parse-csv")

    def test_version_above_current_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A baseline written by a newer merf may use fields this version doesn't
        # understand. Silently loading it risks computing wrong results, so merf
        # must refuse and tell the user to upgrade.
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".merf").mkdir()
        future = {**dataclasses.asdict(_baseline("test")), "version": SCHEMA_VERSION + 1}
        (tmp_path / ".merf" / "test.json").write_text(json.dumps(future))
        with pytest.raises(ValueError, match="version"):
            load_baseline("test")

    def test_version_below_current_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An old baseline from before the current schema is equally unsafe.
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".merf").mkdir()
        old = {**dataclasses.asdict(_baseline("test")), "version": SCHEMA_VERSION - 1}
        (tmp_path / ".merf" / "test.json").write_text(json.dumps(old))
        with pytest.raises(ValueError, match="version"):
            load_baseline("test")

    def test_corrupted_json_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A partially written or manually edited file that is no longer valid JSON
        # must raise rather than return garbage data.
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".merf").mkdir()
        (tmp_path / ".merf" / "broken.json").write_text("not valid json {{{")
        with pytest.raises(ValueError, match="[Cc]orrupt"):
            load_baseline("broken")

    def test_missing_required_field_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Valid JSON that is missing fields (e.g. hand-edited baseline) must raise
        # a clean ValueError rather than crashing with KeyError or AttributeError.
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".merf").mkdir()
        (tmp_path / ".merf" / "partial.json").write_text(
            json.dumps({"version": SCHEMA_VERSION, "name": "partial"})
        )
        with pytest.raises(ValueError):
            load_baseline("partial")


class TestNameVariations:
    """Common name formats must all produce valid, loadable baselines."""

    def test_hyphenated_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        save_baseline("parse-csv", _baseline("parse-csv"))
        assert load_baseline("parse-csv").name == "parse-csv"

    def test_underscored_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        save_baseline("parse_csv", _baseline("parse_csv"))
        assert load_baseline("parse_csv").name == "parse_csv"

    def test_hash_style_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When --name is omitted the CLI derives a 12-char hex name from the
        # command hash. Verify storage handles this format correctly.
        monkeypatch.chdir(tmp_path)
        save_baseline("a1b2c3d4e5f6", _baseline("a1b2c3d4e5f6"))
        assert load_baseline("a1b2c3d4e5f6").name == "a1b2c3d4e5f6"
