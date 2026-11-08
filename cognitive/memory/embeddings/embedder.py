"""Unified embedding client providing local deterministic hashing and cloud API backends."""

import hashlib
import math
import re
from typing import List, Optional
import numpy as np

from memory.core.interfaces import BaseEmbedder
from memory.core.exceptions import EmbeddingError
from memory.config import MemoryConfig, EmbeddingBackend


class LocalHashEmbedder(BaseEmbedder):
    """Deterministic, dependency-free local embedder using character n-grams and hashing.
    
    Generates normalized unit vectors of dimension `dim` (default 384).
    Enables 100% offline testing, zero cold-start, and fast semantic/keyword overlap matching.
    """

    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self._dim

        # Tokenize and extract character 3-grams and words
        clean_text = text.lower().strip()
        tokens = re.findall(r"\b\w+\b", clean_text)
        features: List[str] = list(tokens)

        # Add 3-grams for subword matching
        for word in tokens:
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    features.append(word[i : i + 3])

        if not features:
            features = [clean_text]

        vec = np.zeros(self._dim, dtype=np.float32)

        for feat in features:
            # MD5 hash into feature buckets with sign hash
            h = hashlib.md5(feat.encode("utf-8")).digest()
            bucket = int.from_bytes(h[:4], byteorder="big") % self._dim
            sign = 1.0 if (h[4] % 2 == 0) else -1.0
            vec[bucket] += sign

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return [float(x) for x in vec]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class OpenAIEmbedder(BaseEmbedder):
    """Remote OpenAI or OpenAI-compatible embedding client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dim: int = 1536,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._dim = dim
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            except Exception as e:
                raise EmbeddingError(f"Failed to initialize OpenAI client: {e}")
        return self._client

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        client = self._get_client()
        try:
            res = client.embeddings.create(input=[text], model=self._model)
            return res.data[0].embedding
        except Exception as e:
            raise EmbeddingError(f"OpenAI embedding failed: {e}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = self._get_client()
        try:
            res = client.embeddings.create(input=texts, model=self._model)
            return [d.embedding for d in res.data]
        except Exception as e:
            raise EmbeddingError(f"OpenAI batch embedding failed: {e}")


def get_embedder(config: Optional[MemoryConfig] = None) -> BaseEmbedder:
    """Factory helper to obtain the configured embedder instance."""
    if config is None:
        from memory.config import default_config
        config = default_config

    if config.embedding_backend == EmbeddingBackend.OPENAI and config.openai_api_key:
        return OpenAIEmbedder(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            dim=config.embedding_dim,
        )
    return LocalHashEmbedder(dim=config.embedding_dim)
