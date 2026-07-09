"""Typed data structures used throughout the migration pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MigrationStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Comment:
    """A single Zendesk ticket comment built from a HelpScout thread."""

    author_id: int
    value: str
    created_at: str
    public: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "author_id": self.author_id,
            "value": self.value,
            "created_at": self.created_at,
            "public": self.public,
        }


@dataclass
class ConversationRecord:
    """A HelpScout conversation, normalized for migration."""

    conversation_id: int
    number: int
    subject: str
    author_email: str
    created_at: str
    comments: list[Comment] = field(default_factory=list)


@dataclass
class MigrationResult:
    """Outcome of migrating a single conversation, used for the report CSV."""

    helpscout_conversation_id: int
    zendesk_ticket_id: int | None
    status: MigrationStatus
    detail: str = ""
