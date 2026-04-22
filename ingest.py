#!/usr/bin/env python3
"""Ingest documents into the ChromaDB vector store."""
import argparse
import uuid
from pathlib import Path

from dotenv import load_dotenv

from src.embeddings import EmbeddingModel
from src.vector_store import VectorStore

load_dotenv()


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 20) -> list[str]:
    """Split text into overlapping word-count chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def ingest_file(
    filepath: str, embedding_model: EmbeddingModel, vector_store: VectorStore
) -> None:
    """Chunk a text file, embed the chunks, and store them in the vector store."""
    path = Path(filepath)
    print(f"Ingesting: {path.name}")

    text = path.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    embeddings = embedding_model.embed(chunks)

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"source": path.name, "chunk": i} for i in range(len(chunks))]

    vector_store.add_documents(chunks, embeddings, ids, metadatas)
    print(f"  Added {len(chunks)} chunks from {path.name}")


def main() -> None:
    """Parse CLI arguments and ingest each provided file into the vector store."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into the RAG vector store"
    )
    parser.add_argument("files", nargs="+", help="Text files to ingest")
    args = parser.parse_args()

    print("Loading embedding model...")
    embedding_model = EmbeddingModel()
    vector_store = VectorStore()

    for filepath in args.files:
        path = Path(filepath)
        if path.exists():
            ingest_file(filepath, embedding_model, vector_store)
        else:
            print(f"File not found: {filepath}")

    print(f"\nVector store now contains {vector_store.count()} document chunks.")


if __name__ == "__main__":
    main()
