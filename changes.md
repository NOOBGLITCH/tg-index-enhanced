# tg-index Changes Summary

## New Files
- `app/health.py` - Health metrics & monitoring
- `app/backpressure.py` - Request limits & locking
- `app/cache.py` - LRU/DiskCache implementations
- `app/security.py` - Rate limiting
- `app/telegram.py` - Telegram client with retry logic

## Core Improvements
- **Resilience**: Exponential backoff for FloodWait errors, circuit breaker, graceful shutdown
- **Performance**: Enhanced LRU cache, disk cache, back pressure controller (50 concurrent requests)
- **Security**: Rate limiting (100/60s per IP), session management
- **Monitoring**: Health endpoints, response time tracking, error monitoring

## JWPlayer Controls
- Custom buttons in control bar: replay_10, forward_10, download
- Download forces file save (Content-Disposition: attachment)
- Material Symbols icons

## UI Updates
- Search highlight color (#FBF719)
- Thumbnail optimizations
- Template improvements

## Config
- Expanded `config.py` options
- All views updated with caching & rate limiting