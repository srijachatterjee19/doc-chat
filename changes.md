# Changelog

## 2026-05-20

### Per-session isolation (single-user architecture fix)
- Each browser generates a UUID stored in `localStorage` as `sessionId`
- Backend `_SessionStore` maps session IDs to dedicated `RAGChatbot` instances (LRU cap: 200)
- Each session gets its own `history/{session_id}.json` — users no longer share conversation history
- History survives browser closes and reopens via the same UUID

### Thread-safe `ChatHistory`
- Added a `threading.Lock` per `ChatHistory` instance
- `append()`, `rollback_last()`, and `clear()` are now atomic read-modify-write operations

### Rate limiter fixed behind Nginx
- Replaced `get_remote_address` with a custom `_real_ip()` key function
- Reads `X-Real-IP` header set by Nginx so each client IP gets its own rate limit bucket
- Previously all traffic appeared as `127.0.0.1`, sharing one bucket across all users

### Budget persistence across restarts
- Daily token count is written to `budget/budget.json` on every `add_tokens()` call
- Loaded from disk on startup — container restarts no longer reset the daily counter
- `budget_data` Docker volume keeps the file alive across deployments

### docker-compose fixes
- Removed broken `chat_history.db` bind mount (file was never named that)
- Added named volumes for `history/` and `budget/` directories

### Removed legacy Streamlit UI
- Deleted `backend/app.py`
