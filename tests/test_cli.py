import keyring
import pytest
from typer.testing import CliRunner

from cli_copilot import cli
from cli_copilot.config import SERVICE, USER

runner = CliRunner()


@pytest.fixture
def fake_keyring(monkeypatch):
    store = {}
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: store.__setitem__((s, u), p))
    monkeypatch.setattr(keyring, "get_password", lambda s, u: store.get((s, u)))
    return store


@pytest.fixture
def captured_chat(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "run_chat", lambda *a: captured.setdefault("args", a))
    return captured


def test_hello():
    result = runner.invoke(cli.app, ["hello", "Ann"])
    assert result.exit_code == 0
    assert "Hello, Ann!" in result.output


def test_hello_shout():
    assert "HELLO, ANN!" in runner.invoke(cli.app, ["hello", "Ann", "--shout"]).output


def test_goodbye():
    assert "Goodbye, Bob!" in runner.invoke(cli.app, ["goodbye", "Bob"]).output


def test_login_stores_stripped_key(fake_keyring):
    result = runner.invoke(cli.app, ["login"], input="  secret1234  \n  secret1234  \n")
    assert result.exit_code == 0
    assert fake_keyring[(SERVICE, USER)] == "secret1234"
    assert "...1234" in result.output


def test_get_key_missing_exits_1(fake_keyring):
    assert runner.invoke(cli.app, ["get-key"]).exit_code == 1


def test_get_key_prints_stored_key(fake_keyring):
    fake_keyring[(SERVICE, USER)] = "abc"
    result = runner.invoke(cli.app, ["get-key"])
    assert result.exit_code == 0 and "abc" in result.output


def test_chat_without_key_exits_1(fake_keyring):
    assert runner.invoke(cli.app, ["chat"]).exit_code == 1


def test_chat_passes_options_to_run_chat(fake_keyring, captured_chat):
    fake_keyring[(SERVICE, USER)] = "k"
    result = runner.invoke(cli.app, ["chat", "--model", "x", "--system", "S", "--new"])
    assert result.exit_code == 0
    assert captured_chat["args"] == ("k", "x", "S", True, True)


def test_chat_defaults_system_not_passed(fake_keyring, captured_chat):
    fake_keyring[(SERVICE, USER)] = "k"
    runner.invoke(cli.app, ["chat"])
    assert captured_chat["args"][3] is False
