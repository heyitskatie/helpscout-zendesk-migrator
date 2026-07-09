import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from models import Comment, MigrationResult, MigrationStatus


def test_comment_to_dict():
    comment = Comment(author_id=123, value="Hello", created_at="2022-01-01T00:00:00Z")

    result = comment.to_dict()

    assert result == {
        "author_id": 123,
        "value": "Hello",
        "created_at": "2022-01-01T00:00:00Z",
        "public": True,
    }


def test_migration_result_defaults_detail_to_empty_string():
    result = MigrationResult(
        helpscout_conversation_id=1,
        zendesk_ticket_id=None,
        status=MigrationStatus.FAILED,
    )

    assert result.detail == ""
