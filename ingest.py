#!/usr/bin/env python3
"""
Ingest documents into the ChromaDB vector store.

Usage:
    python ingest.py file.txt [file2.pdf ...]   # ingest one or more files
    python ingest.py --clear                    # wipe all stored chunks
    python ingest.py --clear file.txt           # wipe then re-ingest
    python ingest.py --chunk-size 400 --overlap 50 file.pdf   # custom chunking

Supported formats: .txt, .md, .pdf
Files already present in the store (matched by filename) are skipped.
"""
import argparse
import uuid
from pathlib import Path

from dotenv import load_dotenv

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
        # Step forward by (chunk_size - overlap) so the next chunk
        # re-uses the last `overlap` words, preserving cross-boundary context.
        i += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def read_file(path: Path) -> str:
    """Extract text from .txt, .md, or .pdf files."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8")


def ingest_file(
    filepath: str,
    vector_store: VectorStore,
    chunk_size: int = 200,
    overlap: int = 20,
) -> None:
    """Chunk a file and store the chunks in the vector store (embeddings handled internally)."""
    path = Path(filepath)

    existing_ids = vector_store.get_ids_for_source(path.name)
    if existing_ids:
        print(f"  Skipping {path.name} — already ingested ({len(existing_ids)} chunks)")
        return

    print(f"Ingesting: {path.name}")
    text = read_file(path)
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"source": path.name, "chunk": i} for i in range(len(chunks))]

    vector_store.add_texts(chunks, metadatas=metadatas, ids=ids)
    print(f"  Added {len(chunks)} chunks from {path.name}")


def main() -> None:
    """Parse CLI arguments and ingest each provided file into the vector store."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into the RAG vector store"
    )
    parser.add_argument("files", nargs="*", help="Files to ingest (.txt, .md, .pdf)")
    parser.add_argument("--clear", action="store_true", help="Clear all stored chunks before ingesting")
    parser.add_argument("--chunk-size", type=int, default=200, help="Words per chunk (default: 200)")
    parser.add_argument("--overlap", type=int, default=20, help="Overlapping words between chunks (default: 20)")
    args = parser.parse_args()

    vector_store = VectorStore()

    if args.clear:
        vector_store.delete_all()
        print("Cleared all chunks.")

    if args.files:
        for filepath in args.files:
            path = Path(filepath)
            if path.exists():
                ingest_file(filepath, vector_store,
                            chunk_size=args.chunk_size, overlap=args.overlap)
            else:
                print(f"File not found: {filepath}")

    print(f"\nVector store now contains {vector_store.count()} document chunks.")


if __name__ == "__main__":
    main()
