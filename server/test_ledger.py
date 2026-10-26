import copy
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path

from legacy_http import LedgerServer
from ledger import (Ledger, LedgerConflict, calculate_hash, canonical_json,
                    create_genesis_block, create_new_block, parse_json, verify_chain)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.ledger = Ledger(self.folder.name)

    def tearDown(self):
        self.ledger.close()
        self.folder.cleanup()

    def test_genesis_and_canonical_order(self):
        first = create_genesis_block()
        self.assertEqual(first, create_genesis_block())
        self.assertEqual(first["timestamp_ms"], 0)
        self.assertEqual(canonical_json({"b": 1, "a": "é"}), b'{"a":"\xc3\xa9","b":1}')
        self.assertTrue(verify_chain([first])["valid"])

    def test_restart_and_idempotency(self):
        submission = {"match_id": "match-1", "data": {"scores": [5, 2], "name": "Pulkit"}}
        original, duplicate = self.ledger.append_result(submission)
        self.assertFalse(duplicate)
        self.ledger.close()
        self.ledger = Ledger(self.folder.name)
        repeated, duplicate = self.ledger.append_result(submission)
        self.assertTrue(duplicate)
        self.assertEqual(original, repeated)
        self.assertEqual(len(self.ledger.view()["blocks"]), 2)
        with self.assertRaises(LedgerConflict):
            self.ledger.append_result({"match_id": "match-1", "data": {"scores": [9, 2]}})

    def test_tampering_and_rebuilt_chain_limitation(self):
        self.ledger.append_result({"match_id": "match-1", "data": {"score": 2}})
        self.ledger.append_result({"match_id": "match-2", "data": {"score": 3}})
        blocks = self.ledger.view()["blocks"]
        checkpoint = blocks[-1]["hash"]
        blocks[1]["data"]["score"] = 999
        self.assertFalse(verify_chain(blocks)["valid"])
        blocks[1]["hash"] = calculate_hash(blocks[1])
        self.assertFalse(verify_chain(blocks)["valid"])
        blocks[2]["previous_hash"] = blocks[1]["hash"]
        blocks[2]["hash"] = calculate_hash(blocks[2])
        self.assertTrue(verify_chain(blocks)["valid"])
        self.assertNotEqual(checkpoint, blocks[-1]["hash"])

    def test_invalid_schema_genesis_and_duplicate_id(self):
        genesis = create_genesis_block()
        new = create_new_block(genesis, {"match_id": "one", "data": {}})
        for field, value in (("index", True), ("schema_version", 2), ("timestamp_ms", -1)):
            changed = copy.deepcopy(new)
            changed[field] = value
            changed["hash"] = calculate_hash(changed)
            self.assertFalse(verify_chain([genesis, changed])["valid"])
        changed = copy.deepcopy(genesis)
        changed["data"]["message"] = "Other genesis"
        changed["hash"] = calculate_hash(changed)
        self.assertFalse(verify_chain([changed])["valid"])
        repeated = create_new_block(new, {"match_id": "one", "data": {}})
        self.assertFalse(verify_chain([genesis, new, repeated])["valid"])

    def test_incomplete_file_blocks_append_without_repair(self):
        with self.ledger.path.open("ab") as file:
            file.write(b'{"unfinished":')
        before = self.ledger.path.read_bytes()
        self.assertFalse(self.ledger.view()["verification"]["valid"])
        with self.assertRaises(LedgerConflict):
            self.ledger.append_result({"match_id": "one", "data": {}})
        self.assertEqual(before, self.ledger.path.read_bytes())

    def test_process_lock(self):
        with self.assertRaises(OSError):
            Ledger(self.folder.name)

    def test_cli_verifier_is_read_only_and_works_with_writer(self):
        app = str(Path(__file__).parent / "app.py")
        result = subprocess.run([sys.executable, app, "--data-dir", self.folder.name, "--verify"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])
        missing = Path(self.folder.name) / "does-not-exist"
        result = subprocess.run([sys.executable, app, "--data-dir", str(missing), "--verify"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(missing.exists())

    def test_boolean_is_not_integer_for_retries(self):
        self.ledger.append_result({"match_id": "boolean", "data": {"score": True}})
        with self.assertRaises(LedgerConflict):
            self.ledger.append_result({"match_id": "boolean", "data": {"score": 1}})
        changed = self.ledger.view()["blocks"]
        changed[1]["data"]["score"] = 1
        self.assertFalse(verify_chain(changed)["valid"])

    def test_concurrent_appends(self):
        def append(index):
            return self.ledger.append_result({"match_id": "match-" + str(index), "data": {"score": index}})
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(append, range(20)))
        view = self.ledger.view()
        self.assertTrue(view["verification"]["valid"])
        self.assertEqual(len(view["blocks"]), 21)

    def test_strict_json_profile(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1.5}', '{"a":9007199254740992}', '{"a":"\\ud800"}'):
            with self.assertRaises((ValueError, UnicodeError)):
                parse_json(raw)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.folder.name) / "data")
        self.frontend = Path(self.folder.name) / "dist"
        self.frontend.mkdir()
        (self.frontend / "index.html").write_text("<h1>Ledger</h1>")
        self.server = LedgerServer(("127.0.0.1", 0), self.ledger, self.frontend)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.ledger.close()
        self.folder.cleanup()

    def request(self, method, path, value=None, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        body = raw if raw is not None else json.dumps(value).encode() if value is not None else None
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        status = response.status
        content_type = response.getheader("Content-Type")
        data = response.read()
        connection.close()
        if "application/json" in content_type:
            data = json.loads(data)
        return status, data

    def test_api_create_retry_conflict_and_verify(self):
        value = {"match_id": "api-one", "data": {"winner": 1}}
        status, result = self.request("POST", "/api/blocks", value)
        self.assertEqual(status, 201)
        self.assertFalse(result["duplicate"])
        self.assertEqual(self.request("POST", "/api/blocks", value)[0], 200)
        self.assertEqual(self.request("POST", "/api/blocks", {"match_id": "api-one", "data": {}})[0], 409)
        self.assertTrue(self.request("POST", "/api/verify", {})[1]["valid"])
        view = self.request("GET", "/api/ledger")[1]
        view["blocks"][1]["data"]["winner"] = 2
        self.assertFalse(self.request("POST", "/api/verify", {"blocks": view["blocks"]})[1]["valid"])
        self.assertTrue(self.request("GET", "/api/ledger")[1]["verification"]["valid"])
        self.assertEqual(self.request("GET", "/api/checkpoint")[1]["index"], 1)

    def test_bad_requests_and_browser_origin(self):
        for raw in (b'{"match_id":"x","match_id":"y","data":{}}', b'{"match_id":"x","data":{"x":1.5}}'):
            self.assertEqual(self.request("POST", "/api/blocks", raw=raw)[0], 400)
        self.assertEqual(self.request("POST", "/api/blocks", raw=b"x" * 65537)[0], 413)
        self.assertEqual(self.request("POST", "/api/verify", {}, {"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/verify", {}, {"Origin": "http://localhost:5173"})[0], 200)
        self.assertEqual(self.request("GET", "/api/ledger", headers={"Host": "evil.example"})[0], 403)

    def test_disk_corruption_and_static_path(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertEqual(self.request("GET", "/%2e%2e/secret")[0], 403)
        with self.ledger.path.open("ab") as file:
            file.write(b"bad\n")
        self.assertFalse(self.request("GET", "/api/ledger")[1]["verification"]["valid"])
        self.assertEqual(self.request("GET", "/api/checkpoint")[0], 409)
        self.assertEqual(self.request("POST", "/api/blocks", {"match_id": "x", "data": {}})[0], 409)


if __name__ == "__main__":
    unittest.main()
