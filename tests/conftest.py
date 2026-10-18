import pytest

from cli_copilot import storage


@pytest.fixture(autouse=True)
def sessions_dir(tmp_path, monkeypatch):
    """Redirect all session storage to a temp dir so tests never touch real data."""
    d = tmp_path / "sessions"
    monkeypatch.setattr(storage, "SESSIONS_DIR", d)
    return d
