import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from requests import HTTPError, Request, Response
from urllib.parse import unquote


# Load the entrypoint without importing the database-backed ingestion service.
def load_job():
    modules = {}
    for name in (
        "loguru", "openf1", "openf1.services", "openf1.services.ingestor_livetiming",
        "openf1.services.ingestor_livetiming.historical",
        "openf1.services.ingestor_livetiming.historical.main", "openf1.util",
        "openf1.util.openf1_client", "pushover",
    ):
        modules[name] = ModuleType(name)
    modules["loguru"].logger = Mock()
    modules["openf1.services.ingestor_livetiming.historical.main"].ingest_collections = Mock()
    modules["openf1.util.openf1_client"].get = Mock()
    modules["pushover"].send_pushover_alert = Mock()
    spec = importlib.util.spec_from_file_location("job", Path(__file__).parents[1] / "main.py")
    job = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(job)
    return job


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.job = load_job()
        self.now = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)

    def session(self, hours, key=1, **extra):
        return dict(year=2025, meeting_key=10, session_key=key,
                    date_end=(self.now - timedelta(hours=hours)).isoformat(), **extra)

    def test_inclusive_window_and_multiple_sessions(self):
        self.job.get.return_value = [self.session(0, 1), self.session(self.job.REINGESTION_WINDOW.total_seconds() / 3600, 2)]
        self.job.ingest_telemetry(self.now)
        self.assertEqual(self.job.ingest_collections.call_count, 2)
        self.assertEqual(self.job.ingest_collections.call_args.kwargs,
                         dict(year=2025, meeting_key=10, session_key=2, collection_names=["pit"]))
        self.assertEqual(self.job.get.call_args.args, ("v1/sessions",))
        self.assertEqual(self.job.get.call_args.kwargs["params"]["date_end>"],
                         (self.now - self.job.REINGESTION_WINDOW).isoformat())

    def test_outside_window_cancelled_and_missing_end_are_skipped(self):
        self.job.get.return_value = [self.session(-0.001), self.session(self.job.REINGESTION_WINDOW.total_seconds() / 3600 + 0.001),
                                     self.session(1, is_cancelled=True), {"date_end": None}]
        self.job.ingest_telemetry(self.now)
        self.job.ingest_collections.assert_not_called()
        self.job.send_pushover_alert.assert_not_called()

    def test_schedule_filters_encode_inclusive_comparisons(self):
        self.job.get.return_value = []
        self.job.ingest_telemetry(self.now)
        params = self.job.get.call_args.kwargs["params"]
        url = unquote(Request("GET", "https://api.openf1.org/v1/sessions",
                              params=params).prepare().url)
        self.assertIn("date_end>=" + (self.now - self.job.REINGESTION_WINDOW).isoformat(), url)
        self.assertIn("date_end<=" + self.now.isoformat(), url)
        self.assertNotIn(">==", url)
        self.assertNotIn("<==", url)

    def test_schedule_404_skips_ingestion(self):
        response = Response()
        response.status_code = 404
        self.job.get.side_effect = HTTPError(response=response)
        self.job.ingest_telemetry(self.now)
        self.job.ingest_collections.assert_not_called()
        self.job.send_pushover_alert.assert_not_called()

    def test_other_http_errors_propagate(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                response = Response()
                response.status_code = status
                self.job.get.side_effect = HTTPError(response=response)
                with self.assertRaises(HTTPError):
                    self.job.ingest_telemetry(self.now)
        self.job.ingest_collections.assert_not_called()

    def test_empty_schedule(self):
        self.job.get.return_value = []
        self.job.ingest_telemetry(self.now)
        self.job.ingest_collections.assert_not_called()

    def test_collections_can_be_configured_and_unavailable_session_does_not_stop_next(self):
        self.job.get.return_value = [self.session(1, 1), self.session(2, 2)]
        self.job.ingest_collections.side_effect = [ValueError("not available"), None]
        with patch.object(self.job, "REINGEST_COLLECTIONS", ["pit", "car_data"]):
            self.job.ingest_telemetry(self.now)
        self.assertEqual(self.job.ingest_collections.call_count, 2)
        self.assertEqual(self.job.ingest_collections.call_args.kwargs["collection_names"],
                         ["pit", "car_data"])
        self.job.send_pushover_alert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
