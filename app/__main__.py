from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import uvicorn

from app.api import create_app
from app.bootstrap import bootstrap_memory
from app.config import get_settings
from app.db import init_db
from app.richpanel_client import RichpanelClient
from app.sync_loop import start_sync_loop


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Serve the review dashboard and API")
    bootstrap = commands.add_parser(
        "bootstrap-memory", help="Import approved replies from closed tickets"
    )
    bootstrap.add_argument("--start", help="Start date (YYYY-MM-DD)")
    bootstrap.add_argument("--end", help="End date (YYYY-MM-DD)")
    return parser


def _client(settings):
    return RichpanelClient(
        settings.richpanel_api_token,
        settings.richpanel_base_url,
    )


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    settings = get_settings()
    client = _client(settings)

    if args.command == "serve":
        init_db(settings.database_path).close()
        stop_event, thread = start_sync_loop(settings, client)
        try:
            uvicorn.run(
                create_app(settings=settings, client=client),
                host=settings.host,
                port=settings.port,
            )
        finally:
            stop_event.set()
            thread.join(timeout=5)
        return

    today = datetime.now(UTC).date()
    start_date = args.start or (today - timedelta(days=90)).isoformat()
    end_date = args.end or today.isoformat()
    conn = init_db(settings.database_path)
    try:
        inserted = bootstrap_memory(
            conn,
            client,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )
    finally:
        conn.close()
    print(f"Imported {inserted} approved replies")


if __name__ == "__main__":
    main()
