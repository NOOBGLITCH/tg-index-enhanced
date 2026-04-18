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

## UI Updates
- Search highlight color (#FBF719)
- Thumbnail optimizations
- Template improvements

## Config
- Expanded `config.py` options
- All views updated with caching & rate limiting