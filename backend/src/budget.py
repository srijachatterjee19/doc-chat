import os
import threading
from datetime import date

_lock = threading.Lock()
_state: dict = {"date": date.today(), "tokens": 0}

DAILY_LIMIT: int = int(os.getenv("DAILY_TOKEN_LIMIT", "100000"))


def _reset_if_new_day() -> None:
    today = date.today()
    if _state["date"] != today:
        _state["date"] = today
        _state["tokens"] = 0


def is_over_limit() -> bool:
    with _lock:
        _reset_if_new_day()
        return _state["tokens"] >= DAILY_LIMIT


def add_tokens(n: int) -> None:
    with _lock:
        _reset_if_new_day()
        _state["tokens"] += n


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
