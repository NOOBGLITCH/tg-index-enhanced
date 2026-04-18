# tg-index Changes Summary

## Tech Stack Improvements

### 1. Reliability & Resilience
- **Exponential Backoff Retry** - Telegram client now handles `FloodWaitError` with exponential backoff and jitter
- **Circuit Breaker** - Prevents cascade failures when downstream services are unavailable
- **Graceful Shutdown** - Proper cleanup of tasks and connections on shutdown

### 2. Performance & Caching
- **Enhanced LRU Cache** - TTL support, size limits, async-safe operations
- **DiskCache** - Persistent caching with mmap for fast I/O
- **Message Caching with Timeouts** - Configurable cache timeouts
- **Back Pressure Controller** - Limits concurrent requests (default 50)
- **Optimistic Locking** - Prevents race conditions on concurrent operations

### 3. Observability
- **Health Metrics** - Uptime, request count, error tracking, cache hit/miss rates
- **Response Time Tracking** - Rolling average of last 100 requests
- **Status Code Distribution** - Tracks HTTP status code counts
- **Memory Monitoring** - Uses `psutil` for system metrics (optional)

### 4. Security
- **Rate Limiting** - Configurable request limits per IP (default 100/60s)
- **Enhanced Auth** - Better session management
- **Request ID Tracking** - Unique IDs for debugging

### 5. UX Improvements
- **Search Highlight Color** - Custom highlight (#FBF719)
- **Thumbnail Optimizations** - Better thumbnail viewing
- **Template Enhancements** - Improved UI across all pages

### 6. Configuration
- **Better Config Management** - Refactored `config.py` with more options

## Files Added
- `app/health.py` - Health metrics and monitoring
- `app/backpressure.py` - Back pressure controller and optimistic locking
- `app/cache.py` - Enhanced LRU/DiskCache implementations
- `app/security.py` - Rate limiting and security utilities
- `app/telegram.py` - Enhanced Telegram client with retry logic

## Files Modified
- `app/main.py` - Added health endpoint, graceful shutdown
- `app/config.py` - Expanded configuration options
- `app/views/` - All views updated with caching, rate limiting
- `app/templates/` - UI improvements