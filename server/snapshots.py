"""Encrypted downloads are server-issued receipts, not editable imports."""

import base64
import binascii
import json
import os
import time

from cryptography.fernet import Fernet, InvalidToken

from ledger import LedgerConflict, canonical_json, reject_duplicate_keys, verify_block, verify_chain


MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
SNAPSHOT_FIELDS = {"format_version", "kind", "blocks", "exported_at_ms"}


class Snapshots:
    def __init__(self, ledger):
        self.ledger = ledger
        path = ledger.directory / "snapshot.key"
        # Ledger already holds the process writer lock. Never replace an old key.
        if not path.exists():
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as file:
                file.write(Fernet.generate_key())
                file.flush()
                os.fsync(file.fileno())
        self.cipher = Fernet(path.read_bytes())

    def export(self, block_index=None):
        with self.ledger.lock:
            blocks, report = self.ledger.read()
            if not report["valid"]:
                raise LedgerConflict("Cannot download an invalid ledger")
            kind = "chain"
            selected = blocks
            if block_index is not None:
                if type(block_index) is not int or not 0 <= block_index < len(blocks):
                    raise ValueError("Block index does not exist")
                kind = "block"
                selected = [blocks[block_index]]
            payload = {"format_version": 1, "kind": kind, "blocks": selected,
                       "exported_at_ms": time.time_ns() // 1000000}
            # Blocks were checked individually; the envelope must not reduce their nesting allowance.
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            # Fernet expands data to base64 plus fixed authentication overhead.
            estimated_size = 4 * ((57 + (len(raw) // 16 + 1) * 16 + 2) // 3)
            if estimated_size > MAX_SNAPSHOT_BYTES:
                raise OverflowError("Snapshot exceeds 8 MiB; download individual blocks")
            token = self.cipher.encrypt(raw)
            return token, selected[-1]["index"]

    def validate(self, token):
        if not token or len(token) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Snapshot must contain at most 8 MiB")
        try:
            decoded = base64.b64decode(token, altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(decoded) != token:
                raise ValueError("Snapshot encoding is not canonical")
        except (ValueError, binascii.Error):
            raise ValueError("Snapshot encoding is invalid") from None
        try:
            # Authenticate before parsing. No expiry: old receipts remain useful.
            value = json.loads(self.cipher.decrypt(token), object_pairs_hook=reject_duplicate_keys)
        except InvalidToken:
            raise ValueError("File was changed, is invalid, or belongs to another server key") from None
        if not isinstance(value, dict) or set(value) != SNAPSHOT_FIELDS:
            raise ValueError("Invalid snapshot fields")
        if type(value["format_version"]) is not int or value["format_version"] != 1:
            raise ValueError("Unsupported snapshot format")
        if type(value["exported_at_ms"]) is not int or value["exported_at_ms"] < 0:
            raise ValueError("Invalid snapshot timestamp")
        kind = value["kind"]
        saved = value["blocks"]
        if kind not in ("chain", "block") or not isinstance(saved, list) or not saved:
            raise ValueError("Invalid snapshot contents")
        if kind == "chain":
            report = verify_chain(saved)
            if not report["valid"]:
                raise ValueError("Downloaded chain is invalid: " + report["errors"][0]["message"])
        else:
            if len(saved) != 1:
                raise ValueError("A block snapshot must contain exactly one block")
            verify_block(saved[0])

        with self.ledger.lock:
            current, report = self.ledger.read()
            errors = list(report["errors"])
            if not errors:
                for block in saved:
                    index = block["index"]
                    if index >= len(current):
                        errors.append({"index": index, "message": "Downloaded block is missing from the server"})
                    elif canonical_json(block) != canonical_json(current[index]):
                        errors.append({"index": index, "message": "Downloaded block differs from server history"})
            new_blocks = 0
            if not errors:
                new_blocks = max(0, len(current) - saved[-1]["index"] - 1)
            message = "Downloaded records match the current server history"
            if errors:
                message = "Verification failed; no records were changed"
            return {"valid": not errors, "kind": kind, "checked_blocks": len(saved),
                    "server_blocks": len(current), "new_blocks": new_blocks,
                    "errors": errors, "message": message}
