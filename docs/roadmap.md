# Roadmap

Ordered by practical value.

1. **Real embedder adapter**: add a hosted embedding adapter behind the current
   `HashingEmbedder` interface while keeping the offline default for tests.
2. **Labeled evaluation set**: create a small human-reviewed dataset for
   grounding and answer quality.
3. **Model-graded scorer**: add an optional scorer that returns the same `Score`
   object as the current lexical checks.
4. **Playbook versioning**: fingerprint playbooks so each run records the exact
   workflow version used.
5. **Postgres analytics backend**: move JSONL behind a repository interface and
   use `docs/schema.sql` as the first relational model.
6. **API hardening**: add rate limits, team-level budgets, stronger auth, and
   structured audit logs.
7. **Dashboard improvements**: add document ingestion, playbook execution, and
   run history views directly in the UI.
