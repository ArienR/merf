import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
_MERF_DIR = Path(".merf")


@dataclass(frozen=True)
class BaselineData:
    version: int
    name: str
    command: str
    repeat: int
    warmup_runs: int
    samples_seconds: list[float]
    median: float
    p95: float
    recorded_at: str


def save_baseline(name: str, data: BaselineData) -> None:
    _MERF_DIR.mkdir(exist_ok=True)
    path = _MERF_DIR / f"{name}.json"
    path.write_text(json.dumps(dataclasses.asdict(data), indent=2), encoding="utf-8")


def load_baseline(name: str) -> BaselineData:
    path = _MERF_DIR / f"{name}.json"

    if not path.exists():
        raise FileNotFoundError(
            f'No baseline found for "{name}". Run merf baseline first.'
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Corrupted baseline file at {path}: {exc}") from exc

    if raw.get("version") != SCHEMA_VERSION:
        raise ValueError(
            f"Baseline version mismatch: file has version {raw.get('version')!r}, "
            f"but this version of merf uses version {SCHEMA_VERSION}. "
            "Re-record the baseline with 'merf baseline'."
        )

    try:
        return BaselineData(
            version=raw["version"],
            name=raw["name"],
            command=raw["command"],
            repeat=raw["repeat"],
            warmup_runs=raw["warmup_runs"],
            samples_seconds=raw["samples_seconds"],
            median=raw["median"],
            p95=raw["p95"],
            recorded_at=raw["recorded_at"],
        )
    except KeyError as exc:
        raise ValueError(f"Baseline file is missing required field: {exc}") from exc
