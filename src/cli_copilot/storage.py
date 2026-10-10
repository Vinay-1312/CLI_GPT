import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .config import SESSIONS_DIR


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_dir(session_id: str) -> Path:
    return SESSIONS_DIR / session_id


def conversation_path(session_id: str) -> Path:
    return session_dir(session_id) / "conversation.jsonl"


def meta_path(session_id: str) -> Path:
    return session_dir(session_id) / "meta.json"


def append_turn(session_id: str, turn: dict) -> None:
    path = conversation_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(turn, ensure_ascii=False) + "\n")


def write_meta(session_id: str, meta: dict) -> None:
    meta_path(session_id).parent.mkdir(parents=True, exist_ok=True)
    meta_path(session_id).write_text(json.dumps(meta, indent=2))


def read_meta(session_id: str) -> dict:
    return json.loads(meta_path(session_id).read_text())


def create_session(cwd: str, model: str, name: str | None = None) -> str:
    session_id = str(uuid4())
    write_meta(session_id, {
        "id": session_id,
        "name": name,
        "cwd": cwd,
        "model": model,
        "created_at": now_iso(),
        "last_used_at": now_iso(),
        "ended": False,
    })
    return session_id


def find_active_session_for_cwd(cwd: str, window_seconds: int) -> str | None:
    if window_seconds <= 0 or not SESSIONS_DIR.exists():
        return None
    best_id, best_ts = None, None
    for d in SESSIONS_DIR.iterdir():
        try:
            meta = json.loads((d / "meta.json").read_text())
            if meta.get("cwd") != cwd or meta.get("ended"):
                continue
            ts = datetime.fromisoformat(meta["last_used_at"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        if best_ts is None or ts > best_ts:
            best_id, best_ts = meta.get("id", d.name), ts
    if best_ts is None:
        return None
    age = (datetime.now(timezone.utc) - best_ts).total_seconds()
    return best_id if age < window_seconds else None


def touch_session(session_id: str) -> None:
    meta = read_meta(session_id)
    meta["last_used_at"] = now_iso()
    write_meta(session_id, meta)


def end_session(session_id: str) -> None:
    meta = read_meta(session_id)
    meta["ended"] = True
    write_meta(session_id, meta)


def load_turns(session_id: str) -> list[dict]:
    path = conversation_path(session_id)
    if not path.exists():
        return []
    turns = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # partial trailing line from a crash
    return turns


def to_messages(turns: list[dict]) -> list[dict]:
    return [
        {"role": t["role"], "content": t["content"]}
        for t in turns
        if t.get("role") in {"system", "user", "assistant"}
    ]
