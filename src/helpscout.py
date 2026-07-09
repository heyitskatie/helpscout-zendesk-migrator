"""Minimal HelpScout Mailbox API v2 client."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from config import Settings

logger = logging.getLogger(__name__)

AUTH_URL = "https://api.helpscout.net/v2/oauth2/token"
API_BASE = "https://api.helpscout.net/v2"


class HelpScoutClient:
    """Handles OAuth authentication and conversation/thread retrieval."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self._authenticate()

    def _authenticate(self) -> None:
        response = requests.post(
            AUTH_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": self.settings.helpscout_client_id,
                "client_secret": self.settings.helpscout_client_secret,
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        access_token = response.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})
        logger.info("HelpScout access token refreshed.")

    def list_conversations(
        self,
        mailbox_id: str,
        start_date: str,
        end_date: str,
        status: str = "closed",
        start_page: int = 1,
    ) -> Iterator[dict[str, Any]]:
        """Yield conversations for a mailbox within a date range, paginated."""
        page = start_page
        retry_count = 0

        while True:
            url = (
                f"{API_BASE}/conversations"
                f"?mailbox={mailbox_id}&status={status}"
                f"&query=(createdAt:[{start_date} TO {end_date}])&page={page}"
            )
            response = self.session.get(url, timeout=self.settings.request_timeout_seconds)

            if response.status_code == 401:
                self._authenticate()
                continue

            if response.status_code == 502:
                retry_count += 1
                if retry_count > self.settings.max_retry_attempts:
                    logger.error("Exceeded retries on HelpScout 502s; stopping.")
                    return
                sleep_for = self.settings.backoff_base_seconds * (2**retry_count)
                logger.warning("HelpScout 502, retrying in %ss", sleep_for)
                time.sleep(sleep_for)
                continue

            response.raise_for_status()
            retry_count = 0
            payload = response.json()
            conversations = payload.get("_embedded", {}).get("conversations", [])
            yield from conversations

            next_link = payload.get("_links", {}).get("next", {}).get("href")
            if not next_link:
                return
            page = int(parse_qs(urlparse(next_link).query).get("page", [page])[0])

    def get_threads(self, conversation_id: int) -> list[dict[str, Any]]:
        """Return all threads (messages) for a given conversation."""
        url = f"{API_BASE}/conversations/{conversation_id}/threads?embed=threads"
        response = self.session.get(url, timeout=self.settings.request_timeout_seconds)
        if response.status_code == 401:
            self._authenticate()
            response = self.session.get(url, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        return response.json().get("_embedded", {}).get("threads", [])
