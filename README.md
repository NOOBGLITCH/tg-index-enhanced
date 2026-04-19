# Telegram Index (Forked Version)

An enhanced fork of [tg-index](https://github.com/odysseusmax/tg-index) with major performance, UI, and feature improvements.

## What's New

- **JWPlayer Video Player**: Custom control bar buttons, Material Symbols icons, direct file save
- **UI Redesign**: DaisyUI, dark/light theme, mobile responsive
- **Performance**: LRU cache (TTL), disk cache (mmap), back pressure, rate limiting, circuit breaker, exponential backoff
- **Monitoring**: Health endpoint, response time tracking
- **Bug Fixes**: JS scoping, chat_ids lookup, _me attribute

---

A Python web application that indexes Telegram channels and chats, serving media files for browsing and download with a modern UI.

[![Open Source](https://badges.frapsoft.com/os/v1/open-source.png)](LICENSE) [![GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

## Features

| Category | Feature |
| -------- | -------- |
| **Indexing** | Index multiple Telegram channels/chats, view messages and media in browser |
| **Video Player** | JWPlayer with custom controls (Rewind 10s, Forward 10s, Download), Material Symbols icons |
| **Audio** | Integrated audio player support |
| **Search** | Full-text search through indexed content |
| **UI** | DaisyUI redesign, dark/light theme toggle, mobile responsive |
| **Downloads** | Direct file save via browser or download managers |
| **Auth** | Optional username/password authentication |

## Performance

- LRU cache with TTL support
- Disk cache with mmap for fast I/O
- Back pressure controller (50 concurrent requests)
- Rate limiting (100 requests/60s per IP)
- Circuit breaker for downstream failures
- Exponential backoff for Telegram FloodWait errors
- Graceful shutdown handling

## Monitoring

- Health metrics endpoint (`/health`)
- Response time tracking (rolling average)
- Status code distribution
- Request ID tracking for debugging

## Requirements

- Python 3.8+
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)

## Installation

```bash
git clone https://github.com/odysseusmax/tg-index.git
cd tg-index
python -m venv venv
source venv/bin/activate
pip3 install -U -r requirements.txt
```

## Configuration

| Variable | Required | Description |
| -------- | -------- | ---------- |
| `API_ID` | Yes | Telegram API ID |
| `API_HASH` | Yes | Telegram API hash |
| `SESSION_STRING` | Yes | From `python3 app/generate_session_string.py` |
| `INDEX_SETTINGS` | Yes | Indexing config (see below) |
| `PORT` | No | Server port (default: 8080) |
| `HOST` | No | Server host (default: 0.0.0.0) |
| `DEBUG` | No | Set `true` for debug logging |
| `RESULTS_PER_PAGE` | No | Results per page (default: 20) |
| `TGINDEX_USERNAME` | No | Auth username |
| `PASSWORD` | No | Auth password |
| `SECRET_KEY` | No* | 32-char key for signed sessions (*required if auth enabled) |
| `BLOCK_DOWNLOADS` | No | If set, disables downloads |
| `SHORT_URL_LEN` | No | URL alias length |
| `SESSION_COOKIE_LIFETIME` | No | Session validity in minutes (default: 60) |

### INDEX_SETTINGS

```json
{
  "index_all": true,
  "index_private": false,
  "index_group": false,
  "index_channel": true,
  "exclude_chats": [],
  "include_chats": []
}
```

- `index_all`: Index all chats or use specific settings
- `index_private`: Include private chats
- `index_group`: Include group chats  
- `index_channel`: Include channels
- `exclude_chats`: Chat IDs to skip (when `index_all: true`)
- `include_chats`: Specific chats to index (when `index_all: false`)

## Running

```bash
python3 -m app
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "-m", "app"]
```

### Repl.it

See [replit-deploy-guide.md](./repl-config/replit-deploy-guide.md) for detailed setup instructions.

## Troubleshooting

| Issue | Solution |
| ----- | -------- |
| FloodWait errors | Exponential backoff handles automatically; reduce request frequency |
| Slow playback | Enable disk cache in settings |
| Rate limited | Check `security.py` configuration |
| High memory | Adjust back pressure limits |

## What's New

Recent major enhancements:

- **JWPlayer Video Player**: Custom control bar buttons (Rewind 10s, Forward 10s, Download), Material Symbols icons, direct file save
- **UI Redesign**: Complete DaisyUI template, dark/light theme toggle, enhanced thumbnails, mobile responsive
- **Performance**: LRU cache with TTL, disk cache with mmap, back pressure (50 concurrent), rate limiting (100/min), circuit breaker, exponential backoff, graceful shutdown
- **Monitoring**: Health endpoint, response time tracking, status code distribution, request ID tracking
- **Bug Fixes**: JS scoping (var→let), chat_ids lookup, _me attribute, runtime errors

## License

Released under [GNU General Public License](LICENSE).