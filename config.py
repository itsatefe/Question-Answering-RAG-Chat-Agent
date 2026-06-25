import logging
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def _load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_postgres_uri(uri: str) -> str:
    if not uri:
        return ""
    parsed = urlsplit(uri)
    if parsed.scheme.lower() in {"postgres", "postgresql"}:
        return urlunsplit(parsed._replace(scheme="postgresql+asyncpg"))
    return uri


_load_env_file()

logging.getLogger("google.genai.types").setLevel(logging.ERROR)
logging.getLogger("google_genai.types").setLevel(logging.ERROR)

HF_TOKEN = _get("HF_TOKEN")
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN

PROJECT_ID = _get("PROJECT_ID")
LOCATION = _get("LOCATION", "us-central1")
USER_ID = _get("USER_ID", "user_123")
SESSION_SERVICE_URI = _normalize_postgres_uri(_get("SESSION_SERVICE_URI"))
SESSION_DB_ECHO = _get_bool("SESSION_DB_ECHO")

# Route Gemini calls through Vertex AI (uses ADC instead of an API key).
if PROJECT_ID:
    os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
