import unittest
from skills.workflow.scripts.workflow_lib.document_approvals import canonical_document_bytes


class DocumentLineEndingTests(unittest.TestCase):
    def test_windows_checkout_crlf_matches_lf_git_blob(self):
        raw = b'openapi: 3.1.0\r\npaths: {}\r\n'
        self.assertEqual(canonical_document_bytes(raw, windows=True), b'openapi: 3.1.0\npaths: {}\n')

    def test_tracked_crlf_document_preserves_legacy_hash_on_both_hosts(self):
        raw = b'a\r\nb\n'
        self.assertEqual(canonical_document_bytes(raw, windows=False), raw)
        self.assertEqual(canonical_document_bytes(raw, windows=True, baseline=raw), raw)
