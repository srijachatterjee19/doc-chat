import os

import psycopg2
import psycopg2.extras


class ChatHistory:
    """PostgreSQL-backed store for conversation messages, persisted across server restarts."""

    def __init__(self, connection_string: str | None = None):
        dsn = connection_string or os.environ["DATABASE_URL"]
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False
        self._create_table()

    def _create_table(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id         SERIAL PRIMARY KEY,
                    role       TEXT        NOT NULL,
                    content    TEXT        NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        self.conn.commit()

    def load(self) -> list[dict]:
        """Return all messages ordered by insertion time."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT role, content FROM chat_messages ORDER BY id")
            return [{"role": r["role"], "content": r["content"]} for r in cur.fetchall()]

    def append(self, role: str, content: str) -> None:
        """Persist a single message."""
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (role, content) VALUES (%s, %s)",
                (role, content),
            )
        self.conn.commit()

    def rollback_last(self) -> None:
        """Delete the most recently inserted message."""
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE id = (SELECT MAX(id) FROM chat_messages)"
            )
        self.conn.commit()

    def clear(self) -> None:
        """Delete all messages."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM chat_messages")
        self.conn.commit()
