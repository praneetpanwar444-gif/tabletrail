"""One-pass profiling and data-contract validation."""

from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from .contracts import ColumnRule, Contract
from .errors import TableTrailError
from .reader import read_table
from .storage import Counts

INTEGER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)\Z")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def decimal_value(value: str) -> Decimal | None:
    if len(value) > 1024 or not NUMBER.fullmatch(value):
        return None
    try:
        result = Decimal(value)
        if result.is_finite() and (result.is_zero() or abs(result.adjusted()) <= 1000):
            return result
    except InvalidOperation:
        pass
    return None


def is_type(value: str, kind: str) -> bool:
    if kind == "string":
        return True
    if kind == "integer":
        return bool(INTEGER.fullmatch(value)) and decimal_value(value) is not None
    if kind == "number":
        return decimal_value(value) is not None
    if kind == "boolean":
        return value.lower() in ("true", "false")
    if kind == "date":
        try:
            return bool(DATE.fullmatch(value)) and bool(date.fromisoformat(value))
        except ValueError:
            return False
    return False


def classify(value: str) -> str:
    if is_type(value, "integer"):
        return "integer"
    # Preserve zero-padded identifiers rather than inferring them as numbers.
    unsigned = value.lstrip("+-")
    if len(unsigned) > 1 and unsigned[0] == "0" and unsigned[1].isdigit():
        return "string"
    for kind in ("number", "boolean", "date"):
        if is_type(value, kind):
            return kind
    return "string"


def violations(value: str, rule: ColumnRule):
    if not is_type(value, rule.type):
        yield "type", f"Expected {rule.type}"
        return
    if rule.minimum is not None and Decimal(value) < rule.minimum:
        yield "min", f"Must be at least {rule.minimum}"
    if rule.maximum is not None and Decimal(value) > rule.maximum:
        yield "max", f"Must be at most {rule.maximum}"
    if rule.enum is not None and value not in rule.enum:
        yield "enum", "Value is outside the allowed set"
    if rule.pattern is not None and rule.pattern.fullmatch(value) is None:
        yield "pattern", "Value does not fully match the required pattern"
    if rule.min_length is not None and len(value) < rule.min_length:
        yield "min_length", f"Needs at least {rule.min_length} characters"
    if rule.max_length is not None and len(value) > rule.max_length:
        yield "max_length", f"Allows at most {rule.max_length} characters"


def analyze(path: str | Path, contract: Contract | None = None, *, delimiter=",",
            encoding="utf-8-sig", max_issues: int = 200) -> dict:
    """Return a JSON-compatible report. Inputs are never modified.

    Only issue examples are capped; total issues and failed records remain exact.
    Missing values are whitespace-trimmed before comparison with null_values.
    Uniqueness is lexical after trimming; nulls are excluded from unique checks.
    """
    if type(max_issues) is not int or not 0 <= max_issues <= 10000:
        raise TableTrailError("max_issues must be between 0 and 10000")
    issues, issue_counts = [], Counter()
    total_issues = failed_records = row_count = duplicate_rows = 0
    nulls = set(contract.null_values if contract else ("",))

    def issue(record, line, column, code, message, value=None):
        nonlocal total_issues
        total_issues += 1
        issue_counts[code] += 1
        if len(issues) < max_issues:
            issues.append({"record": record, "line": line, "column": column,
                           "code": code, "message": message,
                           "value": value[:160] if value is not None else None})

    with read_table(path, delimiter, encoding) as (headers, rows), Counts() as counts:
        stats = [{"name": h, "null_count": 0, "types": Counter(), "numeric_count": 0,
                  "sum": Decimal(0), "min": None, "max": None} for h in headers]
        if contract:
            for name in contract.columns:
                if name not in headers:
                    issue(None, None, name, "missing_column", "Contract column is missing")
            if not contract.allow_extra_columns:
                for name in headers:
                    if name not in contract.columns:
                        issue(None, None, name, "extra_column", "Column is not declared in contract")
        keys = [key for key in (contract.unique_keys if contract else ())
                if all(c in headers for c in key)]
        indices = {name: i for i, name in enumerate(headers)}
        for row in rows:
            row_count += 1
            before = total_issues
            values = [v.strip() for v in row.cells]
            first = counts.add("rows", values, row.record)
            if first is not None:
                duplicate_rows += 1
                if contract and contract.unique_rows:
                    issue(row.record, row.line, None, "duplicate_row", f"Same values as record {first}")
            for i, (name, value) in enumerate(zip(headers, values)):
                col = stats[i]
                rule = contract.columns.get(name) if contract else None
                if value in nulls:
                    col["null_count"] += 1
                    if rule and rule.required:
                        issue(row.record, row.line, name, "required", "Value must not be missing", value)
                    continue
                col["types"][classify(value)] += 1
                first = counts.add(f"column:{i}", value, row.record)
                numeric = decimal_value(value)
                if numeric is not None:
                    col["numeric_count"] += 1
                    col["sum"] += numeric
                    col["min"] = numeric if col["min"] is None else min(col["min"], numeric)
                    col["max"] = numeric if col["max"] is None else max(col["max"], numeric)
                if rule:
                    for code, message in violations(value, rule):
                        issue(row.record, row.line, name, code, message, value)
                    if rule.unique and first is not None:
                        issue(row.record, row.line, name, "unique", f"Already used in record {first}", value)
            for key in keys:
                parts = [values[indices[c]] for c in key]
                if any(p in nulls for p in parts):
                    continue
                first = counts.add("key:" + str(key), parts, row.record)
                if first is not None:
                    issue(row.record, row.line, ", ".join(key), "unique_key",
                          f"Composite key already used in record {first}")
            if total_issues > before:
                failed_records += 1
        columns = []
        for i, col in enumerate(stats):
            kinds = set(col["types"])
            inferred = ("empty" if not kinds else "number" if kinds == {"integer", "number"}
                        else next(iter(kinds)) if len(kinds) == 1 else "mixed")
            distinct, top = counts.summary(f"column:{i}")
            n = col["numeric_count"]
            columns.append({"name": col["name"], "inferred_type": inferred,
                            "null_count": col["null_count"],
                            "null_rate": col["null_count"] / row_count if row_count else 0,
                            "distinct_count": distinct, "type_counts": dict(sorted(col["types"].items())),
                            "top_values": top, "numeric_count": n,
                            "numeric_min": str(col["min"]) if n else None,
                            "numeric_max": str(col["max"]) if n else None,
                            "numeric_mean": str(col["sum"] / n) if n else None})
    return {"report_version": 1, "kind": "validation" if contract else "profile",
            "source": Path(path).name, "contract": contract.name if contract else None,
            "rows": row_count, "column_count": len(headers), "duplicate_rows": duplicate_rows,
            "columns": columns, "status": "fail" if total_issues else "pass",
            "failed_records": failed_records, "issue_count": total_issues,
            "issue_counts": dict(sorted(issue_counts.items())), "issues": issues,
            "omitted_issues": total_issues - len(issues)}
