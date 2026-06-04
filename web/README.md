# OpsTeamFlow AI Web Dashboard

This dashboard gives a simple operational view of AI workflow runs, pass rates,
PII redactions, time-saved measurements, and knowledge-base answers from the
FastAPI backend.

It is intentionally small. The project is library-first, and the dashboard is a
thin UI for recruiters or teammates who want to see how the workflow system is
used without reading Python code first.

## Run locally

Start the API from the repository root:

```bash
pip install -e ".[api]"
uvicorn opsteamflow.api.app:app --reload
```

Start the dashboard:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_OPSTEAMFLOW_API_KEY=
```

The API key is optional for local development. If `OPSTEAMFLOW_API_KEY` is set
on the backend, mirror it with `NEXT_PUBLIC_OPSTEAMFLOW_API_KEY` for the demo UI.
