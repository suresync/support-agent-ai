from __future__ import annotations

import logging
import threading

from app.db import init_db
from app.ingest import sync_once


logger = logging.getLogger(__name__)


def run_sync_loop(settings, client, stop_event: threading.Event) -> None:
    """Run sync immediately, then periodically until asked to stop."""
    while not stop_event.is_set():
        conn = init_db(settings.database_path)
        try:
            sync_once(conn, client, settings)
        except Exception:
            logger.exception("Background sync failed")
        finally:
            conn.close()
        stop_event.wait(settings.sync_interval_seconds)


def start_sync_loop(settings, client) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_sync_loop,
        args=(settings, client, stop_event),
        name="support-agent-sync",
        daemon=True,
    )
    thread.start()
    return stop_event, thread
