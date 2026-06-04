"""Offline regression gate for CI.

The gate fails when the committed playbook output no longer meets the expected
schema score. It uses FakeClient by default, so it can run in pull requests
without network access or model spend.
"""

from __future__ import annotations

import sys
from pathlib import Path

from opsteamflow.eval import EvalCase, run_suite, schema_score
from opsteamflow.llm import FakeClient
from opsteamflow.playbook import Playbook, PlaybookRunner

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_DIR = ROOT / "examples" / "playbooks"
THRESHOLD = 1.0


def main() -> int:
    """Return a process exit code based on the eval pass rate."""
    runner = PlaybookRunner(client=FakeClient())
    cases = [
        EvalCase(
            "release_note_schema",
            {"changes": "added SSO; fixed export"},
            lambda output: schema_score(output, ["title", "summary", "highlights"]),
        ),
    ]
    report = run_suite(
        cases,
        produce=lambda inputs: runner.run(
            Playbook.from_file(PLAYBOOK_DIR / "release_note.yaml"), inputs
        ).output,
    )

    print(f"eval pass_rate={report.pass_rate} (threshold {THRESHOLD})")
    if report.pass_rate < THRESHOLD:
        print("FAIL: eval pass rate below threshold")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
