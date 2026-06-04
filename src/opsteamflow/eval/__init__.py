"""Simple evaluation helpers and regression runner."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Score:
    """Numeric score with a human-readable reason."""

    value: float
    reason: str

    @property
    def passed(self) -> bool:
        """Default pass rule used by playbooks and eval reports."""
        return self.value >= 0.5


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def grounding_score(answer: str, context: str, threshold: float = 0.3) -> Score:
    """Score how many answer sentences overlap with the supplied context.

    This is a lightweight proxy, not a truth meter. It is useful as a CI tripwire
    for obvious drift, but it does not prove entailment.
    """
    context_tokens = _tokens(context)
    if not context_tokens:
        return Score(0.0, "empty context")

    sentences = _sentences(answer)
    if not sentences:
        return Score(0.0, "empty answer")

    supported = 0
    for sentence in sentences:
        sentence_tokens = _tokens(sentence)
        if not sentence_tokens:
            continue
        overlap = len(sentence_tokens & context_tokens) / len(sentence_tokens)
        if overlap >= threshold:
            supported += 1

    value = supported / len(sentences)
    return Score(value, f"{supported}/{len(sentences)} sentences grounded")


def schema_score(output: str, required_keys: list[str]) -> Score:
    """Score whether output is valid JSON and contains required keys."""
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return Score(0.0, "not valid JSON")

    if not isinstance(data, dict):
        return Score(0.0, "JSON is not an object")

    missing = [key for key in required_keys if key not in data]
    if missing:
        return Score(0.0, f"missing keys: {', '.join(missing)}")
    return Score(1.0, "all required keys present")


def contains_score(output: str, expected: list[str]) -> Score:
    """Score whether expected phrases are present in output."""
    if not expected:
        return Score(1.0, "no expectations")

    normalized = output.lower()
    hits = [phrase for phrase in expected if phrase.lower() in normalized]
    return Score(len(hits) / len(expected), f"{len(hits)}/{len(expected)} matched")


@dataclass(frozen=True)
class EvalCase:
    """One eval input plus the scorer used to judge it."""

    name: str
    inputs: dict[str, object]
    scorer: Callable[[str], Score]


@dataclass(frozen=True)
class CaseResult:
    """Result for one eval case."""

    name: str
    score: Score


@dataclass
class EvalReport:
    """Aggregated report for an eval suite."""

    results: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        """Number of passing cases."""
        return sum(1 for result in self.results if result.score.passed)

    @property
    def total(self) -> int:
        """Total number of cases."""
        return len(self.results)

    @property
    def pass_rate(self) -> float:
        """Passing cases divided by total cases."""
        return self.passed / self.total if self.total else 0.0

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable report."""
        return {
            "passed": self.passed,
            "total": self.total,
            "pass_rate": round(self.pass_rate, 3),
            "cases": [
                {
                    "name": result.name,
                    "value": round(result.score.value, 3),
                    "passed": result.score.passed,
                    "reason": result.score.reason,
                }
                for result in self.results
            ],
        }


def run_suite(cases: list[EvalCase], produce: Callable[[dict[str, object]], str]) -> EvalReport:
    """Run eval cases by passing each case input to the provided producer."""
    report = EvalReport()
    for case in cases:
        output = produce(case.inputs)
        report.results.append(CaseResult(case.name, case.scorer(output)))
    return report
