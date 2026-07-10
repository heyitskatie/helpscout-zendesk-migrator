"""Minimal Zendesk API client for user lookup/creation and ticket import."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from config import Settings
from models import Comment

logger = logging.getLogger(__name__)


class ZendeskClient:
    """Handles user resolution and bulk ticket import against Zendesk."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.auth = (f"{settings.zendesk_email}/token", settings.zendesk_api_token)
        self.session = requests.Session()

    def get_or_create_user(
        self,
        author_email: str,
        display_name: str | None = None,
    ) -> int:
        """Resolve a HelpScout author email to a Zendesk user ID.

        Skips known system addresses (returns the configured fallback ID),
        searches for an existing user, un-suspends them if needed, and
        creates a new end-user as a last resort.
        """
        normalized_email = author_email.lower()

        if normalized_email in self.settings.skip_emails:
            logger.info("Skipping user lookup for system address: %s", author_email)
            return self.settings.default_fallback_user_id

        existing_id = self._find_user(author_email)
        if existing_id is not None:
            return existing_id

        return self._create_user(author_email, display_name or author_email)

    def _find_user(self, author_email: str) -> int | None:
        url = f"{self.settings.zendesk_base_url}/api/v2/users/search.json"
        response = self.session.get(
            url,
            params={"query": author_email},
            auth=self.auth,
            timeout=self.settings.request_timeout_seconds,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            time.sleep(retry_after)
            return self._find_user(author_email)

        response.raise_for_status()
        users = response.json().get("users", [])
        if not users:
            return None

        user = users[0]
        if user.get("suspended"):
            self._unsuspend_user(user["id"])
        return user["id"]

    def _unsuspend_user(self, user_id: int) -> None:
        url = f"{self.settings.zendesk_base_url}/api/v2/users/{user_id}.json"
        self.session.put(
            url,
            json={"user": {"suspended": False}},
            auth=self.auth,
            timeout=self.settings.request_timeout_seconds,
        )

    def _create_user(self, email: str, name: str) -> int:
        url = f"{self.settings.zendesk_base_url}/api/v2/users.json"
        response = self.session.post(
            url,
            json={"user": {"email": email, "name": name, "role": "end-user"}},
            auth=self.auth,
            timeout=self.settings.request_timeout_seconds,
        )
        if response.status_code in (200, 201):
            return response.json()["user"]["id"]

        logger.error(
            "Failed to create Zendesk user for %s (status %s); using fallback ID.",
            email,
            response.status_code,
        )
        return self.settings.default_fallback_user_id

    def create_ticket(
        self,
        group_id: str,
        requester_id: int,
        subject: str,
        comments: list[Comment],
        tags: list[str],
        external_id: str,
    ) -> dict[str, Any]:
        """Submit a single ticket via the bulk ticket import endpoint."""
        url = f"{self.settings.zendesk_base_url}/api/v2/imports/tickets/create_many"
        payload: dict[str, Any] = {
            "tickets": [
                {
                    "group_id": group_id,
                    "requester_id": requester_id,
                    "comments": [comment.to_dict() for comment in comments],
                    "description": subject,
                    "priority": "normal",
                    "tags": tags,
                    "archive_immediately": True,
                    "status": "closed",
                    "external_id": external_id,
                }
            ]
        }
        response = self.session.post(
            url,
            json=payload,
            auth=self.auth,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
