import re
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from servicepilot.models import Principal


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


class HashEmbedder:
    """Offline lexical vectors, NOT pretrained semantic embeddings."""

    def __init__(self):
        self.vectorizer = HashingVectorizer(n_features=1024, alternate_sign=False, norm="l2")

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.vectorizer.transform(texts).toarray().astype("float32")


class SemanticEmbedder:
    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True).astype("float32")


class KnowledgeBase:
    def __init__(self, directory: Path, embedder: Embedder | None = None):
        self.root = directory.resolve()
        self.embedder = embedder or HashEmbedder()
        self.documents = []
        for path in sorted(self.root.glob("*.md")):
            # Reject symlinks escaping the allowed knowledge directory.
            if not path.resolve().is_relative_to(self.root):
                raise ValueError("Procedure path is outside the knowledge directory")
            lines = path.read_text(encoding="utf-8").splitlines()
            service_id = next(
                (line.split(":", 1)[1].strip() for line in lines if line.startswith("service:")), ""
            )
            title = next((line[2:] for line in lines if line.startswith("# ")), path.stem)
            self.documents.append(
                {
                    "id": path.stem,
                    "title": title,
                    "service_id": service_id,
                    "text": "\n".join(line for line in lines if not line.startswith("service:")),
                }
            )
        if not self.documents:
            raise ValueError("The knowledge directory must contain Markdown procedures")
        self.vectors = self.embedder.encode([d["text"] for d in self.documents])
        # Indexes are isolated by scope; unauthorized documents never enter a query's index.
        self.indexes: dict[tuple[str, ...], tuple[faiss.IndexFlatIP, list[dict]]] = {}

    def search(self, query: str, principal: Principal, k: int = 3) -> list[dict]:
        # A named service narrows relevance without ever widening authorization.
        mentioned = {
            s for s in ("atlas", "nova", "orion", "vpn") if re.search(rf"\b{s}\b", query.lower())
        }
        scope = principal.services.intersection(mentioned) if mentioned else principal.services
        key = tuple(sorted(scope))
        if key not in self.indexes:
            ids = [i for i, d in enumerate(self.documents) if d["service_id"] in scope]
            index = faiss.IndexFlatIP(self.vectors.shape[1])
            if ids:
                index.add(np.ascontiguousarray(self.vectors[ids]))
            self.indexes[key] = index, [self.documents[i] for i in ids]
        index, docs = self.indexes[key]
        if not docs:
            return []
        scores, positions = index.search(self.embedder.encode([query]), min(k, len(docs)))
        return [
            {"id": docs[p]["id"], "title": docs[p]["title"], "excerpt": docs[p]["text"][:1800]}
            for score, p in zip(scores[0], positions[0], strict=True)
            if p >= 0 and score > 0.04
        ]
