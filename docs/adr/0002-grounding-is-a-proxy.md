# ADR 0002: Grounding score is a lexical proxy, stated as such

## Status
Accepted.

## Context
We want a cheap, deterministic signal for "is this answer supported by the
provided context" that can run on every request and in CI. A model-graded
entailment check is more accurate but costs a call, adds latency, and is itself
nondeterministic.

## Decision
Ship `grounding_score` as word-overlap per answer sentence against the context,
returning a fraction. Document its failure modes in code and README: it is
fooled by paraphrase (false low) and by fluent reuse of source words (false
high).

## Consequences
- Free, deterministic, good enough as a drift tripwire and CI gate.
- Not a truth oracle. A future model-graded scorer can implement the same
  `Score` return type and slot in without changing callers.
