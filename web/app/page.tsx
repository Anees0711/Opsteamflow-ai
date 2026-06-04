"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_OPSTEAMFLOW_API_KEY;

type WorkflowRollup = {
  runs: number;
  passed: number;
  pass_rate: number;
  pii_redactions: number;
  input_tokens?: number;
  output_tokens?: number;
};

type Summary = {
  runs: number;
  actors?: string[];
  by_workflow?: Record<string, WorkflowRollup>;
  time_saved_seconds_total?: number | null;
};

type AskResponse = {
  answer: string;
  citations: string[];
  retrieved?: { id: string; score: number }[];
};

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("content-type", "application/json");
  if (API_KEY) {
    headers.set("x-api-key", API_KEY);
  }

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : response.statusText;
    throw new Error(detail || "API request failed");
  }

  return data as T;
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [question, setQuestion] = useState("what happens on every pull request");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    apiFetch<Summary>("/analytics/summary")
      .then(setSummary)
      .catch((err: Error) => setError(`API not reachable: ${err.message}`))
      .finally(() => setLoadingSummary(false));
  }, []);

  async function runAsk() {
    setError(null);
    setAsking(true);
    setAnswer(null);

    try {
      const result = await apiFetch<AskResponse>("/rag/ask", {
        method: "POST",
        body: JSON.stringify({ question }),
      });
      setAnswer(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ask failed";
      setError(`${message}. Ingest a document through the API before asking.`);
    } finally {
      setAsking(false);
    }
  }

  const workflows = Object.entries(summary?.by_workflow ?? {});

  return (
    <main style={styles.main}>
      <h1 style={styles.h1}>OpsTeamFlow AI</h1>
      <p style={styles.sub}>
        Operational view for reusable AI workflows, guardrails, evaluation, and adoption.
      </p>

      {error && <div style={styles.error}>{error}</div>}

      <section style={styles.card}>
        <h2 style={styles.h2}>Run analytics</h2>
        {loadingSummary ? (
          <p style={styles.note}>Loading analytics…</p>
        ) : summary ? (
          <div>
            <p style={styles.metric}>{summary.runs} total runs</p>
            {summary.time_saved_seconds_total != null && (
              <p style={styles.note}>
                {Math.round(summary.time_saved_seconds_total)}s saved against measured manual baselines
              </p>
            )}
            {workflows.length > 0 ? (
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Workflow</th>
                    <th style={styles.th}>Runs</th>
                    <th style={styles.th}>Pass rate</th>
                    <th style={styles.th}>PII redactions</th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.map(([name, workflow]) => (
                    <tr key={name}>
                      <td style={styles.td}>{name}</td>
                      <td style={styles.td}>{workflow.runs}</td>
                      <td style={styles.td}>{(workflow.pass_rate * 100).toFixed(0)}%</td>
                      <td style={styles.td}>{workflow.pii_redactions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={styles.note}>No workflow runs logged yet.</p>
            )}
          </div>
        ) : (
          <p style={styles.note}>No analytics available.</p>
        )}
      </section>

      <section style={styles.card}>
        <h2 style={styles.h2}>Ask the knowledge base</h2>
        <div style={styles.row}>
          <input
            aria-label="Knowledge base question"
            style={styles.input}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button style={styles.button} onClick={runAsk} disabled={asking}>
            {asking ? "asking…" : "ask"}
          </button>
        </div>
        {answer && (
          <div style={styles.answer}>
            <p>{answer.answer}</p>
            <p style={styles.note}>Citations: {answer.citations.join(", ") || "none"}</p>
            {answer.retrieved && answer.retrieved.length > 0 && (
              <p style={styles.note}>
                Retrieved: {answer.retrieved.map((hit) => `${hit.id} (${hit.score})`).join(", ")}
              </p>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  main: {
    maxWidth: 780,
    margin: "0 auto",
    padding: "48px 24px",
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont",
  },
  h1: { fontSize: 34, margin: 0, letterSpacing: -0.5 },
  sub: { color: "#6b7280", marginTop: 4, lineHeight: 1.5 },
  h2: { fontSize: 18, marginTop: 0 },
  card: {
    border: "1px solid #e5e7eb",
    borderRadius: 12,
    padding: 20,
    marginTop: 20,
  },
  metric: { fontSize: 28, fontWeight: 600, margin: "4px 0" },
  note: { color: "#6b7280", fontSize: 14, lineHeight: 1.5 },
  table: { width: "100%", borderCollapse: "collapse", marginTop: 12 },
  th: {
    textAlign: "left",
    fontSize: 12,
    color: "#6b7280",
    borderBottom: "1px solid #e5e7eb",
    padding: "6px 4px",
  },
  td: { fontSize: 14, padding: "6px 4px", borderBottom: "1px solid #f3f4f6" },
  row: { display: "flex", gap: 8 },
  input: { flex: 1, padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 8 },
  button: {
    padding: "8px 16px",
    border: "none",
    borderRadius: 8,
    background: "#111827",
    color: "#fff",
    cursor: "pointer",
  },
  answer: { marginTop: 12, padding: 12, background: "#f9fafb", borderRadius: 8 },
  error: {
    background: "#fef2f2",
    color: "#991b1b",
    padding: 10,
    borderRadius: 8,
    marginTop: 12,
    fontSize: 14,
  },
};
