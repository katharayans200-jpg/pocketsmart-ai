"""Application settings, read from environment variables / the local .env file."""
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

log = logging.getLogger("pocketsmart")


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int((value or "").strip())
    except ValueError:
        return default


def _float(value: str | None, default: float) -> float:
    try:
        return float((value or "").strip())
    except ValueError:
        return default


def _secret_key() -> str:
    key = os.getenv("SECRET_KEY", "").strip()
    if not key:
        log.warning("SECRET_KEY is empty - using a temporary key. Logins reset on every restart. "
                    "Set SECRET_KEY in your .env file.")
        key = secrets.token_hex(32)
    return key


@dataclass
class Settings:
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "").strip())
    gemini_timeout_seconds: float = field(default_factory=lambda: _float(os.getenv("GEMINI_TIMEOUT_SECONDS"), 60.0))
    gemini_retries: int = 1
    gemini_retry_delay: float = 1.5
    demo_mode: bool = field(default_factory=lambda: _flag(os.getenv("DEMO_MODE")))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "").strip() or "sqlite:///./pocketsmart.db")
    secret_key: str = field(default_factory=_secret_key)
    max_upload_mb: int = field(default_factory=lambda: _int(os.getenv("MAX_UPLOAD_MB"), 5))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int(os.getenv("PORT"), 8000))
    reload: bool = field(default_factory=lambda: _flag(os.getenv("RELOAD", "true")))
    cookie_secure: bool = field(default_factory=lambda: _flag(os.getenv("COOKIE_SECURE")))
    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if o.strip()
    ])
    templates_dir: Path = BASE_DIR / "app" / "templates"
    static_dir: Path = BASE_DIR / "static"
    upload_dir: Path = BASE_DIR / "uploads"

    @property
    def gemini_ready(self) -> bool:
        """True only when a key AND a model are configured and demo mode is off."""
        return bool(self.gemini_api_key and self.gemini_model and not self.demo_mode)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
