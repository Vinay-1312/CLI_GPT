from types import SimpleNamespace

import pytest

from cli_copilot import chat, storage

USAGE = SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5)


def make_chunk(content=None, usage=None, choices=True):
    delta = SimpleNamespace(content=content)
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=delta)] if choices else [],
        x_groq=SimpleNamespace(usage=usage) if usage else None,
    )


class FakeClient:
    """Minimal stand-in for groq.Groq with a streaming chat.completions.create."""

    def __init__(self, chunks=None, error=None, factory=None):
        self.calls = []

        def create(**kwargs):
            self.calls.append(kwargs)
            if error:
                raise error
            return factory() if factory else iter(chunks or [])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


# ---- stream_reply -------------------------------------------------------

def test_stream_reply_concatenates_chunks_and_returns_usage():
    client = FakeClient([
        make_chunk("Hel"),
        make_chunk("lo"),
        make_chunk(None, usage=USAGE, choices=False),
    ])
    reply, usage = chat.stream_reply(client, "m", [{"role": "user", "content": "x"}])
    assert reply == "Hello"
    assert usage is USAGE
    assert client.calls[0]["stream"] is True


def test_stream_reply_empty_stream_raises():
    with pytest.raises(RuntimeError):
        chat.stream_reply(FakeClient([]), "m", [])


def test_stream_reply_keyboard_interrupt_carries_partial():
    def gen():
        yield make_chunk("par")
        yield make_chunk("tial")
        raise KeyboardInterrupt

    with pytest.raises(chat.StreamInterrupted) as exc:
        chat.stream_reply(FakeClient(factory=gen), "m", [])
    assert exc.value.partial == "partial"


# ---- start_session ------------------------------------------------------

def test_start_session_creates_new_with_system_prompt():
    sid, messages, _, banner = chat.start_session("/p", "m", "SYS", False, False)
    assert messages == [{"role": "system", "content": "SYS"}]
    assert banner.startswith("New session")
    assert storage.load_turns(sid)[0]["content"] == "SYS"


def test_start_session_resumes_existing():
    sid1, *_ = chat.start_session("/p", "m", "SYS", False, False)
    storage.append_turn(sid1, {"role": "user", "content": "hi"})
    sid2, messages, _, banner = chat.start_session("/p", "m", "SYS", False, False)
    assert sid2 == sid1
    assert len(messages) == 2
    assert banner.startswith("Resumed")


def test_start_session_new_flag_forces_fresh_session():
    sid1, *_ = chat.start_session("/p", "m", "SYS", False, False)
    sid2, *_ = chat.start_session("/p", "m", "SYS", False, True)
    assert sid1 != sid2


def test_start_session_resume_keeps_stored_system_prompt():
    chat.start_session("/p", "m", "OLD", False, False)
    _, messages, system, _ = chat.start_session("/p", "m", "NEW", True, False)
    assert system == "OLD"
    assert messages[0]["content"] == "OLD"


# ---- run_turn -----------------------------------------------------------

def _fresh():
    sid, messages, *_ = chat.start_session("/p", "m", "SYS", False, True)
    return sid, messages


def test_run_turn_persists_exchange_with_tokens():
    sid, messages = _fresh()
    client = FakeClient([make_chunk("hi", usage=USAGE)])
    chat.run_turn(client, "m", sid, messages, "hello")
    assert [m["role"] for m in messages] == ["system", "user", "assistant"]
    last = storage.load_turns(sid)[-1]
    assert last["content"] == "hi"
    assert last["tokens"] == {"prompt": 3, "completion": 2, "total": 5}


def test_run_turn_error_logs_and_rolls_back_user_message():
    sid, messages = _fresh()
    chat.run_turn(FakeClient(error=ValueError("boom")), "m", sid, messages, "hello")
    assert [m["role"] for m in messages] == ["system"]
    last = storage.load_turns(sid)[-1]
    assert last["type"] == "error" and last["error"] == "boom"


def test_run_turn_interrupted_saves_partial(monkeypatch):
    sid, messages = _fresh()

    def interrupted(*a, **k):
        raise chat.StreamInterrupted("part")

    monkeypatch.setattr(chat, "stream_reply", interrupted)
    chat.run_turn(None, "m", sid, messages, "hello")
    last = storage.load_turns(sid)[-1]
    assert last["content"] == "part" and last["interrupted"] is True
    assert messages[-1] == {"role": "assistant", "content": "part"}


def test_run_turn_interrupted_without_partial_drops_user_message(monkeypatch):
    sid, messages = _fresh()

    def interrupted(*a, **k):
        raise chat.StreamInterrupted("")

    monkeypatch.setattr(chat, "stream_reply", interrupted)
    chat.run_turn(None, "m", sid, messages, "hello")
    assert [m["role"] for m in messages] == ["system"]
