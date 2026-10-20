"""Run with python server/app.py. Only the standard library is required."""

import argparse
import json
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ledger import Ledger, LedgerConflict, MAX_BODY_BYTES, parse_json, read_existing_ledger, verify_chain


class LedgerServer(ThreadingHTTPServer):
    # Finish active requests before releasing the writer lock on shutdown.
    daemon_threads = False

    def __init__(self, address, ledger, frontend):
        self.ledger = ledger
        self.frontend = Path(frontend).resolve()
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
        # Local-only browser access prevents another website writing to localhost.
        host = self.headers.get("Host", "")
        try:
            hostname = urlsplit("http://" + host).hostname
        except ValueError:
            return False
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # Command-line integrations need no browser Origin header.
        try:
            parsed = urlsplit(origin)
            allowed_ports = (5173, self.server.server_port)
            return (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
                    and parsed.port in allowed_ports and not parsed.username and not parsed.path)
        except ValueError:
            return False

    def read_body(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Transfer-Encoding is not supported")
        content_lengths = self.headers.get_all("Content-Length", [])
        if len(content_lengths) != 1:
            raise ValueError("Exactly one Content-Length header is required")
        try:
            length = int(content_lengths[0])
        except ValueError:
            raise ValueError("Invalid Content-Length")
        if length < 0 or length > MAX_BODY_BYTES:
            raise OverflowError("Request body exceeds 64 KiB")
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("Incomplete request body")
        return parse_json(body)

    def do_POST(self):
        if not self.local_request():
            self.send_json(403, {"error": "Only local hosts and approved browser origins are allowed"})
            return
        try:
            value = self.read_body()
            path = urlsplit(self.path).path
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
            self.send_json(403, {"error": "Only local hosts and approved browser origins are allowed"})
            return
        path = urlsplit(self.path).path
        if path == "/api/ledger":
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


def main():
    parser = argparse.ArgumentParser(description="Local match-result ledger and viewer API")
    parser.add_argument("--port", type=int, default=8000)
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
        frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist"
        server = LedgerServer(("127.0.0.1", args.port), ledger, frontend)
        print("Ledger server: http://127.0.0.1:" + str(server.server_port), flush=True)
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
