import chromadb


class VectorStore:
    """Persistent ChromaDB collection for storing and querying document embeddings."""

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "documents",
    ):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        documents: list[str],
        embeddings: list[list[float]],
        ids: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Insert documents with their pre-computed embeddings into the collection."""
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas or [{}] * len(documents),
        )

    def query(self, query_embedding: list[float], n_results: int = 3) -> list[str]:
        """Return the top-n most similar document chunks for the given embedding."""
        try:
            count = self.collection.count()
            if count == 0:
                return []
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, count),
            )
            return results["documents"][0] if results["documents"] else []
        except Exception:
            return []

    def count(self) -> int:
        """Return the total number of stored document chunks."""
        return self.collection.count()
