"""Orchestrates the end-to-end HelpScout -> Zendesk migration."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from checkpoint import Checkpoint, CheckpointState
from helpscout import HelpScoutClient
from models import Comment, MigrationResult, MigrationStatus
from utils import html_to_plain_text
from zendesk import ZendeskClient

logger = logging.getLogger(__name__)


class Migrator:
    """Coordinates pulling conversations from HelpScout and creating them in Zendesk."""

    def __init__(
        self,
        helpscout: HelpScoutClient,
        zendesk: ZendeskClient,
        checkpoint: Checkpoint,
        results_csv_path: Path,
    ) -> None:
        self.helpscout = helpscout
        self.zendesk = zendesk
        self.checkpoint = checkpoint
        self.results_csv_path = results_csv_path

    def run(
        self,
        mailbox_id: str,
        zendesk_group_id: str,
        start_date: str,
        end_date: str,
    ) -> list[MigrationResult]:
        state = self.checkpoint.load(
            CheckpointState(mailbox_id=mailbox_id, zendesk_group_id=zendesk_group_id)
        )
        results: list[MigrationResult] = []

        conversations = self.helpscout.list_conversations(
            mailbox_id=mailbox_id,
            start_date=start_date,
            end_date=end_date,
            start_page=state.page,
        )

        for conversation in conversations:
            result = self._migrate_one(conversation, zendesk_group_id)
            results.append(result)

            state.last_conversation_id = conversation["id"]
            if result.zendesk_ticket_id is not None:
                state.last_zendesk_ticket_id = result.zendesk_ticket_id
            self.checkpoint.save(state)
            self._append_result_row(result)

        return results

    def _migrate_one(self, conversation: dict, zendesk_group_id: str) -> MigrationResult:
        conversation_id = conversation["id"]
        try:
            helpscout_number = conversation["number"]
            author_email = conversation["createdBy"]["email"]
            subject = conversation.get("subject", "No Subject Available")

            requester_id = self.zendesk.get_or_create_user(
                author_email, display_name=self._display_name(conversation)
            )

            comments = self._build_comments(conversation_id)

            response = self.zendesk.create_ticket(
                group_id=zendesk_group_id,
                requester_id=requester_id,
                subject=subject,
                comments=comments,
                tags=["hs_ticket_import", f"helpscout_number_{helpscout_number}"],
                external_id=f"hs{conversation_id}",
            )

            ticket_id = response.get("job_status", {}).get("id")
            logger.info("Migrated HelpScout conversation %s", conversation_id)
            return MigrationResult(
                helpscout_conversation_id=conversation_id,
                zendesk_ticket_id=ticket_id,
                status=MigrationStatus.SUCCESS,
            )
        except Exception as exc:  # noqa: BLE001 - log and continue the batch
            logger.error("Failed to migrate conversation %s: %s", conversation_id, exc)
            return MigrationResult(
                helpscout_conversation_id=conversation_id,
                zendesk_ticket_id=None,
                status=MigrationStatus.FAILED,
                detail=str(exc),
            )

    def _build_comments(self, conversation_id: int) -> list[Comment]:
        comments: list[Comment] = []
        for thread in self.helpscout.get_threads(conversation_id):
            if "body" not in thread:
                continue

            thread_author_email = thread["createdBy"]["email"]
            author_id = self.zendesk.get_or_create_user(thread_author_email)
            plain_text = html_to_plain_text(thread["body"]) or "No threaded content"

            comments.append(
                Comment(
                    author_id=author_id,
                    value=plain_text,
                    created_at=thread["createdAt"],
                )
            )
        return comments

    @staticmethod
    def _display_name(conversation: dict) -> str:
        created_by = conversation.get("createdBy", {})
        name = f"{created_by.get('first', '')} {created_by.get('last', '')}".strip()
        return name or created_by.get("email", "External User")

    def _append_result_row(self, result: MigrationResult) -> None:
        file_exists = self.results_csv_path.exists()
        with self.results_csv_path.open("a", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=["helpscout_conversation_id", "zendesk_ticket_id", "status", "detail"],
            )
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "helpscout_conversation_id": result.helpscout_conversation_id,
                    "zendesk_ticket_id": result.zendesk_ticket_id,
                    "status": result.status.value,
                    "detail": result.detail,
                }
            )
