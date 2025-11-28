import traceback

from loguru import logger
from openf1.services.ingestor_livetiming.historical.main import ingest_collections
from openf1.util.openf1_client import get

from pushover import send_pushover_alert


def ingest_telemetry():
    session = get("v1/sessions?session_key=latest")[0]
    ingest_collections(
        year=session["year"],
        meeting_key=session["meeting_key"],
        session_key=session["session_key"],
        collection_names=["location", "car_data", "intervals"],
    )


try:
    ingest_telemetry()
except ValueError as e:
    stack_trace = traceback.format_exc()
    logger.error(stack_trace)
    send_pushover_alert(title="Failed to ingest telemetry", message=stack_trace)
