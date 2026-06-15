"""Application settings.

All secrets come from environment variables (optionally via a local ``.env``
file). Fields without defaults are *required*: instantiating ``Settings``
fails at startup if they are missing, so a misconfigured deployment dies
loudly instead of serving requests with a blank JWT secret.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/core/config.py -> backend/ -> repo root (where the .pkl/.pt live)
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AQUASIGNAL_",
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
    )

    # --- database ---
    database_url: str = (
        "postgresql+asyncpg://aquasignal:aquasignal@localhost:5432/aquasignal"
    )

    @field_validator("database_url")
    @classmethod
    def _force_asyncpg_driver(cls, value: str) -> str:
        # Hosted providers (Supabase, Render dashboards) hand out plain
        # postgresql:// strings; the backend always speaks asyncpg, so
        # normalise here instead of making every deployer remember the
        # +asyncpg suffix.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    # --- auth (no defaults: fail fast if absent) ---
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # --- service-to-service auth (monthly cron -> POST /alerts/trigger) ---
    internal_api_token: str

    # --- integrations ---
    firebase_credentials_file: Path = _BACKEND_DIR / "secrets" / "firebase-service-account.json"
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- AI advisor (OpenRouter) ---
    # An empty key disables the advisor: /advisor/config reports enabled=false
    # and the UI hides the section, mirroring how optional push (Firebase) is
    # treated -- degrade quietly, never hard-fail at startup.
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    @field_validator("openrouter_base_url")
    @classmethod
    def _pin_openrouter_host(cls, value: str) -> str:
        # Defense-in-depth: the outbound request carries the API key in an
        # Authorization header. This is a server-side setting (not user input),
        # but pinning the destination to OpenRouter means a future misconfig --
        # or a "bring your own provider" feature -- cannot silently ship the key
        # to an arbitrary host.
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname != "openrouter.ai":
            raise ValueError("openrouter_base_url must be an https URL on openrouter.ai")
        return value
    # OpenRouter attributes traffic via these headers (shown on their dashboard
    # and used for free-tier ranking); harmless if the values are placeholders.
    openrouter_referer: str = "https://aquasignal.vercel.app"
    openrouter_title: str = "AquaSignal"

    # --- ML artifacts, reported by /health ---
    downscaler_path: Path = _REPO_ROOT / "downscaler.pkl"
    forecaster_path: Path = _REPO_ROOT / "forecaster.pt"

    # --- pipeline output: monthly satellite feature parquets ---
    processed_data_dir: Path = _REPO_ROOT / "data" / "processed"


@lru_cache
def get_settings() -> Settings:
    """Singleton accessor so every module shares one validated instance."""
    return Settings()
