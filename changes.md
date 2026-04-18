# tg-index Changes

## Features Added/Improved

### JWPlayer Video Player
- Custom control bar buttons (Rewind 10s, Forward 10s, Download)
- Material Symbols icons for player controls
- Download forces direct file save (attachment)
- Positioned custom buttons in control bar center

### UI/DaisyUI Redesign
- Complete DaisyUI template redesign
- Dark/Light theme toggle
- Enhanced thumbnail viewing
- Better file type icons
- Improved search highlight color (#FBF719)
- Mobile responsive layout

### Performance
- Enhanced LRU cache with TTL support
- Disk cache with mmap for fast I/O
- Back pressure controller (50 concurrent requests)
- Rate limiting (100 requests per 60s per IP)
- Circuit breaker for downstream failures
- Exponential backoff for Telegram FloodWait errors
- Graceful shutdown handling

### Monitoring
- Health metrics endpoint
- Response time tracking (rolling average)
- Status code distribution
- Request ID tracking for debugging

### Bug Fixes
- Fixed var to let scoping in JS
- Fixed chat_ids dictionary lookup
- Fixed _me attribute reference
- Fixed application runtime errors

---

## New Files
- health.py - Health metrics
- backpressure.py - Request limits
- cache.py - LRU/DiskCache
- security.py - Rate limiting
- telegram.py - Client with retry logic

## Modified
- main.py, config.py, views/, templates/, download.py