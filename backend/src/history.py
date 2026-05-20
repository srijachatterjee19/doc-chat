import json
import threading
from pathlib import Path

_DEFAULT_PATH = Path("chat_history.json")


class ChatHistory:
    """JSON file-backed store for conversation messages."""

    def __init__(self, path: str | Path = _DEFAULT_PATH):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def load(self) -> list[dict]:
        if not self._path.exists():
            return []
        return json.loads(self._path.read_text())

    def append(self, role: str, content: str) -> None:
        with self._lock:
            messages = self.load()
            messages.append({"role": role, "content": content})
            self._path.write_text(json.dumps(messages, indent=2))

    def rollback_last(self) -> None:
        with self._lock:
            messages = self.load()
            if messages:
                messages.pop()
                self._path.write_text(json.dumps(messages, indent=2))

    def clear(self) -> None:
        with self._lock:
            self._path.write_text("[]")
