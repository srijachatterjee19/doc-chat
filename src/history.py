import sqlite3


class ChatHistory:
    """SQLite-backed store for conversation messages, persisted across server restarts."""

    def __init__(self, db_path: str = "./chat_history.db"):
        # check_same_thread=False is safe here — writes are serialised through the chatbot
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def load(self) -> list[dict]:
        """Return all messages ordered by insertion time."""
        rows = self.conn.execute(
            "SELECT role, content FROM messages ORDER BY id"
        ).fetchall()
        return [{"role": role, "content": content} for role, content in rows]

    def append(self, role: str, content: str) -> None:
        """Persist a single message."""
        self.conn.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
        )
        self.conn.commit()

    def rollback_last(self) -> None:
        """Delete the most recently inserted message."""
        self.conn.execute("DELETE FROM messages WHERE id = (SELECT MAX(id) FROM messages)")
        self.conn.commit()

    def clear(self) -> None:
        """Delete all messages."""
        self.conn.execute("DELETE FROM messages")
        self.conn.commit()
