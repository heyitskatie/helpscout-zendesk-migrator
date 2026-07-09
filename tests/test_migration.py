"""End-to-end migration tests using mocked API clients.

These tests never make network calls. They stand in mocked HelpScoutClient
and ZendeskClient objects (built from the fixtures in samples/) so the full
Migrator.run() flow can be exercised without real HelpScout or Zendesk
credentials.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from checkpoint import Checkpoint
from helpscout import HelpScoutClient
from migration import Migrator
from models import MigrationStatus
from zendesk import ZendeskClient

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "samples"


@pytest.fixture
def sample_conversation() -> dict:
    return json.loads((FIXTURES_DIR / "sample_conversation.json").read_text())


@pytest.fixture
def sample_threads() -> list[dict]:
    payload = json.loads((FIXTURES_DIR / "sample_threads.json").read_text())
    return payload["_embedded"]["threads"]


@pytest.fixture
def mock_helpscout(sample_conversation, sample_threads) -> MagicMock:
    client = MagicMock(spec=HelpScoutClient)
    client.list_conversations.return_value = iter([sample_conversation])
    client.get_threads.return_value = sample_threads
    return client


@pytest.fixture
def mock_zendesk() -> MagicMock:
    client = MagicMock(spec=ZendeskClient)
    client.get_or_create_user.return_value = 555000111
    client.create_ticket.return_value = {"job_status": {"id": 999888777}}
    return client


@pytest.fixture
def migrator(mock_helpscout, mock_zendesk, tmp_path) -> Migrator:
    checkpoint = Checkpoint(tmp_path / "checkpoint.json")
    results_csv_path = tmp_path / "migration_results.csv"
    return Migrator(
        helpscout=mock_helpscout,
        zendesk=mock_zendesk,
        checkpoint=checkpoint,
        results_csv_path=results_csv_path,
    )


def test_run_migrates_sample_conversation_successfully(
    migrator, mock_helpscout, mock_zendesk, sample_conversation
):
    results = migrator.run(
        mailbox_id="5",
        zendesk_group_id="12",
        start_date="2022-01-01T00:00:00Z",
        end_date="2022-12-31T23:59:59Z",
    )

    assert len(results) == 1
    assert results[0].status == MigrationStatus.SUCCESS
    assert results[0].helpscout_conversation_id == sample_conversation["id"]
    assert results[0].zendesk_ticket_id == 999888777


def test_run_creates_zendesk_user_for_requester_and_each_thread_author(
    migrator, mock_zendesk, sample_conversation
):
    migrator.run(
        mailbox_id="5",
        zendesk_group_id="12",
        start_date="2022-01-01T00:00:00Z",
        end_date="2022-12-31T23:59:59Z",
    )

    called_emails = [call.args[0] for call in mock_zendesk.get_or_create_user.call_args_list]

    # Once for the conversation requester, once per thread author (2 threads in fixture).
    assert called_emails[0] == sample_conversation["createdBy"]["email"]
    assert len(called_emails) == 3


def test_run_builds_ticket_with_plain_text_comments(migrator, mock_zendesk):
    migrator.run(
        mailbox_id="5",
        zendesk_group_id="12",
        start_date="2022-01-01T00:00:00Z",
        end_date="2022-12-31T23:59:59Z",
    )

    _, kwargs = mock_zendesk.create_ticket.call_args
    comments = kwargs["comments"]

    assert len(comments) == 2
    assert all("<p>" not in comment.value for comment in comments)
    assert "check-in time" in comments[0].value


def test_run_writes_checkpoint_after_each_conversation(migrator, tmp_path):
    migrator.run(
        mailbox_id="5",
        zendesk_group_id="12",
        start_date="2022-01-01T00:00:00Z",
        end_date="2022-12-31T23:59:59Z",
    )

    checkpoint_file = tmp_path / "checkpoint.json"
    assert checkpoint_file.exists()
    state = json.loads(checkpoint_file.read_text())
    assert state["last_conversation_id"] == 123456789
    assert state["last_zendesk_ticket_id"] == 999888777


def test_run_writes_results_csv(migrator, tmp_path):
    migrator.run(
        mailbox_id="5",
        zendesk_group_id="12",
        start_date="2022-01-01T00:00:00Z",
        end_date="2022-12-31T23:59:59Z",
    )

    results_file = tmp_path / "migration_results.csv"
    contents = results_file.read_text()
    assert "helpscout_conversation_id" in contents
    assert "success" in contents


def test_run_records_failure_without_stopping_the_batch(migrator, mock_zendesk):
    mock_zendesk.create_ticket.side_effect = RuntimeError("Zendesk API unavailable")

    results = migrator.run(
        mailbox_id="5",
        zendesk_group_id="12",
        start_date="2022-01-01T00:00:00Z",
        end_date="2022-12-31T23:59:59Z",
    )

    assert len(results) == 1
    assert results[0].status == MigrationStatus.FAILED
    assert results[0].zendesk_ticket_id is None
    assert "Zendesk API unavailable" in results[0].detail
