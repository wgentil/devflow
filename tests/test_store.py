import json
import tempfile
import threading
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))

from workflow_lib.store import WorkflowError, read_state, transact


def tree_bytes(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_stale_version_rejects_without_changing_bytes(self):
        transact(self.root, 0, "one", {"kind": "note", "payload": {"x": 1}})
        before = tree_bytes(self.root)
        with self.assertRaises(WorkflowError) as caught:
            transact(self.root, 0, "two", {"kind": "note", "payload": {"x": 2}})
        self.assertEqual(caught.exception.code, "STALE_STATE")
        self.assertEqual(tree_bytes(self.root), before)

    def test_invalid_run_transition_is_rejected_before_event_commit(self):
        before = tree_bytes(self.root)
        with self.assertRaises(WorkflowError) as caught:
            transact(self.root, 0, "bad-run-event", {"kind": "run.attempt.issued", "payload": {}})
        self.assertEqual(caught.exception.code, "INVALID_EVENT")
        self.assertEqual(tree_bytes(self.root), before)

    def test_run_result_event_cannot_claim_verification_without_registered_proof(self):
        started = transact(self.root, 0, "start", {"kind": "run.started", "payload": {"run": {
            "id": "r", "items": {"w": {"status": "pending", "attempts": []}},
            "state_version": 0, "active_attempt": None, "verifier_proofs": {},
        }}})
        issued = transact(self.root, started["state"]["version"], "issue", {"kind": "run.attempt.issued",
            "payload": {"run_id": "r", "attempt": {"token": "t", "item_id": "w",
            "state_version": 1, "status": "active", "result": None}}})
        before = tree_bytes(self.root)
        with self.assertRaises(WorkflowError) as caught:
            transact(self.root, issued["state"]["version"], "fake-proof", {"kind": "run.result.recorded",
                "payload": {"run_id": "r", "token": "t", "result": {"outcome": "passed"}, "verified": True}})
        self.assertEqual(caught.exception.code, "INVALID_EVENT")
        self.assertEqual(tree_bytes(self.root), before)

    def test_duplicate_operation_returns_original_event(self):
        first = transact(self.root, 0, "same", {"kind": "note", "payload": {"x": 1}})
        again = transact(self.root, 0, "same", {"kind": "different", "payload": {"x": 2}})
        self.assertEqual(again["event"], first["event"])
        self.assertTrue(again["replayed"])
        self.assertEqual(read_state(self.root)["data"], {"x": 1})

    def test_corrupt_and_future_event_schemas_fail_closed(self):
        journal = self.root / "events"
        journal.mkdir()
        (journal / "00000001.json").write_text("{")
        with self.assertRaises(WorkflowError) as caught:
            read_state(self.root)
        self.assertEqual(caught.exception.code, "CORRUPT_STATE")
        (journal / "00000001.json").write_text(json.dumps({
            "schema_version": 99, "sequence": 1, "operation_id": "x", "kind": "note", "payload": {}
        }))
        with self.assertRaises(WorkflowError) as caught:
            read_state(self.root)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_SCHEMA")

    def test_orphan_temporary_write_is_ignored_and_committed_event_replays(self):
        transact(self.root, 0, "one", {"kind": "set", "payload": {"accepted": ["R1"]}})
        snapshot = self.root / "state.json"
        snapshot.unlink()
        (self.root / "events" / ".00000002.abandoned.tmp").write_text('{"partial":')
        state = read_state(self.root)
        self.assertEqual(state["version"], 1)
        self.assertEqual(state["data"], {"accepted": ["R1"]})
        self.assertTrue(any("abandoned" in item for item in state["recovery"]["ignored_temporary_files"]))

    def test_concurrent_writers_keep_sequence_unique(self):
        errors = []
        def writer(n):
            for attempt in range(20):
                state = read_state(self.root)
                try:
                    transact(self.root, state["version"], f"op-{n}", {
                        "kind": "writer", "payload": {"writer": n},
                    })
                    return
                except WorkflowError as exc:
                    if exc.code != "STALE_STATE":
                        errors.append(exc)
                        return
            errors.append(AssertionError("writer exhausted stale retries"))
        threads = [threading.Thread(target=writer, args=(n,)) for n in range(12)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(errors, [])
        events = sorted((self.root / "events").glob("[0-9]*.json"))
        self.assertEqual(len(events), 12)
        self.assertEqual([json.loads(p.read_text(encoding='utf-8'))["sequence"] for p in events], list(range(1, 13)))


if __name__ == "__main__":
    unittest.main()
