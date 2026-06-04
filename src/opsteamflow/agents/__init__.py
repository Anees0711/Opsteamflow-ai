
from __future__ import annotations

from dataclasses import dataclass, field

from ..governance import redact, screen
from ..llm import LLMClient, default_client


@dataclass(frozen=True)
class Guardrails:
    """Per-agent safety controls."""

    block_unsafe: bool = True
    redact_pii: bool = True
    max_output_tokens: int = 700


@dataclass
class AgentStep:
    """One completed agent step."""

    agent: str
    role: str
    output: str
    safety_flags: list[str] = field(default_factory=list)
    redaction_counts: dict[str, int] = field(default_factory=dict)
    blocked: bool = False


@dataclass(frozen=True)
class Agent:
    """An inspectable agent with a role, system instruction, and guardrails."""

    name: str
    role: str
    system: str
    guardrails: Guardrails = field(default_factory=Guardrails)

    def act(self, task: str, transcript: str, client: LLMClient) -> AgentStep:
        """Run one guarded agent step against the task and current transcript."""
        prompt = task if not transcript else f"{transcript}\n\nNEXT TASK:\n{task}"

        safety_flags: list[str] = []
        if self.guardrails.block_unsafe:
            safety = screen(prompt)
            safety_flags = safety.flags
            if not safety.allowed:
                return AgentStep(
                    agent=self.name,
                    role=self.role,
                    output="",
                    safety_flags=safety_flags,
                    blocked=True,
                )

        redaction_counts: dict[str, int] = {}
        if self.guardrails.redact_pii:
            report = redact(prompt)
            prompt = report.clean_text
            redaction_counts = report.counts

        response = client.complete(
            prompt,
            system=self.system,
            max_tokens=self.guardrails.max_output_tokens,
        )
        return AgentStep(
            agent=self.name,
            role=self.role,
            output=response.text,
            safety_flags=safety_flags,
            redaction_counts=redaction_counts,
        )


@dataclass
class WorkflowResult:
    """Result of a sequential multi-agent workflow."""

    steps: list[AgentStep]

    @property
    def final(self) -> str:
        """Return the last non-blocked output."""
        for step in reversed(self.steps):
            if not step.blocked and step.output:
                return step.output
        return ""

    @property
    def blocked(self) -> bool:
        """Whether any agent step was blocked by guardrails."""
        return any(step.blocked for step in self.steps)


class Workflow:
    """Runs agents in order. Each agent sees the transcript so far."""

    def __init__(self, agents: list[Agent], client: LLMClient | None = None) -> None:
        self.agents = agents
        self.client = client or default_client()

    def run(self, task: str) -> WorkflowResult:
        """Run all agents until completion or a guardrail block."""
        steps: list[AgentStep] = []
        transcript = ""
        next_task = task

        for agent in self.agents:
            step = agent.act(next_task, transcript, self.client)
            steps.append(step)
            if step.blocked:
                break
            transcript += f"\n\n[{agent.role}:{agent.name}]\n{step.output}"
            next_task = "Continue from the transcript above."

        return WorkflowResult(steps=steps)
