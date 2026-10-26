import copy
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from legacy_http import LedgerServer, seed_demo
from ledger import Ledger, LedgerConflict, calculate_hash, canonical_json, create_new_block
from snapshots import MAX_SNAPSHOT_BYTES, Snapshots


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.ledger = Ledger(self.folder.name)
        self.snapshots = Snapshots(self.ledger)
        self.ledger.append_result({"match_id": "one", "data": {"score": 5}})

    def tearDown(self):
        self.ledger.close()
        self.folder.cleanup()

    def rewrite(self, blocks):
        self.ledger.path.write_bytes(b"".join(canonical_json(block) + b"\n" for block in blocks))

    def test_chain_export_is_encrypted_and_old_prefix_still_matches(self):
        token, index = self.snapshots.export()
        self.assertEqual(index, 1)
        self.assertNotIn(b'"match_id"', token)
        self.assertTrue(self.snapshots.validate(token)["valid"])
        self.ledger.append_result({"match_id": "two", "data": {}})
        report = self.snapshots.validate(token)
        self.assertEqual((report["valid"], report["checked_blocks"], report["new_blocks"]), (True, 2, 1))

    def test_single_block_is_not_a_chain_prefix(self):
        token, index = self.snapshots.export(1)
        payload = json.loads(self.snapshots.cipher.decrypt(token))
        self.assertEqual(payload["kind"], "block")
        self.assertEqual(len(payload["blocks"]), 1)
        self.assertEqual(payload["blocks"][0]["index"], 1)
        self.assertEqual(index, 1)
        self.assertTrue(self.snapshots.validate(token)["valid"])
        self.assertTrue(self.snapshots.validate(self.snapshots.export(0)[0])["valid"])
        for bad_index in (-1, 2, True, "1"):
            with self.assertRaises(ValueError):
                self.snapshots.export(bad_index)

    def test_key_persists_across_restart(self):
        token, _ = self.snapshots.export()
        key = (self.ledger.directory / "snapshot.key").read_bytes()
        self.ledger.close()
        self.ledger = Ledger(self.folder.name)
        self.snapshots = Snapshots(self.ledger)
        self.assertEqual(key, (self.ledger.directory / "snapshot.key").read_bytes())
        self.assertTrue(self.snapshots.validate(token)["valid"])

    def test_invalid_key_is_not_replaced(self):
        path = self.ledger.directory / "snapshot.key"
        path.write_bytes(b"broken key")
        with self.assertRaises(ValueError):
            Snapshots(self.ledger)
        self.assertEqual(path.read_bytes(), b"broken key")

    def test_modified_wrong_key_and_malformed_files_rejected(self):
        token, _ = self.snapshots.export()
        changed = bytearray(token)
        changed[len(changed) // 2] = ord("A") if changed[len(changed) // 2] != ord("A") else ord("B")
        wrong_key = Fernet(Fernet.generate_key()).encrypt(b"{}")
        for invalid in (b"", b"not a snapshot", bytes(changed), wrong_key, token + b"!", token + b"\n"):
            with self.subTest(file=invalid[:10]):
                with self.assertRaises(ValueError):
                    self.snapshots.validate(invalid)

    def test_rebuilt_history_and_deleted_suffix_fail(self):
        token, _ = self.snapshots.export()
        blocks = self.ledger.view()["blocks"]
        blocks[1]["data"]["score"] = 99
        blocks[1]["hash"] = calculate_hash(blocks[1])
        self.rewrite(blocks)
        report = self.snapshots.validate(token)
        self.assertFalse(report["valid"])
        self.assertEqual(report["errors"][0]["index"], 1)
        self.rewrite(blocks[:1])
        report = self.snapshots.validate(token)
        self.assertFalse(report["valid"])
        self.assertIn("missing", report["errors"][0]["message"])

    def test_single_block_compared_and_current_chain_must_be_valid(self):
        token, _ = self.snapshots.export(1)
        blocks = self.ledger.view()["blocks"]
        blocks[1]["data"]["score"] = 99
        blocks[1]["hash"] = calculate_hash(blocks[1])
        self.rewrite(blocks)
        self.assertFalse(self.snapshots.validate(token)["valid"])
        blocks.append(create_new_block(blocks[-1], {"match_id": "two", "data": {}}))
        blocks[-1]["data"]["tampered"] = True
        self.rewrite(blocks)
        before = self.ledger.path.read_bytes()
        self.assertFalse(self.snapshots.validate(token)["valid"])
        self.assertEqual(before, self.ledger.path.read_bytes())
        with self.assertRaises(LedgerConflict):
            self.snapshots.export()

    def test_authenticated_but_invalid_payloads_rejected(self):
        token, _ = self.snapshots.export()
        original = json.loads(self.snapshots.cipher.decrypt(token))
        variants = [[], {}, dict(original, format_version=True), dict(original, kind="other"),
                    dict(original, blocks=[]), dict(original, exported_at_ms=True)]
        changed_genesis = copy.deepcopy(original)
        changed_genesis["blocks"][0]["data"]["message"] = "Changed"
        changed_genesis["blocks"][0]["hash"] = calculate_hash(changed_genesis["blocks"][0])
        variants.append(changed_genesis)
        for value in variants:
            with self.assertRaises(ValueError):
                self.snapshots.validate(self.snapshots.cipher.encrypt(canonical_json(value)))

    def test_snapshot_envelope_preserves_allowed_record_depth(self):
        data = {"value": 1}
        for _ in range(18):
            data = {"nested": data}
        self.ledger.append_result({"match_id": "nested", "data": data})
        token, _ = self.snapshots.export()
        self.assertTrue(self.snapshots.validate(token)["valid"])

    def test_download_and_upload_size_limits(self):
        with self.assertRaises(ValueError):
            self.snapshots.validate(b"A" * (MAX_SNAPSHOT_BYTES + 1))
        with patch("snapshots.MAX_SNAPSHOT_BYTES", 100):
            with self.assertRaises(OverflowError):
                self.snapshots.export()

    def test_demo_seed_is_explicit_and_idempotent(self):
        self.assertEqual(len(self.ledger.view()["blocks"]), 2)
        seed_demo(self.ledger)
        first = self.ledger.path.read_bytes()
        seed_demo(self.ledger)
        self.assertEqual(first, self.ledger.path.read_bytes())
        demo = self.ledger.view()["blocks"][2:]
        self.assertEqual(len(demo), 4)
        self.assertTrue(all(block["data"]["demo"] for block in demo))


class SnapshotApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.folder.name) / "data")
        self.server = LedgerServer(("127.0.0.1", 0), self.ledger, self.folder.name,
                                   allowed_hosts=["ledger.example", "192.0.2.10"])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.ledger.close()
        self.folder.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        content_type = response.getheader("Content-Type")
        result = response.read()
        status = response.status
        disposition = response.getheader("Content-Disposition")
        connection.close()
        if "application/json" in content_type:
            result = json.loads(result)
        return status, result, disposition

    def test_download_upload_routes_and_headers(self):
        status, token, disposition = self.request("GET", "/api/snapshot")
        self.assertEqual(status, 200)
        self.assertIn('ledger-0.ledger', disposition)
        status, report, _ = self.request("POST", "/api/validate-snapshot", token,
                                       {"Content-Type": "application/octet-stream"})
        self.assertEqual(status, 200)
        self.assertTrue(report["valid"])
        status, single, _ = self.request("GET", "/api/snapshot?block=0")
        self.assertEqual(status, 200)
        self.assertEqual(self.server.snapshots.validate(single)["kind"], "block")
        for query in ("block=-1", "block=x", "block=1", "block=0&block=0", "other=1", "block="):
            self.assertEqual(self.request("GET", "/api/snapshot?" + query)[0], 400)
        self.assertEqual(self.request("POST", "/api/validate-snapshot", b"invalid",
                                     {"Content-Type": "application/octet-stream"})[0], 400)
        self.assertEqual(self.request("POST", "/api/validate-snapshot", token,
                                     {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/api/validate-snapshot", b"",
                                     {"Content-Type": "application/octet-stream", "Content-Length": str(MAX_SNAPSHOT_BYTES + 1)})[0], 400)

    def test_explicit_remote_hosts_and_browser_origins(self):
        host = "ledger.example:" + str(self.server.server_port)
        self.assertEqual(self.request("GET", "/api/ledger", headers={"Host": host})[0], 200)
        self.assertEqual(self.request("GET", "/api/ledger", headers={"Host": host, "Origin": "http://" + host})[0], 200)
        submission = json.dumps({"match_id": "remote", "data": {}}).encode()
        self.assertEqual(self.request("POST", "/api/blocks", submission,
                                     {"Host": host, "Content-Type": "application/json"})[0], 201)
        for invalid in ({"Host": "evil.example:" + str(self.server.server_port)},
                        {"Host": host, "Origin": "http://evil.example:8000"},
                        {"Host": host, "Origin": "http://ledger.example:1"},
                        {"Host": "user@" + host}, {"Host": host + "#fragment"}):
            self.assertEqual(self.request("GET", "/api/ledger", headers=invalid)[0], 403)


if __name__ == "__main__":
    unittest.main()
