"""Checkpoint persistence so an interrupted migration can be resumed."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CheckpointState:
    mailbox_id: str
    zendesk_group_id: str
    page: int = 1
    last_conversation_id: int | None = None
    last_zendesk_ticket_id: int | None = None


class Checkpoint:
    """Reads and writes migration progress to a JSON file on disk."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, default: CheckpointState) -> CheckpointState:
        if not self.path.exists():
            return default
        try:
            data = json.loads(self.path.read_text())
            return CheckpointState(**data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "Could not parse checkpoint file at %s (%s); starting fresh.",
                self.path,
                exc,
            )
            return default

    def save(self, state: CheckpointState) -> None:
        self.path.write_text(json.dumps(asdict(state), indent=2))

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
