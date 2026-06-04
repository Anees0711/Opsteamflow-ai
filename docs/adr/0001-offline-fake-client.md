# ADR 0001: An offline deterministic LLM client is a first-class citizen

## Status
Accepted.

## Context
A system that can only run with a paid API key is hard to test, hard to
onboard to, and impossible to gate in CI cheaply. AI projects routinely ship
with untested glue code because every test costs tokens and is nondeterministic.

## Decision
Define one `LLMClient` interface and ship two implementations: a real Anthropic
client and a deterministic `FakeClient`. The fake returns structurally valid
output (schema-valid JSON when keys are declared, context-grounded sentences
when a CONTEXT block is present). All tests and the demo use the fake by default.

## Consequences
- The full suite runs offline in well under a second.
- Contributors need no key.
- CI can gate on behaviour, not just imports.
- Risk: the fake can mask real-model failures. Mitigated by keeping the fake
  dumb and clearly documenting that it proves plumbing, not answer quality.
