# HTTP API

The API is optional. The Python package can be used directly without FastAPI.

## Run locally

```bash
pip install -e ".[api]"
uvicorn opsteamflow.api.app:app --reload
```

If `OPSTEAMFLOW_API_KEY` is set, protected endpoints require the header:

```bash
-H "x-api-key: $OPSTEAMFLOW_API_KEY"
```

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | - | status |
| POST | `/governance/redact` | `{ "text": "..." }` | redacted text, counts, safety |
| GET | `/context` | - | loaded context packs |
| POST | `/rag/ingest` | `{ "source": "handbook", "text": "..." }` | chunks added, total chunks |
| POST | `/rag/ask` | `{ "question": "...", "k": 4 }` | answer, citations, retrieved chunks |
| POST | `/playbook/run` | `{ "name": "release_note", "inputs": {...} }` | output, pass/fail, scores, safety |
| GET | `/analytics/summary` | - | aggregated run metrics |

## Examples

```bash
curl -s localhost:8000/governance/redact \
  -H 'content-type: application/json' \
  -d '{"text":"mail me at a@b.com"}'

curl -s localhost:8000/rag/ingest \
  -H 'content-type: application/json' \
  -d '{"source":"handbook","text":"Deployment uses GitHub Actions."}'

curl -s localhost:8000/rag/ask \
  -H 'content-type: application/json' \
  -d '{"question":"how is deployment done"}'

curl -s localhost:8000/playbook/run \
  -H 'content-type: application/json' \
  -d '{"name":"release_note","inputs":{"changes":"added SSO; fixed export"}}'
```

## Safety notes

This API is safe for local demos. Before exposing it publicly, enable API-key
auth, add rate limits, restrict CORS, and move analytics from JSONL to a managed
store.
