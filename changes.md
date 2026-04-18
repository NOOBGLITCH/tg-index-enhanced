# tg-index Changes Summary

## All Git Commits

### Latest (a54a321)
- docs: update changes.md with JWPlayer controls

### JWPlayer Enhancements
- **5c6de83** feat: enhance JWPlayer controls, download fix
  - Custom buttons: replay_10, forward_10, download
  - Download forces file save (attachment)
  - Material Symbols icons
  
- **a64ac71** fix: jwplayer custom buttons in control bar
  - Positioned buttons in control bar center
  - Added Share, PiP, Download

- **4590c2e** fix: jwplayer controls, var to let
  - Fixed var to let scoping
  - Fixed chat_ids lookup
  - Fixed _me attribute

- **f0d63e6** fix: use #FBF719 for search highlight

### Performance & UI
- **d4ef243** perf: massive performance & stability improvements
  - LRU cache + disk cache with TTL
  - Back pressure (50 concurrent)
  - Rate limiting (100/60s)
  - Circuit breaker
  - Exponential backoff
  - Health metrics

- **e1bd2d5** compltely redesigned daisy ui
  - Complete DaisyUI redesign
  - Thumbnail optimizations
  - Template improvements

- **4f8f33b** Fix application runtime errors
- **b1628ee** Saved progress at loop completion
- **afb9787** Add project setup
- **b253969** fix for older python versions

---

## New Files
- `app/health.py` - Health metrics
- `app/backpressure.py` - Request limits
- `app/cache.py` - LRU/DiskCache
- `app/security.py` - Rate limiting
- `app/telegram.py` - Telegram client

## Modified
- `app/main.py`, `app/config.py`, `app/views/`, `app/templates/`