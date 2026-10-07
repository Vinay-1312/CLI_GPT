import typer
import keyring

app = typer.Typer()

SERVICE  = 'groq_key'
USER = 'default'

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