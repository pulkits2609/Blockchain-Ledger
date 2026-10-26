"""Small, single-writer JSON Lines ledger. SHA-256 detects changes, not authorship."""

import hashlib
import json
import os
import threading
import time
from pathlib import Path


SCHEMA_VERSION = 2
ZERO_HASH = "0" * 64
MAX_BODY_BYTES = 65536
MAX_DEPTH = 20
BLOCK_FIELDS = {"schema_version", "index", "record_id", "timestamp_ms", "data", "previous_hash", "hash"}


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def validate_json(value, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError("JSON nesting is too deep")
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str):
            value.encode("utf-8")  # Reject unpaired Unicode surrogates.
        return
    if type(value) is int:
        if abs(value) > 9007199254740991:
            raise ValueError("Integers must fit the browser's safe integer range")
        return
    if isinstance(value, list):
        for item in value:
            validate_json(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Object keys must be strings")
            key.encode("utf-8")
            validate_json(item, depth + 1)
        return
    raise ValueError("Only integers, strings, booleans, null, arrays and objects are supported")


def parse_json(raw):
    def reject_constant(value):
        raise ValueError("Invalid JSON number: " + value)

    value = json.loads(raw, object_pairs_hook=reject_duplicate_keys, parse_constant=reject_constant)
    validate_json(value)
    return value


def canonical_json(value):
    validate_json(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def calculate_hash(block):
    contents = {key: value for key, value in block.items() if key != "hash"}
    return hashlib.sha256(canonical_json(contents)).hexdigest()


def create_genesis_block():
    block = {"schema_version": SCHEMA_VERSION, "index": 0, "record_id": "genesis", "timestamp_ms": 0,
             "data": {"application": "blockchainLedger", "message": "Genesis Block"}, "previous_hash": ZERO_HASH}
    block["hash"] = calculate_hash(block)
    return block


def validate_submission(value):
    if not isinstance(value, dict) or set(value) != {"record_id", "data"}:
        raise ValueError("Expected exactly record_id and data")
    record_id = value["record_id"]
    if not isinstance(record_id, str) or not record_id.strip() or len(record_id) > 128:
        raise ValueError("record_id must be a nonempty string of at most 128 characters")
    if record_id == "genesis":
        raise ValueError("The record_id genesis is reserved")
    if not isinstance(value["data"], dict):
        raise ValueError("data must be a JSON object")
    validate_json(value)


def create_new_block(previous_block, submission):
    validate_submission(submission)
    block = {"schema_version": SCHEMA_VERSION, "index": previous_block["index"] + 1,
             "record_id": submission["record_id"], "timestamp_ms": time.time_ns() // 1000000,
             "data": submission["data"], "previous_hash": previous_block["hash"]}
    block["hash"] = calculate_hash(block)
    return block


def is_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def verify_block(block):
    if not isinstance(block, dict) or set(block) != BLOCK_FIELDS:
        raise ValueError("Block fields do not match schema version 2")
    for field in ("schema_version", "index", "timestamp_ms"):
        if type(block[field]) is not int or block[field] < 0:
            raise ValueError(field + " must be a nonnegative integer")
    if block["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported schema version")
    if not isinstance(block["record_id"], str) or not block["record_id"].strip() or len(block["record_id"]) > 128:
        raise ValueError("Invalid record_id")
    if not isinstance(block["data"], dict):
        raise ValueError("Block data must be an object")
    if not is_hash(block["previous_hash"]) or not is_hash(block["hash"]):
        raise ValueError("Hashes must contain 64 lowercase hexadecimal characters")
    if calculate_hash(block) != block["hash"]:
        raise ValueError("Stored hash does not match recalculated hash")
    return True


def verify_chain(blocks, initial_errors=None, genesis=None):
    errors = list(initial_errors or [])
    seen_ids = set()
    if not blocks:
        errors.append({"index": None, "message": "Ledger has no genesis block"})
    for index, block in enumerate(blocks):
        try:
            verify_block(block)
            if block["index"] != index:
                raise ValueError("Block index does not match its position")
            if index == 0 and block != (genesis if genesis is not None else create_genesis_block()):
                raise ValueError("Genesis does not match the prescribed genesis block")
            if block["record_id"] in seen_ids:
                raise ValueError("Duplicate record_id")
            seen_ids.add(block["record_id"])
            if index > 0:
                previous = blocks[index - 1]
                if not isinstance(previous, dict) or block["previous_hash"] != previous.get("hash"):
                    raise ValueError("Previous hash does not match preceding block")
        except (ValueError, TypeError, UnicodeError) as error:
            errors.append({"index": index, "message": str(error)})
    head_hash = None
    if blocks and isinstance(blocks[-1], dict) and is_hash(blocks[-1].get("hash")):
        head_hash = blocks[-1]["hash"]
    return {"valid": not errors, "checked_blocks": len(blocks), "errors": errors, "head_hash": head_hash}


def read_existing_ledger(path):
    blocks = []
    errors = []
    try:
        with Path(path).open("rb") as file:
            for index, line in enumerate(file):
                if len(line) > MAX_BODY_BYTES + 2048:
                    errors.append({"index": index, "message": "Record exceeds maximum size"})
                if not line.endswith(b"\n"):
                    errors.append({"index": index, "message": "Incomplete final record: missing newline"})
                try:
                    blocks.append(parse_json(line))
                except (ValueError, UnicodeError, RecursionError) as error:
                    errors.append({"index": index, "message": "Invalid JSON record: " + str(error)})
                    blocks.append(None)
    except OSError as error:
        errors.append({"index": None, "message": "Cannot read ledger: " + str(error)})
    return blocks, verify_chain(blocks, errors)


class LedgerConflict(ValueError):
    pass


class Ledger:
    def __init__(self, data_dir):
        self.directory = Path(data_dir).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "chain.jsonl"
        self.lock = threading.RLock()
        self.process_lock = open(self.directory / "writer.lock", "a+b")
        try:
            self.acquire_process_lock()
            if not self.path.exists():
                # Exclusive creation avoids replacing an existing ledger.
                with self.path.open("xb") as file:
                    file.write(canonical_json(create_genesis_block()) + b"\n")
                    file.flush()
                    os.fsync(file.fileno())
        except Exception:
            self.process_lock.close()
            raise

    def acquire_process_lock(self):
        if os.name == "nt":
            import msvcrt
            self.process_lock.seek(0)
            if not self.process_lock.read(1):
                self.process_lock.write(b"0")
                self.process_lock.flush()
            self.process_lock.seek(0)
            msvcrt.locking(self.process_lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def close(self):
        self.process_lock.close()

    def read(self):
        return read_existing_ledger(self.path)

    def view(self):
        with self.lock:
            blocks, verification = self.read()
            return {"blocks": blocks, "verification": verification,
                    "storage": {"file": str(self.path)}, "updated_at_ms": time.time_ns() // 1000000}

    def append_record(self, submission):
        validate_submission(submission)
        if len(canonical_json(submission)) > MAX_BODY_BYTES:
            raise ValueError("Submission is too large")
        with self.lock:
            blocks, verification = self.read()
            if not verification["valid"]:
                raise LedgerConflict("Ledger verification failed; no data was changed")
            for block in blocks:
                if block["record_id"] == submission["record_id"]:
                    if canonical_json(block["data"]) != canonical_json(submission["data"]):
                        raise LedgerConflict("This record_id already has different data")
                    return block, True
            block = create_new_block(blocks[-1], submission)
            with self.path.open("ab") as file:
                file.write(canonical_json(block) + b"\n")
                file.flush()
                os.fsync(file.fileno())
            return block, False
