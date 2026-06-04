"""Run logging and aggregate metrics for workflow adoption."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunRecord:
    """One workflow run, designed to be append-only and audit-friendly."""

    workflow: str
    actor: str
    passed: bool
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    pii_redactions: int = 0
    manual_baseline_seconds: float | None = None
    ts: float = field(default_factory=time.time)

    @property
    def time_saved_seconds(self) -> float | None:
        """Return measured time saved when a manual baseline is provided."""
        if self.manual_baseline_seconds is None:
            return None
        return round(self.manual_baseline_seconds - self.duration_seconds, 2)


class RunLog:
    """Append-only JSONL run log."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: RunRecord) -> None:
        """Append one run to disk."""
        row = asdict(record)
        row["time_saved_seconds"] = record.time_saved_seconds
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    def read(self) -> list[dict[str, Any]]:
        """Read valid JSONL rows. Empty logs return an empty list."""
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate run records by workflow."""
    if not rows:
        return {"runs": 0, "by_workflow": {}}

    by_workflow: dict[str, dict[str, Any]] = {}
    total_saved = 0.0
    saved_known = 0

    for row in rows:
        workflow = str(row["workflow"])
        rollup = by_workflow.setdefault(
            workflow,
            {
                "runs": 0,
                "passed": 0,
                "pii_redactions": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
        )
        rollup["runs"] += 1
        rollup["passed"] += int(bool(row.get("passed", False)))
        rollup["pii_redactions"] += int(row.get("pii_redactions", 0))
        rollup["input_tokens"] += int(row.get("input_tokens", 0))
        rollup["output_tokens"] += int(row.get("output_tokens", 0))

        time_saved = row.get("time_saved_seconds")
        if time_saved is not None:
            total_saved += float(time_saved)
            saved_known += 1

    for rollup in by_workflow.values():
        rollup["pass_rate"] = round(rollup["passed"] / rollup["runs"], 3)

    return {
        "runs": len(rows),
        "actors": sorted({str(row["actor"]) for row in rows}),
        "by_workflow": by_workflow,
        "time_saved_seconds_total": round(total_saved, 2) if saved_known else None,
        "time_saved_runs_with_baseline": saved_known,
    }
