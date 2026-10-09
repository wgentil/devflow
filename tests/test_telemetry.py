import json
import tempfile
import io
from contextlib import redirect_stderr
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.telemetry import record_offload


class TelemetryTests(unittest.TestCase):
    def test_success_and_failure_measurements_keep_attribution_and_utf8_byte_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            success = {"operation_id": "op-1", "operation": "digest", "duration_ms": 4, "result": "ok",
                       "input_bytes": len("東京".encode()), "output_bytes": 3,
                       "run_id": "run-1", "attempt_id": "attempt-1", "work_item": "W1"}
            failed = {"operation_id": "op-2", "operation": "verify", "duration_ms": 8, "result": "error",
                      "input_bytes": 9, "output_bytes": 0}
            self.assertTrue(record_offload(root, success)["recorded"])
            self.assertTrue(record_offload(root, failed)["recorded"])
            rows = [json.loads(line) for line in (root / "offload.jsonl").read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[0]["input_bytes"], 6)
            self.assertEqual(rows[0]["run_id"], "run-1")
            self.assertNotIn("run_id", rows[1])
            self.assertEqual(rows[1]["result"], "error")

    def test_repeated_operation_id_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            item = {"operation_id": "same", "operation": "hash", "duration_ms": 1, "result": "ok",
                    "input_bytes": 1, "output_bytes": 1}
            record_offload(root, item)
            repeated = record_offload(root, item)
            self.assertTrue(repeated["duplicate"])
            self.assertEqual(len((root / "offload.jsonl").read_text(encoding='utf-8').splitlines()), 1)

    def test_collection_failure_is_returned_without_raising_or_changing_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "file"
            root.write_text("occupied")
            measurement = {"operation_id": "lost", "operation": "read", "duration_ms": 1,
                           "result": "ok", "input_bytes": 0, "output_bytes": 2}
            before = dict(measurement)
            warning = io.StringIO()
            with redirect_stderr(warning):
                outcome = record_offload(root, measurement)
            self.assertIn('offload telemetry gap', warning.getvalue())
            self.assertFalse(outcome["recorded"])
            self.assertTrue(outcome["gap"])
            self.assertEqual(measurement, before)


if __name__ == "__main__":
    unittest.main()
