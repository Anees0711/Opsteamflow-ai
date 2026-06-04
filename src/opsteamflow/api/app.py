"""FastAPI application for OpsTeamFlow AI."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from ..analytics import RunLog, RunRecord, aggregate
from ..context import ContextRegistry
from ..governance import redact, screen
from ..playbook import Playbook, PlaybookRunner
from ..rag import RAGPipeline

_PLAYBOOK_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


class RedactIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)


class IngestIn(BaseModel):
    source: str = Field(..., min_length=1, max_length=120)
    text: str = Field(..., min_length=1, max_length=200_000)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if not _PLAYBOOK_NAME.fullmatch(value):
            raise ValueError("source can only contain letters, numbers, '_' and '-'")
        return value


class AskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=4_000)
    k: int = Field(default=4, ge=1, le=10)


class PlaybookIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    inputs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _PLAYBOOK_NAME.fullmatch(value):
            raise ValueError("playbook name can only contain letters, numbers, '_' and '-'")
        return value


class Settings:
    """Runtime settings read once when the API is created."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPSTEAMFLOW_API_KEY")
        self.cors_origin = os.environ.get("OPSTEAMFLOW_CORS_ORIGIN", "http://localhost:3000")

def require_api_key(settings: Settings) -> Callable[[str | None], None]:
from collections.abc import Callable
    """Return a dependency that enforces an API key only when configured."""

    def dependency(x_api_key: str | None = Header(default=None)) -> None:
        if settings.api_key and x_api_key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing API key",
            )

    return dependency


def create_app(
    context_dir: str | Path = "examples/context_packs",
    playbook_dir: str | Path = "examples/playbooks",
    log_path: str | Path = "run_log.jsonl",
) -> FastAPI:
    """Create the FastAPI application."""
    settings = Settings()
    auth = require_api_key(settings)

    app = FastAPI(title="OpsTeamFlow AI API", version="0.4.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "x-api-key"],
    )

    context_path = Path(context_dir)
    registry = ContextRegistry(context_path) if context_path.exists() else None
    runner = PlaybookRunner(registry=registry)
    rag = RAGPipeline()
    runlog = RunLog(log_path)
    playbook_path = Path(playbook_dir)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/governance/redact", dependencies=[Depends(auth)])
    def do_redact(body: RedactIn) -> dict[str, Any]:
        report = redact(body.text)
        safety = screen(body.text)
        return {
            "clean_text": report.clean_text,
            "counts": report.counts,
            "safety_allowed": safety.allowed,
            "safety_flags": safety.flags,
        }

    @app.get("/context", dependencies=[Depends(auth)])
    def list_context() -> dict[str, Any]:
        if registry is None:
            return {"packs": []}
        return {"packs": [registry.get(name).to_dict() for name in registry.names()]}

    @app.post("/rag/ingest", dependencies=[Depends(auth)])
    def ingest(body: IngestIn) -> dict[str, int]:
        chunks_added = rag.store.ingest(body.source, body.text)
        return {"chunks_added": chunks_added, "total_chunks": len(rag.store)}

    @app.post("/rag/ask", dependencies=[Depends(auth)])
    def ask(body: AskIn) -> dict[str, Any]:
        if len(rag.store) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="no documents ingested yet",
            )
        grounded_answer = rag.answer(body.question, k=body.k)
        return {
            "answer": grounded_answer.answer,
            "citations": grounded_answer.citations,
            "retrieved": [
                {"id": hit.chunk.id, "score": round(hit.score, 3)}
                for hit in grounded_answer.retrieved
            ],
        }

    @app.post("/playbook/run", dependencies=[Depends(auth)])
    def run_playbook(body: PlaybookIn) -> dict[str, Any]:
        path = playbook_path / f"{body.name}.yaml"
        if not path.exists() or path.parent != playbook_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no playbook {body.name!r}",
            )

        playbook = Playbook.from_file(path)
        start = time.perf_counter()
        try:
            run = runner.run(playbook, body.inputs)
        except (KeyError, PermissionError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        runlog.append(
            RunRecord(
                workflow=playbook.name,
                actor="api",
                passed=run.passed,
                duration_seconds=round(time.perf_counter() - start, 3),
                pii_redactions=sum(run.redaction_counts.values()),
            )
        )

        return {
            "output": run.output,
            "passed": run.passed,
            "scores": {
                name: {"value": round(score.value, 3), "reason": score.reason}
                for name, score in run.scores.items()
            },
            "redaction_counts": run.redaction_counts,
            "safety_flags": run.safety_flags,
        }

    @app.get("/analytics/summary", dependencies=[Depends(auth)])
    def summary() -> dict[str, Any]:
        return aggregate(runlog.read())

    return app


app = create_app()
