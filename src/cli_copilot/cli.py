import keyring
import typer
from click.core import ParameterSource

from .chat import console, run_chat
from .config import DEFAULT_MODEL, DEFAULT_SYSTEM, SERVICE, USER

app = typer.Typer()


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
    api_key = ""
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


@app.command()
def chat(
    ctx: typer.Context,
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    system: str = typer.Option(DEFAULT_SYSTEM, "--system"),
    new: bool = typer.Option(False, "--new"),
):
    """Start an interactive chat with Groq."""
    api_key = keyring.get_password(SERVICE, USER)
    if not api_key:
        console.print("[red]No API key stored.[/] Run [cyan]`cli_copilot login`[/] first.")
        raise typer.Exit(1)

    system_passed = ctx.get_parameter_source("system") == ParameterSource.COMMANDLINE
    run_chat(api_key, model, system, system_passed, new)
