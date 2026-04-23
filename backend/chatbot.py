#!/usr/bin/env python3
"""Interactive RAG chatbot CLI."""
from dotenv import load_dotenv

from .src.rag import RAGChatbot
from .src.vector_store import VectorStore

load_dotenv()


def main() -> None:
    """Run the interactive CLI chatbot loop."""
    vector_store = VectorStore()

    doc_count = vector_store.count()
    if doc_count == 0:
        print(
            "Warning: No documents in the vector store.\n"
            "Run: python ingest.py data/sample.txt"
        )
    else:
        print(f"Vector store ready with {doc_count} document chunks.")

    chatbot = RAGChatbot(vector_store)

    print("\nRAG Chatbot ready! Commands: 'quit' to exit, 'reset' to clear history.")
    print("-" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
        if user_input.lower() == "reset":
            chatbot.reset()
            print("Conversation history cleared.")
            continue

        print("\nAssistant: ", end="", flush=True)
        full_response = ""
        for chunk in chatbot.stream(user_input):
            full_response += chunk
            print(chunk, end="", flush=True)
        print()
        chatbot.commit(user_input, full_response)


if __name__ == "__main__":
    main()
