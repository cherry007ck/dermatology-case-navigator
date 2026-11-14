"""Runtime settings read from environment variables (see services/api/.env.example).

Secrets are read here only; they are never logged or returned by any route.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]

# Local development convenience only. Real environments set DEMO_ACCESS_CODE explicitly.
LOCAL_DEMO_ACCESS_CODE = "local-demo"


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    data_backend: str
    extractor_mode: str
    collection_mode: str
    cors_origins: list[str]
    demo_access_code: str = field(repr=False)
    session_token_secret: str = field(repr=False)
    voice_tool_secret: str = field(repr=False)
    fixture_root: Path
    exasol_dsn: str = ""
    exasol_user: str = ""
    # SaaS personal access token goes here: PyExasol 4.0.0 accepts it as password=.
    exasol_password: str = field(default="", repr=False)
    exasol_schema: str = "DERMA_NAV"
    # Meta Model API (OpenAI-compatible). The key is secret and server-only.
    model_api_key: str = field(default="", repr=False)
    model_base_url: str = ""
    model_name: str = ""

    @property
    def is_development(self) -> bool:
        return self.app_env in {"development", "test"}

    def effective_demo_access_code(self) -> str | None:
        """Configured code, or the documented local code in development/test only."""
        if self.demo_access_code:
            return self.demo_access_code
        return LOCAL_DEMO_ACCESS_CODE if self.is_development else None


@lru_cache
def get_settings() -> Settings:
    load_dotenv(API_ROOT / ".env", override=False)
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        data_backend=os.getenv("DATA_BACKEND", "memory"),
        extractor_mode=os.getenv("EXTRACTOR_MODE", "fixture"),
        collection_mode=os.getenv("COLLECTION_MODE", "synthetic"),
        cors_origins=_split(os.getenv("CORS_ORIGINS", "http://localhost:3000")),
        demo_access_code=os.getenv("DEMO_ACCESS_CODE", ""),
        session_token_secret=os.getenv("SESSION_TOKEN_SECRET", ""),
        voice_tool_secret=os.getenv("VOICE_TOOL_SECRET", ""),
        fixture_root=Path(os.getenv("FIXTURE_ROOT", str(REPO_ROOT))),
        exasol_dsn=os.getenv("EXASOL_DSN", ""),
        exasol_user=os.getenv("EXASOL_USER", ""),
        exasol_password=os.getenv("EXASOL_PASSWORD", ""),
        exasol_schema=os.getenv("EXASOL_SCHEMA", "DERMA_NAV") or "DERMA_NAV",
        model_api_key=os.getenv("MODEL_API_KEY", ""),
        model_base_url=os.getenv("MODEL_BASE_URL", ""),
        model_name=os.getenv("MODEL_NAME", ""),
    )
