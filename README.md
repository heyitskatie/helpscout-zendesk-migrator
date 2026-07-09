# HelpScout → Zendesk Migration Tool

A Python utility that migrates closed HelpScout conversations into Zendesk as tickets, using the public APIs for both platforms. Built to handle large historical backlogs safely: it resumes after interruptions, retries on rate limits, and reports results to a CSV file.

![Python CI](https://github.com/heyitskatie/helpscout-zendesk-migrator/actions/workflows/python.yml/badge.svg)

## Why this exists

Support teams switching help desk platforms often need to bring years of historical tickets with them. This tool was built to migrate a multi-year HelpScout conversation history into Zendesk while preserving the original requester, thread history, and timestamps, without manual copy-paste.

## Features

- OAuth2 authentication with HelpScout, with automatic token refresh on expiry
- Resumable migrations via a JSON checkpoint file, so a network blip does not mean starting over
- Automatic retry with exponential backoff on transient errors (502s, rate limits)
- HTML-to-plain-text conversion for thread bodies
- Automatic Zendesk user lookup, un-suspension, and creation
- Configurable skip list for system/shared mailbox addresses
- CSV report of every migration outcome (success, failure, or skip)
- Structured logging to both console and file

## Project structure

```
helpscout-zendesk-migrator/
├── src/
│   ├── main.py         # CLI entry point
│   ├── config.py       # Settings loaded from environment variables
│   ├── helpscout.py    # HelpScout API client
│   ├── zendesk.py      # Zendesk API client
│   ├── migration.py    # Migration orchestration
│   ├── checkpoint.py   # Resume-on-failure state
│   ├── models.py       # Typed data structures
│   └── utils.py        # HTML/attachment helpers
├── samples/             # Example API payloads for local testing
├── tests/                # Unit tests (pytest)
└── .github/workflows/    # CI: ruff, black, mypy, pytest
```

## Requirements

- Python 3.11+
- A HelpScout OAuth2 app (Client ID and Secret)
- A Zendesk API token

## Installation

```bash
git clone https://github.com/heyitskatie/helpscout-zendesk-migrator.git
cd helpscout-zendesk-migrator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `HELPSCOUT_CLIENT_ID` | HelpScout OAuth2 app client ID |
| `HELPSCOUT_CLIENT_SECRET` | HelpScout OAuth2 app client secret |
| `ZENDESK_EMAIL` | Zendesk admin email used for API auth |
| `ZENDESK_API_TOKEN` | Zendesk API token |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain, e.g. `yourcompany` for `yourcompany.zendesk.com` |
| `SKIP_EMAILS` | Comma-separated system addresses to route to the fallback user |
| `DEFAULT_FALLBACK_USER_ID` | Zendesk user ID used for system emails or failed user creation |

## Usage

```bash
python src/main.py \
  --mailbox 5 \
  --group 12 \
  --start 2020-01-01 \
  --end 2023-12-31
```

| Flag | Description |
|---|---|
| `--mailbox` | HelpScout mailbox ID to migrate from |
| `--group` | Zendesk group ID to assign imported tickets to |
| `--start` | Start date (`YYYY-MM-DD`) |
| `--end` | End date (`YYYY-MM-DD`) |
| `--checkpoint-file` | Optional path for the resume checkpoint (default: `checkpoint.json`) |
| `--results-file` | Optional path for the CSV outcome report (default: `migration_results.csv`) |

If the process is interrupted, rerun the same command. It picks up from the last saved page in `checkpoint.json` rather than starting over.

### Sample data

The `samples/` directory contains example HelpScout API payloads (`sample_conversation.json`, `sample_threads.json`) and a sample user mapping (`users.csv`) so you can inspect the expected data shapes without hitting a live account.

## Running tests

The test suite runs entirely offline. `tests/test_migration.py` mocks both
`HelpScoutClient` and `ZendeskClient` and replays the fixtures in
`samples/` through the full `Migrator.run()` flow, so the end-to-end
migration logic (user resolution, comment building, checkpointing, CSV
reporting, failure handling) is exercised without hitting either platform
or needing live credentials.

```bash
pip install -r requirements.txt
pytest
```

## Development

This project uses Ruff for linting, Black for formatting, and mypy for type checking:

```bash
ruff check src tests
black src tests
mypy src
```

## Security notes

- Credentials are read from environment variables only. Nothing sensitive is hardcoded.
- All HTTP requests use standard TLS certificate verification.
- `checkpoint.json` and `migration_results.csv` are git-ignored since they can contain real customer data from a live run.

## License

MIT. See [LICENSE](LICENSE).
