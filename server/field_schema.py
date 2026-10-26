"""A ledger fixes its allowed data fields before its genesis block is created."""

import re

from ledger import validate_json


FIELD_TYPES = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list}
FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def reject_nul(value):
    # PostgreSQL JSONB cannot store NUL, even though JSON can escape it.
    if isinstance(value, str) and "\x00" in value:
        raise ValueError("NUL characters are not supported in stored strings or field names")
    if isinstance(value, dict):
        for key, item in value.items():
            reject_nul(key)
            reject_nul(item)
    elif isinstance(value, list):
        for item in value:
            reject_nul(item)


def validate_fields(fields):
    if not isinstance(fields, list) or not 1 <= len(fields) <= 32:
        raise ValueError("Choose between 1 and 32 data fields")
    result = []
    names = set()
    for field in fields:
        if not isinstance(field, dict) or not {"name", "type"} <= set(field) <= {"name", "type", "required"}:
            raise ValueError("Each field needs name, type and an optional required flag")
        name = field["name"]
        if not isinstance(name, str) or not FIELD_NAME.fullmatch(name) or name in names:
            raise ValueError("Field names must be unique identifiers of at most 64 characters")
        if not isinstance(field["type"], str) or field["type"] not in FIELD_TYPES:
            raise ValueError("Field type must be string, integer, boolean, object or array")
        required = field.get("required", True)
        if type(required) is not bool:
            raise ValueError("The required flag must be true or false")
        names.add(name)
        result.append({"name": name, "type": field["type"], "required": required})
    return result


def validate_data(data, fields):
    if not isinstance(data, dict):
        raise ValueError("Block data must be a JSON object")
    allowed = {field["name"] for field in fields}
    if set(data) - allowed:
        raise ValueError("Data contains fields outside this ledger's fixed structure")
    for field in fields:
        name = field["name"]
        if name not in data:
            if field["required"]:
                raise ValueError("Missing required field: " + name)
            continue
        # bool subclasses int in Python, but a boolean is not an integer field.
        if type(data[name]) is not FIELD_TYPES[field["type"]]:
            raise ValueError(name + " must have type " + field["type"])
    validate_json(data)
