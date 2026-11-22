"""Environment-based configuration. Secrets never live in source control."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    env: str = "development"
    db_path: str = str(REPO_DIR / "data" / "lifeexe.db")
    session_ttl_hours: int = 24 * 14
    secure_cookies: bool = False
    frontend_dist: str | None = str(REPO_DIR / "frontend" / "dist")
    auth_rate_limit_per_minute: int = 10
    max_body_bytes: int = 64 * 1024
    log_level: str = "INFO"
    allowed_origins: tuple[str, ...] = ()

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("LIFEEXE_ENV", "development")
        defaults = cls()
        origins = os.getenv("LIFEEXE_ALLOWED_ORIGINS", "")
        return cls(
            env=env,
            db_path=os.getenv("LIFEEXE_DB_PATH", defaults.db_path),
            session_ttl_hours=int(os.getenv("LIFEEXE_SESSION_TTL_HOURS", defaults.session_ttl_hours)),
            # Secure cookies default ON in production; never silently off there.
            secure_cookies=_bool(os.getenv("LIFEEXE_SECURE_COOKIES"), env == "production"),
            frontend_dist=os.getenv("LIFEEXE_FRONTEND_DIST", defaults.frontend_dist) or None,
            auth_rate_limit_per_minute=int(
                os.getenv("LIFEEXE_AUTH_RATE_LIMIT", defaults.auth_rate_limit_per_minute)
            ),
            log_level=os.getenv("LIFEEXE_LOG_LEVEL", defaults.log_level),
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )
