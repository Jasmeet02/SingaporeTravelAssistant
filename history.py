from pathlib import Path
from datetime import datetime
import json

HISTORY_PATH = Path("conversation_history.json")
# Number of past exchanges to include in RAG queries (user+assistant pairs)
HISTORY_LIMIT = 6
# Maximum number of stored exchanges to keep on disk
HISTORY_STORE_LIMIT = 200

def load_history() -> list:
    if not HISTORY_PATH.exists():
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []

def save_history(history: list) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=2)

def append_history(user_message: str, assistant_message: str) -> None:
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user": user_message,
        "assistant": assistant_message,
    }
    history = load_history()
    history.append(entry)
    # Trim stored history to the most recent HISTORY_STORE_LIMIT exchanges
    if len(history) > HISTORY_STORE_LIMIT:
        history = history[-HISTORY_STORE_LIMIT:]
    save_history(history)
