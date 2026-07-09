"""Configuration management for the migration tool.

All credentials and tunable values are loaded from environment variables
(typically via a local .env file). Nothing sensitive should ever be
hardcoded in source.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the migration tool."""

    helpscout_client_id: str
    helpscout_client_secret: str
    zendesk_email: str
    zendesk_api_token: str
    zendesk_subdomain: str
    default_fallback_user_id: int = 0
    skip_emails: frozenset[str] = field(default_factory=frozenset)
    request_timeout_seconds: int = 10
    max_retry_attempts: int = 3
    backoff_base_seconds: int = 5

    @property
    def zendesk_base_url(self) -> str:
        return f"https://{self.zendesk_subdomain}.zendesk.com"

    @classmethod
    def from_env(cls) -> Settings:
        skip_emails_raw = os.environ.get("SKIP_EMAILS", "")
        skip_emails = frozenset(
            email.strip().lower() for email in skip_emails_raw.split(",") if email.strip()
        )
        return cls(
            helpscout_client_id=_require_env("HELPSCOUT_CLIENT_ID"),
            helpscout_client_secret=_require_env("HELPSCOUT_CLIENT_SECRET"),
            zendesk_email=_require_env("ZENDESK_EMAIL"),
            zendesk_api_token=_require_env("ZENDESK_API_TOKEN"),
            zendesk_subdomain=_require_env("ZENDESK_SUBDOMAIN"),
            default_fallback_user_id=int(os.environ.get("DEFAULT_FALLBACK_USER_ID", "0")),
            skip_emails=skip_emails,
        )


def _require_env(key: str) -> str:
    """Fetch a required environment variable or raise a clear error."""
    value = os.environ.get(key)
    if not value:
        raise OSError(
            f"Missing required environment variable: {key}. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return value
