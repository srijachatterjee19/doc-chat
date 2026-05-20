import json
import os
import threading
from datetime import date
from pathlib import Path

_lock = threading.Lock()
_PERSIST_PATH = Path(os.getenv("BUDGET_FILE", "budget/budget.json"))
DAILY_LIMIT: int = int(os.getenv("DAILY_TOKEN_LIMIT", "100000"))


def _load() -> dict:
    try:
        data = json.loads(_PERSIST_PATH.read_text())
        return {"date": date.fromisoformat(data["date"]), "tokens": int(data["tokens"])}
    except Exception:
        return {"date": date.today(), "tokens": 0}


def _save(state: dict) -> None:
    _PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PERSIST_PATH.write_text(json.dumps({"date": str(state["date"]), "tokens": state["tokens"]}))


_state: dict = _load()


def _reset_if_new_day() -> None:
    today = date.today()
    if _state["date"] != today:
        _state["date"] = today
        _state["tokens"] = 0
        _save(_state)


def is_over_limit() -> bool:
    with _lock:
        _reset_if_new_day()
        return _state["tokens"] >= DAILY_LIMIT


def add_tokens(n: int) -> None:
    with _lock:
        _reset_if_new_day()
        _state["tokens"] += n
        _save(_state)


def status() -> dict:
    with _lock:
        _reset_if_new_day()
        used = _state["tokens"]
        return {
            "tokens_used": used,
            "daily_limit": DAILY_LIMIT,
            "remaining": max(0, DAILY_LIMIT - used),
            "date": str(_state["date"]),
        }
