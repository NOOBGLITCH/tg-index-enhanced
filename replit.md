# Telegram Index

A Python web application (aiohttp) that indexes Telegram channels/chats and serves their files for browser viewing and download.

## Architecture

- **Language**: Python 3.12
- **Framework**: aiohttp (async web framework)
- **Templating**: aiohttp-jinja2 (Jinja2 templates)
- **Telegram client**: Telethon
- **Session storage**: aiohttp_session with encrypted cookies

## Project Structure

- `app/` - Main application package
  - `__main__.py` - Entry point, sets up logging and starts Indexer
  - `main.py` - Core app class (Indexer), sets up aiohttp app and middleware
  - `config.py` - Configuration from environment variables
  - `routes.py` - URL routing setup
  - `telegram.py` - Telegram client wrapper
  - `views/` - Request handlers (home, download, login, logout, etc.)
  - `templates/` - Jinja2 HTML templates
  - `icons/` - Static icon files
- `repl-config/` - Replit-specific config and run scripts
  - `run-repl.py` - Entry point script (checks env vars, runs app or session generator)
  - `run-dev.py` - Dev entry point (loads .env first)
- `requirements.txt` - Python dependencies

## Required Environment Variables (Secrets)

| Variable | Description |
|---|---|
| `API_ID` | Telegram API ID from https://my.telegram.org/apps |
| `API_HASH` | Telegram API hash from https://my.telegram.org/apps |
| `INDEX_SETTINGS` | JSON config for which chats to index |
| `SESSION_STRING` | Telethon session string for authentication |

## Optional Environment Variables

| Variable | Description | Default |
|---|---|---|
| `PORT` | Server port | 5000 (set) |
| `HOST` | Server host | 0.0.0.0 |
| `DEBUG` | Enable debug logging | false |
| `BLOCK_DOWNLOADS` | Disable file downloads | false |
| `RESULTS_PER_PAGE` | Search results per page | 20 |
| `TGINDEX_USERNAME` | Web UI username (auth) | '' |
| `PASSWORD` | Web UI password (auth) | '' |
| `SECRET_KEY` | 32-char cookie signing key (auth) | '' |
| `SESSION_COOKIE_LIFETIME` | Session lifetime in minutes | 60 |

## Running

The workflow runs: `python repl-config/run-repl.py`

This script checks for required env vars, generates a SESSION_STRING if missing, then runs `python -m app`.

## Deployment

Configured as a VM deployment (always-running) since it maintains a persistent Telegram connection.
Run command: `python repl-config/run-repl.py`
