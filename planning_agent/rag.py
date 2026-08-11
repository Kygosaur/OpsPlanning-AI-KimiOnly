from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from docx import Document
from pypdf import PdfReader


TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{2,}")
SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf", ".docx", ".csv", ".xlsx", ".json", ".yaml", ".yml", ".py"}
EXCLUDED_NAMES = {".env", ".git", ".venv", "__pycache__", "node_modules", "secrets", "credentials"}


@dataclass(frozen=True)
class Passage:
    text: str
    document: str
    location: str
    score: float


@dataclass(frozen=True)
class _Chunk:
    text: str
    document: str
    location: str
    terms: Counter[str]


class WorkspaceIndex:
    """Read-only, lexical workspace search with no network or embedding service."""

    def __init__(self, root: str | Path, *, max_file_bytes: int = 5_000_000):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError(f"Workspace is not a directory: {self.root}")
        self.max_file_bytes = max_file_bytes
        self._chunks: list[_Chunk] = []
        self._postings: dict[str, list[tuple[int, float]]] = {}
        self._idf: dict[str, float] = {}
        self.skipped: list[str] = []

    def build(self) -> int:
        self._chunks.clear()
        self._postings.clear()
        self._idf.clear()
        self.skipped.clear()
        for path in self.root.rglob("*"):
            if not self._allowed(path):
                continue
            try:
                for text, location in _extract(path):
                    for chunk in _chunk_text(text):
                        terms = Counter(_tokens(chunk))
                        if terms:
                            relative = str(path.relative_to(self.root))
                            self._chunks.append(_Chunk(chunk, relative, location, terms))
            except Exception as error:
                self.skipped.append(f"{path.name}: {type(error).__name__}")
        self._prepare_search()
        return len(self._chunks)

    def search(self, question: str, top_k: int = 5, minimum_score: float = 0.05) -> list[Passage]:
        query = Counter(_tokens(question))
        if not query or not self._chunks:
            return []
        query_vector = {term: frequency * self._idf.get(term, 0.0) for term, frequency in query.items()}
        query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
        if not query_norm:
            return []
        scores: Counter[int] = Counter()
        for term, query_weight in query_vector.items():
            for chunk_index, normalized_weight in self._postings.get(term, []):
                scores[chunk_index] += (query_weight / query_norm) * normalized_weight
        scored: list[Passage] = []
        for chunk_index, score in scores.items():
            if score >= minimum_score:
                chunk = self._chunks[chunk_index]
                scored.append(Passage(chunk.text, chunk.document, chunk.location, score))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def _prepare_search(self) -> None:
        count = len(self._chunks)
        frequency = Counter(term for chunk in self._chunks for term in chunk.terms)
        self._idf = {term: math.log((count + 1) / (value + 1)) + 1 for term, value in frequency.items()}
        for index, chunk in enumerate(self._chunks):
            vector = {term: value * self._idf[term] for term, value in chunk.terms.items()}
            norm = math.sqrt(sum(value * value for value in vector.values()))
            if not norm:
                continue
            for term, value in vector.items():
                self._postings.setdefault(term, []).append((index, value / norm))

    def _allowed(self, path: Path) -> bool:
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return False
        if not resolved.is_relative_to(self.root) or path.is_symlink() or not path.is_file():
            return False
        relative_parts = {part.casefold() for part in path.relative_to(self.root).parts}
        if relative_parts & EXCLUDED_NAMES or path.name.casefold() in EXCLUDED_NAMES:
            return False
        if path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            return False
        if path.stat().st_size > self.max_file_bytes:
            self.skipped.append(f"{path.name}: file too large")
            return False
        return True


def _extract(path: Path) -> Iterable[tuple[str, str]]:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        for page_number, page in enumerate(PdfReader(path).pages, start=1):
            yield page.extract_text() or "", f"page {page_number}"
    elif suffix == ".docx":
        document = Document(path)
        yield "\n".join(p.text for p in document.paragraphs), "document"
    elif suffix == ".xlsx":
        book = pd.ExcelFile(path)
        for sheet in book.sheet_names:
            frame = pd.read_excel(book, sheet_name=sheet)
            yield frame.to_csv(index=False), f"sheet {sheet}"
    elif suffix == ".csv":
        yield pd.read_csv(path).to_csv(index=False), "table"
    elif suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        yield json.dumps(value, ensure_ascii=False, indent=2), "document"
    else:
        yield path.read_text(encoding="utf-8", errors="replace"), "document"


def _chunk_text(text: str, chunk_size: int = 1400, overlap: int = 200) -> Iterable[str]:
    text = text.strip()
    start = 0
    while start < len(text):
        yield text[start:start + chunk_size]
        start += chunk_size - overlap


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


