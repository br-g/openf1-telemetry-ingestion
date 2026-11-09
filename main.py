import os
import traceback
from datetime import datetime, timedelta, timezone

from loguru import logger
from requests import HTTPError
from openf1.services.ingestor_livetiming.historical.main import ingest_collections
from openf1.util.db import _get_mongo_db_sync
from openf1.util.openf1_client import get

from pushover import send_pushover_alert


REINGESTION_WINDOW = timedelta(hours=6)
REINGEST_COLLECTIONS = ["pit"]


def load_f1_token_from_db():
    """Load the token maintained by openf1-ingestor without refreshing it."""
    document = _get_mongo_db_sync()["_f1_tokens"].find_one(
        {"_key": "current_token"}, sort=[("timestamp", -1)]
    )
    token = document.get("token") if document else None
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("No valid F1 token found in MongoDB collection _f1_tokens")
    os.environ["F1_TOKEN"] = token
    logger.info("F1 token loaded from MongoDB")


def ingest_telemetry(now=None):
    now = now or datetime.now(timezone.utc)
    # Query by end time rather than 'latest': multiple sessions may qualify,
    # and the reingestion window can cross a year boundary.
    try:
        sessions = get(
            "v1/sessions",
            # requests supplies the "=" separator, completing >= and <=.
            params={
                "date_end>": (now - REINGESTION_WINDOW).isoformat(),
                "date_end<": now.isoformat(),
                "is_cancelled": False,
            },
        )
    except HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        logger.info("No sessions found in the reingestion window; skipping ingestion")
        return
    eligible_sessions = []
    for session in sessions:
        if not session.get("date_end") or session.get("is_cancelled"):
            continue
        end = datetime.fromisoformat(session["date_end"].replace("Z", "+00:00"))
        if end <= now <= end + REINGESTION_WINDOW:
            eligible_sessions.append(session)

    if not eligible_sessions:
        logger.info("Outside all session reingestion windows; skipping ingestion")
        return

    load_f1_token_from_db()

    for session in eligible_sessions:
        try:
            ingest_collections(
                year=session["year"],
                meeting_key=session["meeting_key"],
                session_key=session["session_key"],
                collection_names=REINGEST_COLLECTIONS,
            )
        except ValueError:  # Data not yet available
            logger.info("Data not yet available for session {}", session["session_key"])
            continue
        send_pushover_alert(title="Telemetry ingested", message="Telemetry ingested")


if __name__ == "__main__":
    try:
        ingest_telemetry()
    except Exception:
        stack_trace = traceback.format_exc()
        logger.error(stack_trace)
        send_pushover_alert(title="Failed to ingest telemetry", message=stack_trace)
        raise
