-- Postgres mapping for the analytics run log (docs/schema.sql).
-- The library writes JSONL by default; this is the warehouse target when
-- volume grows. One row per run, plus a view for the aggregates the
-- dashboard shows.

CREATE TABLE IF NOT EXISTS workflow_run (
    id                       BIGSERIAL PRIMARY KEY,
    workflow                 TEXT        NOT NULL,
    actor                    TEXT        NOT NULL,
    passed                   BOOLEAN     NOT NULL,
    duration_seconds         NUMERIC(10,3) NOT NULL,
    input_tokens             INTEGER     NOT NULL DEFAULT 0,
    output_tokens            INTEGER     NOT NULL DEFAULT 0,
    pii_redactions           INTEGER     NOT NULL DEFAULT 0,
    manual_baseline_seconds  NUMERIC(10,3),               -- NULL when unset
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_run_workflow ON workflow_run (workflow);
CREATE INDEX IF NOT EXISTS idx_run_created  ON workflow_run (created_at);

-- time saved is a difference of two real numbers, never invented
CREATE OR REPLACE VIEW workflow_rollup AS
SELECT
    workflow,
    COUNT(*)                                             AS runs,
    SUM(CASE WHEN passed THEN 1 ELSE 0 END)              AS passed,
    ROUND(AVG(CASE WHEN passed THEN 1 ELSE 0 END), 3)    AS pass_rate,
    SUM(pii_redactions)                                  AS pii_redactions,
    SUM(input_tokens + output_tokens)                    AS total_tokens,
    SUM(manual_baseline_seconds - duration_seconds)
        FILTER (WHERE manual_baseline_seconds IS NOT NULL) AS time_saved_seconds
FROM workflow_run
GROUP BY workflow;
