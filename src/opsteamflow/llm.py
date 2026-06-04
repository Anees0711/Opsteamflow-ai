####  LLM client


from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = "end_turn"


@runtime_checkable
class LLMClient(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        max_tokens: int = ...,
        temperature: float = ...,
    ) -> LLMResponse: ...


# Real client


class AnthropicClient:
    """Wraps the official anthropic SDK.

    Kept intentionally small. We do not stream here because every caller in
    this project wants a whole answer before scoring it.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "anthropic SDK not installed. `pip install anthropic` "
                "or use FakeClient for offline runs."
            ) from exc
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set.")
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = self._client.messages.create(**kwargs)
        text = "".join(block.text for block in msg.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            stop_reason=msg.stop_reason or "end_turn",
        )


# Offline deterministic client
@dataclass
class FakeClient:
    """Deterministic offline client.

    It is not trying to be smart. It does three useful things so that the
    rest of the system can be exercised end to end without a network:

      1. If the prompt asks for JSON, it returns parseable JSON.
      2. If the prompt contains a `CONTEXT:` block (our RAG convention), it
         answers using sentences pulled from that context, so grounding
         checks have something real to verify.
      3. Otherwise it echoes a stable, hashed response.
    """

    model: str = "fake-deterministic-1"
    scripted: dict[str, str] = field(default_factory=dict)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        for needle, canned in self.scripted.items():
            if needle in prompt:
                return self._wrap(canned, prompt)

        if re.search(r"\bJSON\b", prompt) or "json" in (system or "").lower():
            # If the prompt declares required keys (our playbook convention:
            # "keys: a, b, c"), echo them so an offline run produces a
            # schema-valid object. Deterministic, no cleverness.
            keys = self._declared_keys(prompt)
            if keys:
                payload = {k: f"offline value for {k}" for k in keys}
            else:
                payload = {
                    "summary": self._first_context_sentence(prompt) or "no context provided",
                    "confidence": 0.5,
                }
            return self._wrap(json.dumps(payload), prompt)

        grounded = self._first_context_sentence(prompt)
        if grounded:
            return self._wrap(grounded, prompt)

        digest = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        return self._wrap(f"[fake:{digest}] {prompt[:80].strip()}", prompt)

    @staticmethod
    def _declared_keys(prompt: str) -> list[str]:
        m = re.search(r"keys?:\s*([a-zA-Z0-9_,\s]+)", prompt)
        if not m:
            return []
        raw = m.group(1)
        # stop at a line break so we don't swallow later prose
        raw = raw.splitlines()[0]
        return [k.strip() for k in raw.split(",") if k.strip()]

    @staticmethod
    def _first_context_sentence(prompt: str) -> str | None:
        m = re.search(r"CONTEXT:\s*(.+?)(?:\n\n|QUESTION:|$)", prompt, re.S)
        if not m:
            return None
        block = m.group(1).strip()
        parts = re.split(r"(?<=[.!?])\s+", block)
        return parts[0].strip() if parts else None

    def _wrap(self, text: str, prompt: str) -> LLMResponse:
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=max(1, len(prompt) // 4),
            output_tokens=max(1, len(text) // 4),
        )


def default_client() -> LLMClient:
    """Return a real client if a key exists, else the offline fake."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicClient()
    return FakeClient()
