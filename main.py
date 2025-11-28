import traceback

from loguru import logger
from openf1.services.ingestor_livetiming.historical.main import ingest_collections
from openf1.util.openf1_client import get
from requests import HTTPError

from pushover import send_pushover_alert


def ingest_telemetry():
    try:
        r = get("v1/car_data?session_key=latest")
        if r != []:  # data already ingested
            logger.info("Data already ingested (1)")
            return
    except HTTPError:  # data already ingested
        logger.info("Data already ingested (2)")
        return

    session = get("v1/sessions?session_key=latest")[0]

    try:
        ingest_collections(
            year=session["year"],
            meeting_key=session["meeting_key"],
            session_key=session["session_key"],
            collection_names=["location", "car_data", "intervals"],
        )
        send_pushover_alert(title="Telemetry ingested", message="Telemetry ingested")
    except ValueError:  # Data not yet available
        logger.info("Data not yet available")


try:
    ingest_telemetry()
except ValueError as e:
    stack_trace = traceback.format_exc()
    logger.error(stack_trace)
    send_pushover_alert(title="Failed to ingest telemetry", message=stack_trace)
