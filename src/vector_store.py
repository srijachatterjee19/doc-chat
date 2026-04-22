from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings


class VectorStore:
    """ChromaDB-backed vector store using LangChain's Chroma integration."""

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "documents",
        embedding_model: str = "nomic-embed-text",
    ):
        self._store = Chroma(
            persist_directory=persist_directory,
            collection_name=collection_name,
            embedding_function=OllamaEmbeddings(model=embedding_model),
            collection_metadata={"hnsw:space": "cosine"},
        )

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """Embed and insert texts into the collection."""
        self._store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    def similarity_search(self, query: str, k: int = 3) -> list[str]:
        """Return the top-k most similar document chunks for the query."""
        try:
            if self.count() == 0:
                return []
            docs = self._store.similarity_search(query, k=min(k, self.count()))
            return [doc.page_content for doc in docs]
        except Exception:
            return []

    def get_ids_for_source(self, source_name: str) -> list[str]:
        """Return all chunk IDs stored under a given source filename."""
        result = self._store._collection.get(where={"source": {"$eq": source_name}})
        return result["ids"]

    def delete_all(self) -> None:
        """Delete every chunk from the collection."""
        ids = self._store._collection.get()["ids"]
        if ids:
            self._store._collection.delete(ids=ids)

    def list_sources(self) -> list[dict]:
        """Return each ingested source file with its chunk count."""
        result = self._store._collection.get(include=["metadatas"])
        sources: dict[str, int] = {}
        for meta in result["metadatas"]:
            name = meta.get("source", "unknown")
            sources[name] = sources.get(name, 0) + 1
        return [{"name": name, "chunks": count} for name, count in sorted(sources.items())]

    def count(self) -> int:
        """Return the total number of stored chunks."""
        return self._store._collection.count()
