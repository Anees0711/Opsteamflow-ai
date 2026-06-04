"""Versioned context packs and token-budget assembly."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _rough_tokens(text: str) -> int:
    """Estimate tokens without adding a tokenizer dependency."""
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class ContextPack:
    """Reference text that can be reused across workflows."""

    name: str
    kind: str
    body: str
    version: int = 1
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fingerprint(self) -> str:
        """Short content fingerprint used for run manifests."""
        digest = hashlib.sha256()
        digest.update(f"{self.name}|{self.kind}|{self.version}|".encode())
        digest.update(self.body.encode())
        return digest.hexdigest()[:12]

    @property
    def token_estimate(self) -> int:
        """Rough token estimate used by ContextAssembler."""
        return _rough_tokens(self.body)

    @classmethod
    def from_file(cls, path: str | Path) -> ContextPack:
        """Load a context pack from YAML."""
        raw = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError(f"context pack {path} must be a YAML object")
        if "name" not in data or "body" not in data:
            raise ValueError(f"context pack {path} needs 'name' and 'body'")
        return cls(
            name=str(data["name"]),
            kind=str(data.get("kind", "other")),
            body=str(data["body"]).strip(),
            version=int(data.get("version", 1)),
            tags=tuple(str(tag) for tag in data.get("tags", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a safe manifest representation."""
        return {
            "name": self.name,
            "kind": self.kind,
            "version": self.version,
            "tags": list(self.tags),
            "fingerprint": self.fingerprint,
            "token_estimate": self.token_estimate,
        }


class ContextBudgetError(RuntimeError):
    """Raised when selected context exceeds the explicit token budget."""


@dataclass(frozen=True)
class ContextAssembler:
    """Selects and concatenates packs under an explicit token budget."""

    token_budget: int = 4000

    def assemble(self, packs: list[ContextPack]) -> tuple[str, list[dict[str, Any]]]:
        """Return prompt-ready context plus a manifest of the packs used."""
        total = sum(pack.token_estimate for pack in packs)
        if total > self.token_budget:
            raise ContextBudgetError(
                f"context packs need ~{total} tokens, budget is "
                f"{self.token_budget}. Drop a pack or raise the budget explicitly."
            )

        blocks: list[str] = []
        manifest: list[dict[str, Any]] = []
        for pack in packs:
            blocks.append(f"### {pack.kind.upper()} CONTEXT: {pack.name}\n{pack.body}")
            manifest.append(pack.to_dict())
        return "\n\n".join(blocks), manifest


class ContextRegistry:
    """Loads every YAML context pack from a directory and serves them by name."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._packs: dict[str, ContextPack] = {}
        self.reload()

    def reload(self) -> None:
        """Reload all context packs from disk."""
        self._packs.clear()
        if not self.directory.exists():
            return
        for path in sorted(self.directory.glob("*.yaml")):
            pack = ContextPack.from_file(path)
            self._packs[pack.name] = pack

    def get(self, name: str) -> ContextPack:
        """Return one context pack by name."""
        if name not in self._packs:
            raise KeyError(f"no context pack named {name!r}")
        return self._packs[name]

    def names(self) -> list[str]:
        """Return all loaded context pack names."""
        return sorted(self._packs)
