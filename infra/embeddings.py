from __future__ import annotations

from typing import Iterable

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


E5_MODEL_NAME = "intfloat/multilingual-e5-large-instruct"


class E5InstructEmbeddings(Embeddings):
    def __init__(self, model_name: str = E5_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def _format_query(self, text: str) -> str:
        normalized = (text or "").strip()
        return f"Instruct: Given a search query, retrieve relevant passages.\nQuery: {normalized}"

    def _format_passage(self, text: str) -> str:
        normalized = (text or "").strip()
        return f"passage: {normalized}"

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(
            self._format_query(text),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vector.tolist()

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        prepared = [self._format_passage(text) for text in texts]
        vectors = self._model.encode(
            prepared,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vectors.tolist()
