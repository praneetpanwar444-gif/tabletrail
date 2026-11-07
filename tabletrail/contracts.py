"""Strict parsing prevents misspelled rules from silently passing validation."""

from dataclasses import dataclass, field
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

from .errors import TableTrailError

TYPES = {"string", "integer", "number", "boolean", "date"}
RULE_KEYS = {"type", "required", "unique", "min", "max", "enum", "pattern",
             "min_length", "max_length"}


def _unknown(data: dict, allowed: set, context: str) -> None:
    extra = set(data) - allowed
    if extra:
        raise TableTrailError(f"Unknown {context} option(s): {', '.join(sorted(extra))}")


def _bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise TableTrailError(f"{label} must be true or false")
    return value


def _number(value: Any, label: str) -> Decimal:
    if type(value) not in (int, float) or not Decimal(str(value)).is_finite():
        raise TableTrailError(f"{label} must be a finite JSON number")
    return Decimal(str(value))


@dataclass(frozen=True)
class ColumnRule:
    type: str = "string"
    required: bool = False
    unique: bool = False
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    enum: tuple[str, ...] | None = None
    pattern: re.Pattern | None = None
    min_length: int | None = None
    max_length: int | None = None


@dataclass(frozen=True)
class Contract:
    name: str
    columns: dict[str, ColumnRule] = field(default_factory=dict)
    allow_extra_columns: bool = False
    unique_rows: bool = False
    unique_keys: tuple[tuple[str, ...], ...] = ()
    null_values: tuple[str, ...] = ("",)

    @classmethod
    def from_dict(cls, data: dict) -> "Contract":
        if not isinstance(data, dict):
            raise TableTrailError("Contract must be a JSON object")
        _unknown(data, {"version", "name", "columns", "allow_extra_columns",
                        "unique_rows", "unique_keys", "null_values"}, "contract")
        if type(data.get("version")) is not int or data["version"] != 1:
            raise TableTrailError("Contract version must be 1")
        name = data.get("name", "Untitled contract")
        if not isinstance(name, str) or not name.strip():
            raise TableTrailError("Contract name must be a non-empty string")
        columns = data.get("columns")
        if not isinstance(columns, dict) or not columns:
            raise TableTrailError("Contract columns must be a non-empty object")
        parsed = {}
        for col, rule in columns.items():
            if not isinstance(col, str) or not col.strip() or not isinstance(rule, dict):
                raise TableTrailError("Every column needs a name and a rule object")
            _unknown(rule, RULE_KEYS, f"column {col!r}")
            kind = rule.get("type", "string")
            if not isinstance(kind, str) or kind not in TYPES:
                raise TableTrailError(f"Unsupported type for {col!r}: {kind!r}")
            bounds = {key: _number(rule[key], f"{col}.{key}")
                      for key in ("min", "max") if key in rule}
            if bounds and kind not in ("integer", "number"):
                raise TableTrailError(f"Numeric bounds need a numeric type: {col}")
            if "min" in bounds and "max" in bounds and bounds["min"] > bounds["max"]:
                raise TableTrailError(f"min cannot exceed max: {col}")
            lengths = {}
            for key in ("min_length", "max_length"):
                if key in rule:
                    value = rule[key]
                    if type(value) is not int or value < 0:
                        raise TableTrailError(f"{col}.{key} must be a non-negative integer")
                    lengths[key] = value
            if lengths.get("min_length", 0) > lengths.get("max_length", float("inf")):
                raise TableTrailError(f"min_length cannot exceed max_length: {col}")
            enum = rule.get("enum")
            if "enum" in rule and (not isinstance(enum, list) or not enum
                                    or any(not isinstance(v, str) for v in enum)):
                raise TableTrailError(f"{col}.enum must be a non-empty array of strings")
            pattern = None
            if "pattern" in rule:
                if not isinstance(rule["pattern"], str) or len(rule["pattern"]) > 512:
                    raise TableTrailError(f"{col}.pattern must be a string of at most 512 characters")
                try:
                    pattern = re.compile(rule["pattern"])
                except re.error as exc:
                    raise TableTrailError(f"Invalid pattern for {col}: {exc}") from exc
            parsed[col] = ColumnRule(
                type=kind, required=_bool(rule.get("required", False), f"{col}.required"),
                unique=_bool(rule.get("unique", False), f"{col}.unique"),
                minimum=bounds.get("min"), maximum=bounds.get("max"),
                enum=tuple(enum) if enum is not None else None, pattern=pattern, **lengths)
        keys = data.get("unique_keys", [])
        if not isinstance(keys, list):
            raise TableTrailError("unique_keys must be an array of column-name arrays")
        for key in keys:
            if (not isinstance(key, list) or not key
                    or any(not isinstance(c, str) or c not in parsed for c in key)
                    or len(set(key)) != len(key)):
                raise TableTrailError("Each unique key must contain distinct, declared columns")
        nulls = data.get("null_values", [""])
        if not isinstance(nulls, list) or any(not isinstance(v, str) for v in nulls):
            raise TableTrailError("null_values must be an array of strings")
        return cls(name, parsed,
                   _bool(data.get("allow_extra_columns", False), "allow_extra_columns"),
                   _bool(data.get("unique_rows", False), "unique_rows"),
                   tuple(tuple(k) for k in keys), tuple(nulls))


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise TableTrailError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_contract(path: str | Path) -> Contract:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs)
        return Contract.from_dict(data)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TableTrailError(f"Cannot read contract: {exc}") from exc
