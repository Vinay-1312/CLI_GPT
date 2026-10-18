import json
from datetime import datetime, timedelta, timezone

from cli_copilot import storage


def _set_last_used(sid, dt):
    meta = storage.read_meta(sid)
    meta["last_used_at"] = dt.isoformat()
    storage.write_meta(sid, meta)


def test_create_session_writes_meta():
    sid = storage.create_session(cwd="/proj", model="m")
    meta = storage.read_meta(sid)
    assert meta["id"] == sid
    assert meta["cwd"] == "/proj"
    assert meta["model"] == "m"
    assert meta["ended"] is False


def test_meta_is_valid_json_on_disk():
    sid = storage.create_session("/p", "m", name="demo")
    assert json.loads(storage.meta_path(sid).read_text())["name"] == "demo"


def test_append_and_load_turns_roundtrip():
    sid = storage.create_session("/p", "m")
    storage.append_turn(sid, {"role": "user", "content": "héllo ✓"})
    storage.append_turn(sid, {"role": "assistant", "content": "hi"})
    turns = storage.load_turns(sid)
    assert [t["content"] for t in turns] == ["héllo ✓", "hi"]


def test_load_turns_missing_file_returns_empty():
    assert storage.load_turns("does-not-exist") == []


def test_load_turns_skips_blank_and_corrupt_lines():
    sid = storage.create_session("/p", "m")
    storage.append_turn(sid, {"role": "user", "content": "ok"})
    with storage.conversation_path(sid).open("a", encoding="utf-8") as f:
        f.write("\n")
        f.write('{"role": "assistant", "content": "trunc')  # crash mid-write
    assert len(storage.load_turns(sid)) == 1


def test_to_messages_filters_non_message_turns():
    turns = [
        {"role": "system", "content": "s", "ts": "x"},
        {"type": "error", "error": "boom"},
        {"role": "user", "content": "u"},
        {"role": "tool", "content": "ignored"},
    ]
    assert storage.to_messages(turns) == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]


def test_end_session_marks_ended():
    sid = storage.create_session("/p", "m")
    storage.end_session(sid)
    assert storage.read_meta(sid)["ended"] is True


def test_touch_session_updates_last_used():
    sid = storage.create_session("/p", "m")
    old = datetime.now(timezone.utc) - timedelta(hours=5)
    _set_last_used(sid, old)
    storage.touch_session(sid)
    new = datetime.fromisoformat(storage.read_meta(sid)["last_used_at"])
    assert new > old


def test_find_active_returns_none_when_no_dir():
    assert storage.find_active_session_for_cwd("/p", 3600) is None


def test_find_active_returns_none_when_window_disabled():
    storage.create_session("/p", "m")
    assert storage.find_active_session_for_cwd("/p", 0) is None


def test_find_active_matches_cwd():
    a = storage.create_session("/a", "m")
    storage.create_session("/b", "m")
    assert storage.find_active_session_for_cwd("/a", 3600) == a


def test_find_active_ignores_ended_sessions():
    sid = storage.create_session("/p", "m")
    storage.end_session(sid)
    assert storage.find_active_session_for_cwd("/p", 3600) is None


def test_find_active_ignores_expired_sessions():
    sid = storage.create_session("/p", "m")
    _set_last_used(sid, datetime.now(timezone.utc) - timedelta(hours=2))
    assert storage.find_active_session_for_cwd("/p", 3600) is None


def test_find_active_picks_most_recent():
    old = storage.create_session("/p", "m")
    new = storage.create_session("/p", "m")
    _set_last_used(old, datetime.now(timezone.utc) - timedelta(minutes=30))
    _set_last_used(new, datetime.now(timezone.utc) - timedelta(minutes=1))
    assert storage.find_active_session_for_cwd("/p", 3600) == new


def test_find_active_handles_naive_timestamp():
    sid = storage.create_session("/p", "m")
    meta = storage.read_meta(sid)
    meta["last_used_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    storage.write_meta(sid, meta)
    assert storage.find_active_session_for_cwd("/p", 3600) == sid


def test_find_active_skips_corrupt_meta():
    good = storage.create_session("/p", "m")
    bad = storage.SESSIONS_DIR / "bad"
    bad.mkdir()
    (bad / "meta.json").write_text("{not json")
    (storage.SESSIONS_DIR / "empty").mkdir()  # no meta.json at all
    assert storage.find_active_session_for_cwd("/p", 3600) == good
