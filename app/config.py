from pathlib import Path
import tempfile
import traceback
import json
import sys
import os


def get_int_env(key: str, default: str, min_val: int = 1, max_val: int = 65535) -> int:
    try:
        value = int(os.environ.get(key, default))
        return max(min_val, min(value, max_val))
    except (ValueError, TypeError):
        return int(default)


def get_required_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        traceback.print_exc()
        print(f"\n\nPlease set the {key} environment variable correctly")
        sys.exit(1)
    return value


port = get_int_env("PORT", "8080")
if not 1 <= port <= 65535:
    print("PORT must be between 1 and 65535")
    sys.exit(1)

try:
    api_id = int(get_required_env("API_ID"))
    api_hash = get_required_env("API_HASH")
except (KeyError, ValueError):
    print("\n\nPlease set the API_ID and API_HASH environment variables correctly")
    print("You can get your own API keys at https://my.telegram.org/apps")
    sys.exit(1)

try:
    index_settings_str = os.environ.get("INDEX_SETTINGS", "").strip()
    index_settings = json.loads(index_settings_str) if index_settings_str else {}
except json.JSONDecodeError:
    traceback.print_exc()
    print("\n\nPlease set the INDEX_SETTINGS environment variable correctly")
    sys.exit(1)

REQUIRED_INDEX_KEYS = {
    "index_all",
    "index_private",
    "index_group",
    "index_channel",
    "exclude_chats",
    "include_chats",
}
for key in REQUIRED_INDEX_KEYS:
    if key not in index_settings:
        index_settings[key] = False if "index" in key else []

if index_settings_str and not index_settings:
    traceback.print_exc()
    print("\n\nPlease set the INDEX_SETTINGS environment variable correctly")
    sys.exit(1)

session_string = get_required_env("SESSION_STRING")

host = os.environ.get("HOST", "0.0.0.0")
debug = bool(os.environ.get("DEBUG"))
block_downloads = bool(os.environ.get("BLOCK_DOWNLOADS"))
results_per_page = get_int_env("RESULTS_PERPAGE", "20", 1, 500)

logo_folder = Path(os.path.join(tempfile.gettempdir(), "logo"))
logo_folder.mkdir(parents=True, exist_ok=True)

username = os.environ.get("TGINDEX_USERNAME", "")
password = os.environ.get("PASSWORD", "")

SHORT_URL_LEN = max(3, get_int_env("SHORT_URL_LEN", "3", 3, 32))

authenticated = bool(username and password)

try:
    SESSION_COOKIE_LIFETIME = get_int_env("SESSION_COOKIE_LIFETIME", "60", 1)
except ValueError:
    SESSION_COOKIE_LIFETIME = 60

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if authenticated:
    if not SECRET_KEY or len(SECRET_KEY) != 32:
        print(
            "\n\nSECRET_KEY must be exactly 32 characters when authentication is enabled"
        )
        sys.exit(1)
