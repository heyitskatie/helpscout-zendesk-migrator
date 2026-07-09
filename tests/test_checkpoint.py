import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from checkpoint import Checkpoint, CheckpointState


def test_load_returns_default_when_file_missing(tmp_path):
    checkpoint = Checkpoint(tmp_path / "checkpoint.json")
    default = CheckpointState(mailbox_id="5", zendesk_group_id="12")

    result = checkpoint.load(default)

    assert result == default


def test_save_and_load_roundtrip(tmp_path):
    checkpoint = Checkpoint(tmp_path / "checkpoint.json")
    state = CheckpointState(
        mailbox_id="5",
        zendesk_group_id="12",
        page=3,
        last_conversation_id=42,
        last_zendesk_ticket_id=99,
    )

    checkpoint.save(state)
    loaded = checkpoint.load(CheckpointState(mailbox_id="5", zendesk_group_id="12"))

    assert loaded == state


def test_clear_removes_file(tmp_path):
    path = tmp_path / "checkpoint.json"
    checkpoint = Checkpoint(path)
    checkpoint.save(CheckpointState(mailbox_id="5", zendesk_group_id="12"))

    checkpoint.clear()

    assert not path.exists()
