from functools import lru_cache
from openai import OpenAI

_client = OpenAI()
_MODEL = "text-embedding-3-small"


@lru_cache(maxsize=512)
def _embed_cached(text: str) -> tuple[float, ...]:
    response = _client.embeddings.create(model=_MODEL, input=text)
    return tuple(response.data[0].embedding)


class EmbeddingModel:
    """Wraps OpenAI's embedding API to produce vector representations of text."""

    def embed_single(self, text: str) -> list[float]:
        return list(_embed_cached(text))

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = _client.embeddings.create(model=_MODEL, input=texts)
        return [d.embedding for d in response.data]
