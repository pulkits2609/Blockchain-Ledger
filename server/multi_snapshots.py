"""Ledger-specific encrypted receipts and visible per-block comparisons."""

import base64
import binascii
import json
import time

from cryptography.fernet import Fernet, InvalidToken

from field_schema import validate_data
from ledger import LedgerConflict, canonical_json, reject_duplicate_keys, verify_block
from snapshots import MAX_SNAPSHOT_BYTES
from store import ledger_genesis, verify_ledger


SNAPSHOT_FIELDS = {"format_version", "ledger_id", "kind", "blocks", "exported_at_ms"}


class SnapshotService:
    def __init__(self, store, ledger_id):
        self.store = store
        self.ledger_id = ledger_id

    def cipher(self):
        # Keys belong to individual ledgers. They never enter public metadata or receipts.
        return Fernet(self.store.get_snapshot_key(self.ledger_id))

    def export(self, block_index=None):
        view = self.store.read(self.ledger_id)
        if not view["verification"]["valid"]:
            raise LedgerConflict("Cannot download an invalid ledger")
        blocks = view["blocks"]
        selected = blocks
        kind = "chain"
        if block_index is not None:
            if type(block_index) is not int or not 0 <= block_index < len(blocks):
                raise ValueError("Block index does not exist")
            selected = [blocks[block_index]]
            kind = "block"
        payload = {"format_version": 2, "ledger_id": self.ledger_id, "kind": kind,
                   "blocks": selected, "exported_at_ms": time.time_ns() // 1000000}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        estimated_size = 4 * ((57 + (len(raw) // 16 + 1) * 16 + 2) // 3)
        if estimated_size > MAX_SNAPSHOT_BYTES:
            raise OverflowError("Snapshot exceeds 8 MiB; download individual blocks")
        return self.cipher().encrypt(raw), selected[-1]["index"]

    def decode(self, token):
        if not token or len(token) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Snapshot must contain at most 8 MiB")
        try:
            decoded = base64.b64decode(token, altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(decoded) != token:
                raise ValueError("Snapshot encoding is not canonical")
        except (ValueError, binascii.Error):
            raise ValueError("Snapshot encoding is invalid") from None
        try:
            value = json.loads(self.cipher().decrypt(token), object_pairs_hook=reject_duplicate_keys)
        except InvalidToken:
            # Authentication failure cannot identify which block a changed encrypted file contained.
            raise ValueError("File could not be authenticated: it was changed or belongs to another ledger. No block can be marked verified.") from None
        except (UnicodeError, RecursionError):
            raise ValueError("Snapshot contents could not be decoded") from None
        if not isinstance(value, dict) or set(value) != SNAPSHOT_FIELDS:
            raise ValueError("Invalid snapshot fields")
        if type(value["format_version"]) is not int or value["format_version"] != 2:
            raise ValueError("Unsupported snapshot format")
        if value["ledger_id"] != self.ledger_id:
            raise ValueError("This snapshot belongs to another ledger")
        if type(value["exported_at_ms"]) is not int or value["exported_at_ms"] < 0:
            raise ValueError("Invalid snapshot timestamp")
        if value["kind"] not in ("chain", "block") or not isinstance(value["blocks"], list) or not value["blocks"]:
            raise ValueError("Invalid snapshot contents")
        return value

    def validate(self, token):
        snapshot = self.decode(token)
        saved = snapshot["blocks"]
        view = self.store.read(self.ledger_id)
        metadata = view["ledger"]
        if snapshot["kind"] == "chain":
            report = verify_ledger(saved, metadata)
            if not report["valid"]:
                raise ValueError("Downloaded chain is invalid: " + report["errors"][0]["message"])
        else:
            if len(saved) != 1:
                raise ValueError("A block snapshot must contain exactly one block")
            verify_block(saved[0])
            if saved[0]["index"] == 0:
                if saved[0] != ledger_genesis(self.ledger_id, metadata["fields"]):
                    raise ValueError("Downloaded genesis does not match this ledger")
            else:
                validate_data(saved[0]["data"], metadata["fields"])

        current = view["blocks"]
        # A missing middle row shifts list positions, but does not renumber later blocks.
        current_by_index = {}
        position_indices = []
        duplicates = set()
        errors = []
        for position, block in enumerate(current):
            index = block.get("index") if isinstance(block, dict) else None
            if type(index) is not int or not 0 <= index <= 9007199254740991:
                position_indices.append(None)
                errors.append({"index": None, "message": "Stored position " + str(position) + " has no usable block index."})
                continue
            position_indices.append(index)
            if index in current_by_index:
                duplicates.add(index)
            else:
                current_by_index[index] = block
        # The chain verifier reports positions; the viewer labels cards by their stored index.
        for error in view["verification"]["errors"]:
            position = error["index"]
            index = None
            message = error["message"]
            if type(position) is int and 0 <= position < len(position_indices):
                index = position_indices[position]
                message = "Stored position " + str(position) + ": " + message
            errors.append({"index": index, "message": message})
        for index in duplicates:
            errors.append({"index": index, "message": "More than one current record claims this block index."})
        saved_by_index = {block["index"]: block for block in saved}
        statuses = []
        findings = {}
        for error in errors:
            findings.setdefault(error["index"], []).append(error["message"])
        for index, block in current_by_index.items():
            status = "not_in_snapshot"
            message = "This block is not present in the downloaded snapshot; it has not been verified by this file."
            if index in saved_by_index:
                try:
                    matches = canonical_json(saved_by_index[index]) == canonical_json(block)
                except (ValueError, TypeError, UnicodeError):
                    matches = False
                if matches:
                    status = "verified"
                    message = "The snapshot contains the same block data, hash and previous-hash link."
                else:
                    status = "changed"
                    message = "This block differs from the authenticated snapshot."
                    errors.append({"index": index, "message": message})
            if index in findings:
                status = "changed"
                message = "Current ledger verification failed: " + "; ".join(findings[index])
            statuses.append({"index": index, "status": status, "message": message})
        for index in sorted(set(saved_by_index) - set(current_by_index)):
            message = "No current block with this saved index could be identified; it is missing or its index was changed."
            errors.append({"index": index, "message": message})
            statuses.append({"index": index, "status": "changed", "message": message})
        statuses.sort(key=lambda entry: entry["index"])
        valid = not errors
        return {"valid": valid, "kind": snapshot["kind"], "ledger_id": self.ledger_id,
                "checked_blocks": len(saved), "server_blocks": len(current),
                "new_blocks": sum(index > saved[-1]["index"] for index in current_by_index),
                "errors": errors, "block_statuses": statuses, "snapshot_blocks": saved,
                "compared_head": view["verification"]["head_hash"],
                "message": "Downloaded records match the current ledger." if valid
                    else "Verification found changed or missing records. No records were changed by this check."}
