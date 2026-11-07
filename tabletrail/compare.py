"""Compare independently profiled files using explicit, inspectable thresholds."""

from decimal import Decimal
from fractions import Fraction
import math

from .engine import analyze
from .errors import TableTrailError


def compare(baseline, current, *, null_threshold=0.05, mean_threshold=0.25,
            row_threshold=0.5, delimiter=",", encoding="utf-8-sig") -> dict:
    for label, value in (("null", null_threshold), ("mean", mean_threshold), ("row", row_threshold)):
        if isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise TableTrailError(f"{label} threshold must be finite and non-negative")
    old = analyze(baseline, delimiter=delimiter, encoding=encoding)
    new = analyze(current, delimiter=delimiter, encoding=encoding)
    old_cols = {c["name"]: c for c in old["columns"]}
    new_cols = {c["name"]: c for c in new["columns"]}
    changes = []

    def add(column, code, before, after, message):
        changes.append({"column": column, "code": code, "before": before,
                        "after": after, "message": message})

    for name in old_cols.keys() - new_cols.keys():
        add(name, "removed_column", "present", "missing", "Baseline column was removed")
    for name in new_cols.keys() - old_cols.keys():
        add(name, "added_column", "missing", "present", "New column appeared")
    if old["rows"] == 0:
        if new["rows"]:
            add(None, "row_count", 0, new["rows"], "Baseline had no data records")
    elif Fraction(abs(new["rows"] - old["rows"]), old["rows"]) > Fraction(str(row_threshold)):
        add(None, "row_count", old["rows"], new["rows"], "Row count changed beyond threshold")
    for name in sorted(old_cols.keys() & new_cols.keys()):
        a, b = old_cols[name], new_cols[name]
        if a["inferred_type"] != b["inferred_type"]:
            add(name, "type_change", a["inferred_type"], b["inferred_type"], "Inferred type changed")
        old_missing = Fraction(a["null_count"], old["rows"]) if old["rows"] else Fraction(0)
        new_missing = Fraction(b["null_count"], new["rows"]) if new["rows"] else Fraction(0)
        if new_missing - old_missing > Fraction(str(null_threshold)):
            add(name, "missing_increase", a["null_rate"], b["null_rate"], "Missing fraction increased beyond threshold")
        if a["inferred_type"] in ("integer", "number") and b["inferred_type"] in ("integer", "number"):
            before, after = Decimal(a["numeric_mean"]), Decimal(b["numeric_mean"])
            # A zero baseline has no meaningful relative denominator. Any change is flagged.
            shifted = before != after if before == 0 else abs(after-before) / abs(before) > Decimal(str(mean_threshold))
            if shifted:
                add(name, "mean_shift", str(before), str(after), "Numeric mean changed beyond threshold")
    changes.sort(key=lambda c: (c["column"] or "", c["code"]))
    return {"report_version": 1, "kind": "comparison", "source": new["source"],
            "baseline": old["source"], "rows": new["rows"], "baseline_rows": old["rows"],
            "column_count": new["column_count"], "status": "fail" if changes else "pass",
            "thresholds": {"null_rate_increase": null_threshold, "relative_mean_change": mean_threshold,
                           "relative_row_change": row_threshold},
            "changes": changes, "change_count": len(changes), "columns": new["columns"]}
