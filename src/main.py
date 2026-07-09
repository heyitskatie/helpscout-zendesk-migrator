"""CLI entry point for the HelpScout -> Zendesk migration tool.

Example:
    python src/main.py --mailbox 5 --group 12 --start 2020-01-01 --end 2023-12-31
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from checkpoint import Checkpoint
from config import Settings
from helpscout import HelpScoutClient
from migration import Migrator
from zendesk import ZendeskClient

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def configure_logging() -> None:
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "migration.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate closed HelpScout conversations into Zendesk as tickets."
    )
    parser.add_argument("--mailbox", required=True, help="HelpScout mailbox ID")
    parser.add_argument("--group", required=True, help="Zendesk group ID for imported tickets")
    parser.add_argument("--start", required=True, help="Start date, e.g. 2020-01-01")
    parser.add_argument("--end", required=True, help="End date, e.g. 2023-12-31")
    parser.add_argument(
        "--checkpoint-file",
        default="checkpoint.json",
        help="Path to the checkpoint file used to resume interrupted runs",
    )
    parser.add_argument(
        "--results-file",
        default="migration_results.csv",
        help="Path to the CSV report of migration outcomes",
    )
    return parser.parse_args()


def to_iso_range(date_str: str, end_of_day: bool = False) -> str:
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{date_str}{suffix}"


def main() -> None:
    configure_logging()
    args = parse_args()
    logger = logging.getLogger(__name__)

    settings = Settings.from_env()

    helpscout = HelpScoutClient(settings)
    zendesk = ZendeskClient(settings)
    checkpoint = Checkpoint(Path(args.checkpoint_file))

    migrator = Migrator(
        helpscout=helpscout,
        zendesk=zendesk,
        checkpoint=checkpoint,
        results_csv_path=Path(args.results_file),
    )

    results = migrator.run(
        mailbox_id=args.mailbox,
        zendesk_group_id=args.group,
        start_date=to_iso_range(args.start),
        end_date=to_iso_range(args.end, end_of_day=True),
    )

    succeeded = sum(1 for r in results if r.status.value == "success")
    failed = sum(1 for r in results if r.status.value == "failed")
    logger.info("Migration complete: %s succeeded, %s failed.", succeeded, failed)


if __name__ == "__main__":
    main()
