import typer
import keyring
import httpx
from groq import Groq, APIStatusError, APIError

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

console = Console()


app = typer.Typer()

SERVICE  = 'groq_key'
USER = 'default'
API_URL = "https://api.groq.com/openai/v1/chat/completions"

@app.command()
def hello(name: str, shout: bool = False):
    """Say hello."""
    msg = f"Hello, {name}!"
    typer.echo(msg.upper() if shout else msg)

@app.command()
def goodbye(name: str):
    """Say goodbye."""
    typer.echo(f"Goodbye, {name}!")

@app.command()
def login():
    """Prompt for an API key and save it."""
    api_key = '';
    while not (api_key or "").strip():
        api_key = typer.prompt(
            "Enter your API key",
            hide_input=True,
            confirmation_prompt=True,
        )

    api_key = api_key.strip()
    keyring.set_password(SERVICE, USER, api_key)
    typer.echo(f"Saved key ending in ...{api_key[-4:]}")

@app.command()
def get_key():
    """Returns stored API key."""
    key = keyring.get_password(SERVICE, USER)
    if key is None:
        typer.echo("No key stored.", err=True)
        raise typer.Exit(1)
    typer.echo(key)

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

console = Console()

@app.command()
def chat(
    model: str = typer.Option("openai/gpt-oss-120b", "--model"),
    system: str = typer.Option("You are a helpful assistant.", "--system"),
):
    """Start an interactive chat with Groq."""
    api_key = keyring.get_password(SERVICE, USER)
    if not api_key:
        console.print("[red]No API key stored.[/] Run [cyan]`cli_copilot login`[/] first.")
        raise typer.Exit(1)

    client = Groq(api_key=api_key)
    messages = [{"role": "system", "content": system}]

    console.print(Panel.fit(
        f"Chatting with [bold cyan]{model}[/]\n"
        "Type [yellow]/exit[/] to quit, [yellow]/clear[/] to reset history.",
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
        if user_input.lower() == "/clear":
            messages = [messages[0]]
            console.print("[yellow]History cleared.[/]")
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            with console.status("[dim]thinking...[/]", spinner="dots"):
                stream = client.chat.completions.create(
                    model=model, messages=messages, stream=True,
                )
                first = next(stream)  # wait for first chunk
                reply = first.choices[0].delta.content or ""
            console.print()  # spacer
            with Live(
                Panel("", title="[bold magenta]Assistant[/]", border_style="magenta"),
                console=console,
                refresh_per_second=20,
                vertical_overflow="visible",
            ) as live:
                usage = None;
                for chunk in stream:
                    if chunk.usage:
                        usage = chunk.usage
                    delta = chunk.choices[0].delta.content
                    if delta:
                        reply += delta
                        live.update(Panel(
                            Markdown(reply),
                            title="[bold magenta]Assistant[/]",
                            border_style="magenta",
                        ))
            if usage:
                console.print(
                    f"[dim]↳ {usage.prompt_tokens} in · {usage.completion_tokens} out · "
                    f"{usage.total_tokens} total[/]"
                )
            messages.append({"role": "assistant", "content": reply})

        except KeyboardInterrupt:
            console.print("\n[yellow][interrupted][/]")
            messages.pop()
        except Exception as e:
            console.print(f"\n[red]Error:[/] {e}")
            messages.pop()