# cli-copilot

A terminal chat copilot powered by [Groq](https://groq.com). Replies stream live and render as Markdown, and conversations are saved so you can pick up where you left off.

## Features

- Streaming responses with Markdown rendering
- Sessions saved per working directory; chatting again within an hour resumes the last one
- API key stored securely in your system keyring
- Token usage shown after each reply
- Ctrl+C stops a reply and keeps the partial text

## Install

```bash
pipx install cli-copilot
# or
uv tool install cli-copilot
```

Requires Python 3.12+.

## Setup

Create an API key at [console.groq.com/keys](https://console.groq.com/keys), then store it:

```bash
cli-copilot login
```

## Usage

```bash
cli-copilot chat                      # start or resume a chat in this directory
cli-copilot chat --new                # force a fresh session
cli-copilot chat --model <model-id>   # choose a Groq model
cli-copilot chat --system "You are a code reviewer."
```

Inside a chat: `/new` starts a new session, `/exit` quits.

Other commands: `login`, `get-key`, `hello`, `goodbye`.

## Data

Sessions are stored as JSONL files in your user app directory (one folder per session, with `conversation.jsonl` and `meta.json`).

## Development

```bash
uv sync --group dev
uv run pytest
```
