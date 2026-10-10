from pathlib import Path

from groq import Groq
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .config import AUTO_RESUME_WINDOW_SECONDS
from .storage import (
    append_turn,
    create_session,
    end_session,
    find_active_session_for_cwd,
    load_turns,
    now_iso,
    to_messages,
    touch_session,
)

console = Console()


class StreamInterrupted(Exception):
    """Raised when Ctrl+C stops a stream; carries the partial reply."""

    def __init__(self, partial: str):
        super().__init__("interrupted")
        self.partial = partial


def _chunk_usage(chunk):
    # Groq reports stream usage in x_groq.usage on the final chunk.
    x_groq = getattr(chunk, "x_groq", None)
    return (x_groq.usage if x_groq else None) or getattr(chunk, "usage", None)


def stream_reply(client: Groq, model: str, messages: list[dict]):
    """Stream one assistant reply. Returns (reply, usage)."""
    reply = ""
    try:
        with console.status("[dim]thinking...[/]", spinner="dots"):
            stream = client.chat.completions.create(
                model=model, messages=messages, stream=True,
            )
            try:
                first = next(stream)  # wait for first chunk
            except StopIteration:
                raise RuntimeError("Stream ended before any data was received.")
            if first.choices:
                reply = first.choices[0].delta.content or ""
        console.print()  # spacer
        usage = _chunk_usage(first)
        with Live(
            Panel("", title="[bold magenta]Assistant[/]", border_style="magenta"),
            console=console,
            refresh_per_second=20,
            vertical_overflow="visible",
        ) as live:
            for chunk in stream:
                usage = _chunk_usage(chunk) or usage
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    reply += delta
                    live.update(Panel(
                        Markdown(reply),
                        title="[bold magenta]Assistant[/]",
                        border_style="magenta",
                    ))
    except KeyboardInterrupt:
        raise StreamInterrupted(reply)
    return reply, usage


def start_session(cwd: str, model: str, system: str, system_passed: bool, new: bool):
    """Resume a recent session for cwd or create one.

    Returns (session_id, messages, system, banner).
    """
    session_id = None
    if not new:
        session_id = find_active_session_for_cwd(cwd, AUTO_RESUME_WINDOW_SECONDS)

    if session_id is None:
        session_id = create_session(cwd=cwd, model=model)
        append_turn(session_id, {"role": "system", "content": system, "ts": now_iso()})
        messages = [{"role": "system", "content": system}]
        return session_id, messages, system, f"New session {session_id[:8]}"

    turns = load_turns(session_id)
    messages = to_messages(turns)
    stored_system = next((t["content"] for t in turns if t.get("role") == "system"), None)
    if stored_system is not None:
        if system_passed and system != stored_system:
            console.print(
                "[dim]Note: --system ignored on resume; using stored system prompt. "
                "Pass --new to override.[/]"
            )
        system = stored_system
    return session_id, messages, system, f"Resumed {session_id[:8]} · {len(messages)} messages"


def run_turn(client: Groq, model: str, session_id: str, messages: list[dict], user_input: str) -> None:
    """Send one user message, persist the exchange, and update messages in place."""
    append_turn(session_id, {"role": "user", "content": user_input, "ts": now_iso()})
    messages.append({"role": "user", "content": user_input})

    try:
        reply, usage = stream_reply(client, model, messages)
        if usage:
            console.print(
                f"[dim]↳ {usage.prompt_tokens} in · {usage.completion_tokens} out · "
                f"{usage.total_tokens} total[/]"
            )
        assistant_turn = {
            "role": "assistant",
            "content": reply,
            "ts": now_iso(),
            "model": model,
        }
        if usage:
            assistant_turn["tokens"] = {
                "prompt": usage.prompt_tokens,
                "completion": usage.completion_tokens,
                "total": usage.total_tokens,
            }
        append_turn(session_id, assistant_turn)
        messages.append({"role": "assistant", "content": reply})

    except StreamInterrupted as e:
        console.print("\n[yellow][interrupted][/]")
        if e.partial:
            append_turn(session_id, {
                "role": "assistant",
                "content": e.partial,
                "ts": now_iso(),
                "model": model,
                "interrupted": True,
            })
            messages.append({"role": "assistant", "content": e.partial})
        else:
            messages.pop()
    except Exception as e:
        append_turn(session_id, {"type": "error", "error": str(e), "ts": now_iso()})
        messages.pop()
        console.print(f"\n[red]Error:[/] {e}")

    touch_session(session_id)


def run_chat(api_key: str, model: str, system: str, system_passed: bool, new: bool) -> None:
    client = Groq(api_key=api_key)
    cwd = str(Path.cwd())
    session_id, messages, system, banner = start_session(cwd, model, system, system_passed, new)

    console.print(Panel.fit(
        f"Chatting with [bold cyan]{model}[/] · {banner}\n"
        "Type [yellow]/exit[/] to quit, [yellow]/new[/] to start a new session.",
        title="Groq Copilot",
        border_style="cyan",
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"/exit", "/quit", "/bye"}:
            console.print("[dim]Goodbye.[/]")
            break
        if user_input.lower() == "/new":
            end_session(session_id)
            session_id = create_session(cwd=cwd, model=model)
            append_turn(session_id, {"role": "system", "content": system, "ts": now_iso()})
            messages = [{"role": "system", "content": system}]
            console.print(f"[yellow]Started new session {session_id[:8]}.[/]")
            continue

        run_turn(client, model, session_id, messages, user_input)
