from pathlib import Path

import typer

SERVICE = "groq_key"
USER = "default"
APP_DIR = Path(typer.get_app_dir("your-copilot"))
SESSIONS_DIR = APP_DIR / "sessions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_SYSTEM = "You are a helpful assistant."
AUTO_RESUME_WINDOW_SECONDS = 3600
