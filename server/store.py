"""PostgreSQL registry and separate block/key tables for each ledger."""

import hashlib
import hmac
import secrets
import time
import uuid

import psycopg
from cryptography.fernet import Fernet
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from field_schema import validate_data, validate_fields
from ledger import (LedgerConflict, MAX_BODY_BYTES, calculate_hash, canonical_json,
                    create_genesis_block, create_new_block, validate_submission, verify_chain)


LEDGER_STATES = {"active", "read_only", "archived"}


class StoreNotFound(ValueError):
    pass


class StoreForbidden(ValueError):
    pass


def table_names(ledger_id):
    try:
        identifier = uuid.UUID(ledger_id)
    except (ValueError, TypeError, AttributeError):
        raise StoreNotFound("Ledger not found") from None
    if str(identifier) != ledger_id:
        raise StoreNotFound("Ledger not found")
    # Only a generated UUID enters a table name; labels never become SQL identifiers.
    prefix = "ledger_" + identifier.hex
    return prefix + "_blocks", prefix + "_secrets"


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ledger_genesis(ledger_id, fields):
    block = create_genesis_block()
    block["data"]["ledger_id"] = ledger_id
    block["data"]["fields"] = fields
    block["hash"] = calculate_hash(block)
    return block


def verify_ledger(blocks, metadata):
    try:
        fields = validate_fields(metadata["fields"])
        report = verify_chain(blocks, genesis=ledger_genesis(metadata["id"], fields))
    except (ValueError, TypeError, KeyError) as error:
        return {"valid": False, "checked_blocks": len(blocks),
                "errors": [{"index": 0, "message": "Invalid fixed ledger schema: " + str(error)}], "head_hash": None}
    for position, block in enumerate(blocks[1:], 1):
        try:
            validate_data(block["data"], fields)
        except (ValueError, TypeError, KeyError) as error:
            report["errors"].append({"index": position, "message": "Data schema: " + str(error)})
    report["valid"] = not report["errors"]
    return report


def validate_label(value, label, maximum, allow_empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
        raise ValueError(label + " must be text of at most " + str(maximum) + " characters")
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError(label + " contains unsupported control characters")
    return value.strip()


class Store:
    def __init__(self, database_url):
        self.database_url = database_url
        with self.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS ledger_registry (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('active', 'read_only', 'archived')),
                fields JSONB NOT NULL,
                created_at BIGINT NOT NULL,
                token_hash TEXT NOT NULL
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS ledger_owner_index ON ledger_registry (owner_id)")

    def connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5)

    def _metadata(self, connection, ledger_id, lock=False):
        table_names(ledger_id)
        query = "SELECT * FROM ledger_registry WHERE id = %s"
        query += " FOR UPDATE" if lock else " FOR SHARE"
        row = connection.execute(query, (ledger_id,)).fetchone()
        if row is None:
            raise StoreNotFound("Ledger not found")
        return row

    def _public(self, connection, row):
        blocks, _ = table_names(row["id"])
        count = connection.execute(sql.SQL("SELECT COUNT(*) AS count FROM {}").format(sql.Identifier(blocks))).fetchone()["count"]
        return {key: row[key] for key in ("id", "owner_id", "name", "description", "state", "fields", "created_at")} | {"block_count": count}

    def create_ledger(self, owner_id, name, description, fields):
        owner_id = validate_label(owner_id, "Owner ID", 128)
        name = validate_label(name, "Ledger name", 80)
        description = validate_label(description, "Description", 1000, True)
        fields = validate_fields(fields)
        ledger_id = str(uuid.uuid4())
        blocks, secret_table = table_names(ledger_id)
        write_token = secrets.token_urlsafe(32)
        genesis = ledger_genesis(ledger_id, fields)
        with self.connect() as connection:
            connection.execute("""INSERT INTO ledger_registry
                (id, owner_id, name, description, state, fields, created_at, token_hash)
                VALUES (%s, %s, %s, %s, 'active', %s, %s, %s)""",
                (ledger_id, owner_id, name, description, Jsonb(fields), time.time_ns() // 1000000, token_hash(write_token)))
            connection.execute(sql.SQL("""CREATE TABLE {} (
                position BIGINT PRIMARY KEY CHECK (position >= 0),
                match_id TEXT UNIQUE NOT NULL,
                record JSONB NOT NULL
            )""").format(sql.Identifier(blocks)))
            connection.execute(sql.SQL("""CREATE TABLE {} (
                singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
                snapshot_key TEXT NOT NULL
            )""").format(sql.Identifier(secret_table)))
            connection.execute(sql.SQL("INSERT INTO {} (position, match_id, record) VALUES (0, 'genesis', %s)")
                               .format(sql.Identifier(blocks)), (Jsonb(genesis),))
            connection.execute(sql.SQL("INSERT INTO {} (snapshot_key) VALUES (%s)").format(sql.Identifier(secret_table)),
                               (Fernet.generate_key().decode("ascii"),))
            metadata = self._public(connection, self._metadata(connection, ledger_id))
        return {"ledger": metadata, "write_token": write_token, "write_path": "/api/ledgers/" + ledger_id + "/blocks"}

    def list_ledgers(self, owner_id=None, admin=False):
        with self.connect() as connection:
            query = "SELECT * FROM ledger_registry"
            parameters = ()
            if owner_id is not None and not admin:
                query += " WHERE owner_id = %s"
                parameters = (owner_id,)
            # Share locks keep tables alive while counting, even during admin deletion.
            rows = connection.execute(query + " ORDER BY created_at, id FOR SHARE", parameters).fetchall()
            return [self._public(connection, row) for row in rows]

    def get_ledger(self, ledger_id):
        with self.connect() as connection:
            return self._public(connection, self._metadata(connection, ledger_id))

    def credentials(self, ledger_id, user_id, is_admin=False):
        metadata = self.get_ledger(ledger_id)
        if metadata["owner_id"] != user_id:
            raise StoreForbidden("Only the ledger creator can access its integration details")
        return {"ledger_id": ledger_id, "write_path": "/api/ledgers/" + ledger_id + "/blocks",
                "token_hint": "The secret is shown once at creation or rotation. Rotate it if lost."}

    def rotate_token(self, ledger_id, user_id):
        write_token = secrets.token_urlsafe(32)
        with self.connect() as connection:
            row = self._metadata(connection, ledger_id, lock=True)
            if row["owner_id"] != user_id:
                raise StoreForbidden("Only the ledger creator can rotate its write token")
            connection.execute("UPDATE ledger_registry SET token_hash = %s WHERE id = %s",
                               (token_hash(write_token), ledger_id))
        return {"ledger_id": ledger_id, "write_token": write_token, "write_path": "/api/ledgers/" + ledger_id + "/blocks"}

    def update_ledger(self, ledger_id, changes=None, **updates):
        changes = dict(changes or {}) | updates
        if not changes or set(changes) - {"name", "description", "state"}:
            raise ValueError("Only ledger name, description and state can be changed")
        if "name" in changes:
            changes["name"] = validate_label(changes["name"], "Ledger name", 80)
        if "description" in changes:
            changes["description"] = validate_label(changes["description"], "Description", 1000, True)
        if "state" in changes and (not isinstance(changes["state"], str) or changes["state"] not in LEDGER_STATES):
            raise ValueError("State must be active, read_only or archived")
        with self.connect() as connection:
            self._metadata(connection, ledger_id, lock=True)
            assignments = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(key)) for key in changes)
            connection.execute(sql.SQL("UPDATE ledger_registry SET {} WHERE id = %s").format(assignments),
                               (*changes.values(), ledger_id))
            return self._public(connection, self._metadata(connection, ledger_id))

    def delete_ledger(self, ledger_id):
        with self.connect() as connection:
            self._metadata(connection, ledger_id, lock=True)
            for name in table_names(ledger_id):
                connection.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(name)))
            connection.execute("DELETE FROM ledger_registry WHERE id = %s", (ledger_id,))

    def _blocks(self, connection, ledger_id):
        blocks, _ = table_names(ledger_id)
        rows = connection.execute(sql.SQL("SELECT record FROM {} ORDER BY position").format(sql.Identifier(blocks))).fetchall()
        return [row["record"] for row in rows]

    def read(self, ledger_id):
        with self.connect() as connection:
            row = self._metadata(connection, ledger_id)
            blocks = self._blocks(connection, ledger_id)
            metadata = self._public(connection, row)
            return {"ledger": metadata, "blocks": blocks, "verification": verify_ledger(blocks, row),
                    "updated_at_ms": time.time_ns() // 1000000}

    def get_snapshot_key(self, ledger_id):
        with self.connect() as connection:
            self._metadata(connection, ledger_id)
            _, secret_table = table_names(ledger_id)
            row = connection.execute(sql.SQL("SELECT snapshot_key FROM {} WHERE singleton = TRUE")
                                     .format(sql.Identifier(secret_table))).fetchone()
            if row is None:
                raise LedgerConflict("The ledger snapshot key is missing; restore it from a backup")
            return row["snapshot_key"].encode("ascii")

    def append(self, ledger_id, token, submission):
        validate_submission(submission)
        if len(canonical_json(submission)) > MAX_BODY_BYTES:
            raise ValueError("Submission is too large")
        with self.connect() as connection:
            row = self._metadata(connection, ledger_id, lock=True)
            if not isinstance(token, str) or not 20 <= len(token) <= 256 or not hmac.compare_digest(token_hash(token), row["token_hash"]):
                raise StoreForbidden("Invalid ledger write token")
            if row["state"] != "active":
                raise LedgerConflict("This ledger does not accept new blocks in its current state")
            validate_data(submission["data"], row["fields"])
            blocks = self._blocks(connection, ledger_id)
            if not verify_ledger(blocks, row)["valid"]:
                raise LedgerConflict("Ledger verification failed; no data was changed")
            for block in blocks:
                if block["match_id"] == submission["match_id"]:
                    if canonical_json(block["data"]) != canonical_json(submission["data"]):
                        raise LedgerConflict("This match_id already has different data")
                    return block, True
            block = create_new_block(blocks[-1], submission)
            block_table, _ = table_names(ledger_id)
            connection.execute(sql.SQL("INSERT INTO {} (position, match_id, record) VALUES (%s, %s, %s)")
                               .format(sql.Identifier(block_table)), (block["index"], block["match_id"], Jsonb(block)))
            return block, False
