"""YAML playbooks that combine context, guardrails, LLM calls, and checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..context import ContextAssembler, ContextRegistry
from ..eval import Score, contains_score, grounding_score, schema_score
from ..governance import redact, screen
from ..llm import LLMClient, default_client


@dataclass(frozen=True)
class PlaybookChecks:
    """Success checks owned by a playbook."""

    required_keys: list[str] = field(default_factory=list)
    contains: list[str] = field(default_factory=list)
    min_grounding: float | None = None

    @property
    def configured(self) -> bool:
        """Whether at least one check is configured."""
        return bool(self.required_keys or self.contains or self.min_grounding is not None)


@dataclass(frozen=True)
class Playbook:
    """A repeatable AI workflow loaded from YAML."""

    name: str
    goal: str
    prompt_template: str
    inputs: list[str] = field(default_factory=list)
    context_packs: list[str] = field(default_factory=list)
    checks: PlaybookChecks = field(default_factory=PlaybookChecks)
    system: str | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> Playbook:
        """Load and validate a playbook from YAML."""
        raw = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError(f"playbook {path} must be a YAML object")
        if "name" not in data or "prompt_template" not in data:
            raise ValueError(f"playbook {path} needs 'name' and 'prompt_template'")

        checks = data.get("checks", {}) or {}
        return cls(
            name=str(data["name"]),
            goal=str(data.get("goal", "")),
            prompt_template=str(data["prompt_template"]),
            inputs=[str(item) for item in data.get("inputs", [])],
            context_packs=[str(item) for item in data.get("context_packs", [])],
            system=data.get("system"),
            checks=PlaybookChecks(
                required_keys=[str(item) for item in checks.get("required_keys", [])],
                contains=[str(item) for item in checks.get("contains", [])],
                min_grounding=checks.get("min_grounding"),
            ),
        )


@dataclass(frozen=True)
class PlaybookRun:
    """Auditable result of one playbook run."""

    output: str
    scores: dict[str, Score]
    redaction_counts: dict[str, int]
    context_manifest: list[dict[str, Any]]
    safety_flags: list[str]

    @property
    def passed(self) -> bool:
        """A playbook without checks should not silently pass."""
        return bool(self.scores) and all(score.passed for score in self.scores.values())


class PlaybookRunner:
    """Executes playbooks through a guarded, measurable path."""

    def __init__(
        self,
        registry: ContextRegistry | None = None,
        client: LLMClient | None = None,
        token_budget: int = 4000,
    ) -> None:
        self.registry = registry
        self.client = client or default_client()
        self.assembler = ContextAssembler(token_budget=token_budget)

    def run(self, playbook: Playbook, inputs: dict[str, object]) -> PlaybookRun:
        """Run a playbook with validated inputs."""
        missing = [name for name in playbook.inputs if name not in inputs]
        if missing:
            raise ValueError(f"missing inputs: {', '.join(missing)}")

        filled = playbook.prompt_template.format(**inputs)
        safety = screen(filled)
        if not safety.allowed:
            raise PermissionError(f"prompt blocked by safety screen: {', '.join(safety.flags)}")

        redaction_report = redact(filled)
        prompt = redaction_report.clean_text
        context_block = ""
        manifest: list[dict[str, Any]] = []

        if playbook.context_packs:
            if not self.registry:
                raise RuntimeError("playbook needs context packs but no registry was given")
            packs = [self.registry.get(name) for name in playbook.context_packs]
            context_block, manifest = self.assembler.assemble(packs)
            prompt = f"{context_block}\n\n{prompt}"

        response = self.client.complete(prompt, system=playbook.system, max_tokens=800)
        scores = self._score_output(playbook, response.text, context_block or prompt)

        return PlaybookRun(
            output=response.text,
            scores=scores,
            redaction_counts=redaction_report.counts,
            context_manifest=manifest,
            safety_flags=safety.flags,
        )

    @staticmethod
    def _score_output(
        playbook: Playbook,
        output: str,
        grounding_context: str,
    ) -> dict[str, Score]:
        """Apply configured playbook checks."""
        scores: dict[str, Score] = {}
        if playbook.checks.required_keys:
            scores["schema"] = schema_score(output, playbook.checks.required_keys)
        if playbook.checks.contains:
            scores["contains"] = contains_score(output, playbook.checks.contains)
        if playbook.checks.min_grounding is not None:
            grounding = grounding_score(output, grounding_context)
            min_grounding = playbook.checks.min_grounding
            reason = grounding.reason
            if grounding.value < min_grounding:
                reason = f"{grounding.reason} below {min_grounding}"
            else:
                reason = f"{grounding.reason} (need {min_grounding})"
            scores["grounding"] = Score(grounding.value, reason)
        return scores
