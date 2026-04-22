import ollama


class EmbeddingModel:
    """Wraps an Ollama embedding model to produce vector representations of text."""

    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input string."""
        response = ollama.embed(model=self.model, input=texts)
        return response.embeddings

    def embed_single(self, text: str) -> list[float]:
        """Return a single embedding vector for one string."""
        response = ollama.embed(model=self.model, input=text)
        return response.embeddings[0]
