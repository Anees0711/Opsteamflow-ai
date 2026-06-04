"""Retrieval-augmented answering with citations."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

from ..llm import LLMClient, default_client


def chunk_text(text: str, target_chars: int = 500, overlap: int = 80) -> list[str]:
    """Split text into sentence-aware chunks with small character overlap."""
    if target_chars <= 0:
        raise ValueError("target_chars must be positive")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > target_chars:
            chunks.append(current.strip())
            current = f"{current[-overlap:]} {sentence}" if overlap else sentence
        else:
            current = f"{current} {sentence}".strip()

    if current.strip():
        chunks.append(current.strip())
    return chunks


class HashingEmbedder:
    """Deterministic offline embedder: hashed bag of words, L2-normalized."""

    def __init__(self, dims: int = 256) -> None:
        if dims <= 0:
            raise ValueError("dims must be positive")
        self.dims = dims

    def embed(self, text: str) -> list[float]:
        """Return a stable vector for text across Python processes."""
        vector = [0.0] * self.dims
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            index = int(digest, 16) % self.dims
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(x * y for x, y in zip(left, right))


@dataclass(frozen=True)
class Chunk:
    """One indexed document chunk."""

    id: str
    source: str
    text: str
    vector: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class Retrieved:
    """One retrieval hit."""

    chunk: Chunk
    score: float


class VectorStore:
    """In-memory cosine store behind a swappable interface."""

    def __init__(self, embedder: HashingEmbedder | None = None) -> None:
        self.embedder = embedder or HashingEmbedder()
        self._chunks: list[Chunk] = []

    def ingest(self, source: str, text: str) -> int:
        """Chunk, embed, and store text. Returns number of chunks added."""
        if not source.strip():
            raise ValueError("source cannot be empty")
        if not text.strip():
            return 0

        added = 0
        for index, body in enumerate(chunk_text(text)):
            chunk_id = f"{source}#{index}"
            self._chunks.append(
                Chunk(
                    id=chunk_id,
                    source=source,
                    text=body,
                    vector=self.embedder.embed(body),
                )
            )
            added += 1
        return added

    def retrieve(self, query: str, k: int = 4) -> list[Retrieved]:
        """Return the top-k chunks by cosine similarity."""
        if k <= 0:
            raise ValueError("k must be positive")
        if not self._chunks:
            return []

        query_vector = self.embedder.embed(query)
        scored = [
            Retrieved(chunk=chunk, score=_cosine(query_vector, chunk.vector))
            for chunk in self._chunks
        ]
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._chunks)


@dataclass(frozen=True)
class GroundedAnswer:
    """RAG answer with citations and retrieval metadata."""

    answer: str
    citations: list[str]
    retrieved: list[Retrieved]


class RAGPipeline:
    """Minimal RAG pipeline: retrieve context, ask model, extract citations."""

    def __init__(
        self,
        store: VectorStore | None = None,
        client: LLMClient | None = None,
    ) -> None:
        self.store = store or VectorStore()
        self.client = client or default_client()

    def answer(self, question: str, k: int = 4) -> GroundedAnswer:
        """Answer a question using retrieved chunks only."""
        hits = self.store.retrieve(question, k=k)
        context = "\n".join(f"[{hit.chunk.id}] {hit.chunk.text}" for hit in hits)
        prompt = (
            "Answer the question using only the context. "
            "Cite the bracketed chunk ids you used. If the answer is not in "
            "the context, say that the context is insufficient.\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {question}"
        )
        response = self.client.complete(prompt, max_tokens=512)
        citations = re.findall(r"\[([^\]]+#\d+)\]", response.text)
        return GroundedAnswer(
            answer=response.text,
            citations=list(dict.fromkeys(citations)),
            retrieved=hits,
        )
