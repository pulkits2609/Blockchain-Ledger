"""Run with python server/app.py after installing server/requirements.txt."""

import argparse
import json
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from ledger import Ledger, LedgerConflict, MAX_BODY_BYTES, parse_json, read_existing_ledger, verify_chain
from snapshots import MAX_SNAPSHOT_BYTES, Snapshots


class LedgerServer(ThreadingHTTPServer):
    # Finish active requests before releasing the writer lock on shutdown.
    daemon_threads = False

    def __init__(self, address, ledger, frontend, allowed_hosts=None):
        self.ledger = ledger
        self.frontend = Path(frontend).resolve()
        self.allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        self.allowed_hosts.update(host.lower() for host in (allowed_hosts or []))
        if address[0] not in ("0.0.0.0", "::"):
            self.allowed_hosts.add(address[0].lower())
        self.snapshots = Snapshots(ledger)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def send_json(self, status, value):
        data = json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def local_request(self):
        # Explicit host names preserve DNS-rebinding protection when serving LAN clients.
        try:
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1:
                return False
            host = urlsplit("http://" + hosts[0])
            if host.path or host.query or host.fragment:
                return False
            if host.hostname not in self.server.allowed_hosts or host.username or host.password:
                return False
            host_port = host.port
            if host_port is None:
                host_port = 80
            if host_port != self.server.server_port:
                return False
            origin = self.headers.get("Origin")
            if origin is None:
                return True  # Native GFX and command-line requests have no browser Origin.
            parsed = urlsplit(origin)
            if parsed.scheme != "http" or parsed.username or parsed.password:
                return False
            if parsed.path or parsed.query or parsed.fragment:
                return False
            origin_port = parsed.port
            if origin_port is None:
                origin_port = 80
            same_server = parsed.hostname == host.hostname and origin_port == self.server.server_port
            local_development = parsed.hostname in ("localhost", "127.0.0.1", "::1") and parsed.port == 5173
            return same_server or local_development
        except ValueError:
            return False

    def read_body(self, maximum=MAX_BODY_BYTES, content_type="application/json"):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Transfer-Encoding is not supported")
        content_lengths = self.headers.get_all("Content-Length", [])
        if len(content_lengths) != 1:
            raise ValueError("Exactly one Content-Length header is required")
        try:
            length = int(content_lengths[0])
        except ValueError:
            raise ValueError("Invalid Content-Length")
        if length < 0 or length > maximum:
            raise OverflowError("Request body exceeds the allowed size")
        if self.headers.get_content_type() != content_type:
            raise ValueError("Content-Type must be " + content_type)
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("Incomplete request body")
        if content_type == "application/json":
            return parse_json(body)
        return body

    def do_POST(self):
        if not self.local_request():
            self.send_json(403, {"error": "Only approved hosts and browser origins are allowed"})
            return
        try:
            path = urlsplit(self.path).path
            if path == "/api/validate-snapshot":
                try:
                    token = self.read_body(MAX_SNAPSHOT_BYTES, "application/octet-stream")
                except OverflowError as error:
                    raise ValueError(str(error)) from None
                self.send_json(200, self.server.snapshots.validate(token))
                return
            value = self.read_body()
            if path == "/api/blocks":
                block, duplicate = self.server.ledger.append_result(value)
                self.send_json(200 if duplicate else 201, {"block": block, "duplicate": duplicate})
            elif path == "/api/verify":
                if value == {}:
                    verification = self.server.ledger.view()["verification"]
                elif isinstance(value, dict) and set(value) == {"blocks"} and isinstance(value["blocks"], list):
                    verification = verify_chain(value["blocks"])
                else:
                    raise ValueError("Expected {} or an object containing a blocks array")
                self.send_json(200, verification)
            else:
                self.send_json(404, {"error": "API route not found"})
        except LedgerConflict as error:
            self.send_json(409, {"error": str(error)})
        except OverflowError as error:
            self.send_json(413, {"error": str(error)})
        except (ValueError, UnicodeError, RecursionError) as error:
            self.send_json(400, {"error": str(error)})
        except (socket.timeout, TimeoutError):
            self.send_json(408, {"error": "Request body timed out"})
        except OSError as error:
            self.log_message("Storage operation failed: %s", error)
            self.send_json(503, {"error": "Storage operation failed; inspect and verify the ledger before retrying"})

    def do_GET(self):
        if not self.local_request():
            self.send_json(403, {"error": "Only approved hosts and browser origins are allowed"})
            return
        path = urlsplit(self.path).path
        if path == "/api/snapshot":
            try:
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                block_index = None
                if query:
                    if set(query) != {"block"} or len(query["block"]) != 1:
                        raise ValueError("Expected one block index")
                    text = query["block"][0]
                    if not text.isascii() or not text.isdecimal():
                        raise ValueError("Block index must be a nonnegative integer")
                    block_index = int(text)
                token, index = self.server.snapshots.export(block_index)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(token)))
                self.send_header("Content-Disposition", 'attachment; filename="ledger-' + str(index) + '.ledger"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(token)
            except LedgerConflict as error:
                self.send_json(409, {"error": str(error)})
            except (ValueError, OverflowError) as error:
                self.send_json(400, {"error": str(error)})
            except OSError:
                self.send_json(503, {"error": "Storage operation failed"})
        elif path == "/api/ledger":
            self.send_json(200, self.server.ledger.view())
        elif path == "/api/checkpoint":
            view = self.server.ledger.view()
            if not view["verification"]["valid"]:
                self.send_json(409, {"error": "Cannot export checkpoint from an invalid ledger"})
            else:
                head = view["blocks"][-1]
                self.send_json(200, {"schema_version": 1, "index": head["index"], "hash": head["hash"]})
        elif path.startswith("/api/"):
            self.send_json(404, {"error": "API route not found"})
        else:
            self.serve_frontend(path)

    def serve_frontend(self, path):
        root = self.server.frontend
        target = (root / unquote(path).lstrip("/")).resolve()
        if not target.is_relative_to(root):
            self.send_json(403, {"error": "Invalid file path"})
            return
        if target.is_dir():
            target = (target / "index.html").resolve()
        if not target.is_relative_to(root):
            self.send_json(403, {"error": "Invalid file path"})
            return
        if not target.is_file():
            self.send_json(404, {"error": "Frontend not built. Run the React development server or build frontend/dist."})
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)


def seed_demo(ledger):
    """Opt-in examples use stable IDs, so restarting never duplicates the matches."""
    for number in range(1, 5):
        ledger.append_result({"match_id": "DEMO-MATCH-" + str(number).zfill(3),
                              "data": {"demo": True, "label": "Demo match " + str(number),
                                       "duration_seconds": 180, "winning_team": 1,
                                       "team_scores": [number + 3, number + 2],
                                       "players": [{"name": "Player 1", "team": 1, "kills": number + 3, "deaths": number + 2},
                                                   {"name": "Player 2", "team": 2, "kills": number + 2, "deaths": number + 3}]}})


def main():
    parser = argparse.ArgumentParser(description="Local match-result ledger and viewer API")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind", default="127.0.0.1", help="Listening IP; use 0.0.0.0 for trusted LAN access")
    parser.add_argument("--allow-host", action="append", default=[], help="Explicit remote-facing hostname or IP; repeat if needed")
    parser.add_argument("--seed-demo", action="store_true", help="Append four labelled test matches without replacing records")
    parser.add_argument("--data-dir", default=str(Path(__file__).parent / "data"))
    parser.add_argument("--verify", action="store_true", help="Verify saved records and exit without starting HTTP")
    args = parser.parse_args()
    if args.verify:
        # Independent verification must never initialize or repair stored data.
        _, report = read_existing_ledger(Path(args.data_dir) / "chain.jsonl")
        print(json.dumps(report, indent=2))
        return 0 if report["valid"] else 1
    ledger = Ledger(args.data_dir)
    try:
        if args.seed_demo:
            seed_demo(ledger)
        frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist"
        server = LedgerServer((args.bind, args.port), ledger, frontend, args.allow_host)
        print("Ledger server: http://" + args.bind + ":" + str(server.server_port), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    finally:
        ledger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
