"""Governance helpers: PII redaction and prompt-safety screening."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "EMAIL": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "PHONE": re.compile(
        r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?"
        r"(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}(?!\d)"
    ),
    "CREDIT_CARD": re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)"),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"),
}

_INJECTION_SIGNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "override",
        re.compile(r"ignore (all )?(previous|prior|above) instructions", re.I),
    ),
    (
        "system_leak",
        re.compile(
            r"(print|reveal|show|repeat).{0,20}(system prompt|instructions)",
            re.I,
        ),
    ),
    ("role_break", re.compile(r"you are now (a|an|no longer)", re.I)),
    (
        "exfiltration",
        re.compile(r"(send|post|upload).{0,30}(api[_ ]?key|password|secret)", re.I),
    ),
]

_REDACTION_ORDER = ("CREDIT_CARD", "IBAN", "EMAIL", "PHONE")


@dataclass(frozen=True)
class RedactionReport:
    """Redacted text plus counts by sensitive-data type."""

    clean_text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def found_pii(self) -> bool:
        """Whether any configured PII pattern matched."""
        return any(count > 0 for count in self.counts.values())


def redact(
    text: str,
    custom: dict[str, re.Pattern[str]] | None = None,
) -> RedactionReport:
    """Replace configured PII patterns with typed placeholders."""
    patterns = dict(_PII_PATTERNS)
    if custom:
        patterns.update(custom)

    ordered_labels = [
        *[label for label in _REDACTION_ORDER if label in patterns],
        *[label for label in patterns if label not in _REDACTION_ORDER],
    ]
    clean_text = text
    counts: dict[str, int] = {}

    for label in ordered_labels:
        clean_text, matches = patterns[label].subn(f"[{label}]", clean_text)
        if matches:
            counts[label] = matches

    return RedactionReport(clean_text=clean_text, counts=counts)


@dataclass(frozen=True)
class SafetyReport:
    """Prompt-screening decision with matched safety flags."""

    allowed: bool
    flags: list[str] = field(default_factory=list)


def screen(prompt: str) -> SafetyReport:
    """Flag common prompt-injection and secret-exfiltration patterns."""
    flags = [name for name, pattern in _INJECTION_SIGNS if pattern.search(prompt)]
    return SafetyReport(allowed=not flags, flags=flags)
