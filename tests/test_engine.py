import csv
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from tabletrail import Contract, analyze, compare, load_contract
from tabletrail.engine import classify
from tabletrail.errors import TableTrailError

ROOT = Path(__file__).resolve().parents[1]


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data.csv"

    def csv(self, rows):
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)
        return self.path

    def contract(self, columns, **kwargs):
        return Contract.from_dict({"version": 1, "name": "test", "columns": columns, **kwargs})

    def test_profile_counts_nulls_distinct_and_duplicates_exactly(self):
        path = self.csv([["id", "amount"], ["001", "10.5"], ["002", ""], ["001", "10.5"]])
        result = analyze(path)
        self.assertEqual((result["rows"], result["duplicate_rows"]), (3, 1))
        self.assertEqual(result["columns"][0]["inferred_type"], "string")
        amount = result["columns"][1]
        self.assertEqual((amount["null_count"], amount["distinct_count"]), (1, 1))
        self.assertEqual(Decimal(amount["numeric_mean"]), Decimal("10.5"))

    def test_type_inference_and_non_finite_numbers(self):
        cases = {"001": "string", "1": "integer", "1.2": "number", "true": "boolean",
                 "FALSE": "boolean", "2024-02-29": "date", "2023-02-29": "string",
                 "NaN": "string", "Infinity": "string", "1e1001": "string"}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(classify(value), expected)

    def test_numeric_int_float_inference(self):
        result = analyze(self.csv([["value"], ["1"], ["2.5"]]))
        self.assertEqual(result["columns"][0]["inferred_type"], "number")

    def test_all_rule_codes_and_exact_totals_with_issue_cap(self):
        contract = self.contract({
            "id": {"required": True, "unique": True, "pattern": "[A-Z]{2}"},
            "n": {"type": "integer", "min": 0, "max": 10},
            "category": {"enum": ["ok"], "min_length": 2, "max_length": 3},
            "day": {"type": "date"}, "flag": {"type": "boolean"}})
        path = self.csv([["id", "n", "category", "day", "flag"],
                         ["AA", "-1", "x", "2023-02-29", "yes"],
                         ["AA", "11", "long", "2024-01-01", "true"],
                         ["", "one", "ok", "2024-01-01", "false"],
                         ["bad", "1", "ok", "2024-01-01", "true"]])
        result = analyze(path, contract, max_issues=2)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["failed_records"], 4)
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(result["issue_count"], sum(result["issue_counts"].values()))
        self.assertEqual(result["omitted_issues"], result["issue_count"] - 2)
        self.assertEqual(set(result["issue_counts"]),
                         {"min", "max", "enum", "min_length", "max_length", "type", "unique", "required", "pattern"})

    def test_composite_key_is_not_naive_string_concatenation(self):
        contract = self.contract({"a": {}, "b": {}}, unique_keys=[["a", "b"]])
        path = self.csv([["a", "b"], ["a|b", "c"], ["a", "b|c"], ["a|b", "c"], ["", "c"], ["", "c"]])
        result = analyze(path, contract)
        self.assertEqual(result["issue_counts"], {"unique_key": 1})

    def test_missing_and_extra_columns_are_header_failures(self):
        result = analyze(self.csv([["a", "extra"], ["1", "2"]]), self.contract({"a": {}, "b": {}}))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["failed_records"], 0)
        self.assertEqual(result["issue_counts"], {"extra_column": 1, "missing_column": 1})
        self.assertIsNone(result["issues"][0]["record"])

    def test_optional_column_must_exist_but_null_can_repeat(self):
        result = analyze(self.csv([["x"], [""], [" "]]), self.contract({"x": {"unique": True}}))
        self.assertEqual(result["issue_count"], 0)
        self.assertEqual(result["columns"][0]["inferred_type"], "empty")

    def test_custom_null_markers_and_whitespace(self):
        result = analyze(self.csv([["x"], [" N/A "], ["4"]]),
                         self.contract({"x": {"required": True}}, null_values=["N/A"]))
        self.assertEqual(result["issue_counts"], {"required": 1})
        self.assertEqual(result["columns"][0]["null_count"], 1)

    def test_unique_rows_are_opt_in_and_after_trimming(self):
        result = analyze(self.csv([["x"], [" hi "], ["hi"]]), self.contract({"x": {}}, unique_rows=True))
        self.assertEqual(result["issue_counts"], {"duplicate_row": 1})

    def test_multiline_quotes_unicode_and_bom(self):
        self.path.write_text('\ufeffid,note\r\n1,"hello, world\r\nनमस्ते"\r\n', encoding="utf-8", newline="")
        result = analyze(self.path, self.contract({"id": {}, "note": {"max_length": 2}}))
        self.assertEqual(result["rows"], 1)
        self.assertEqual(result["issues"][0]["line"], 3)
        self.assertEqual(result["issues"][0]["record"], 2)

    def test_header_only_file_is_valid_and_has_zero_null_rate(self):
        result = analyze(self.csv([["x"]]))
        self.assertEqual(result["rows"], 0)
        self.assertEqual(result["columns"][0]["null_rate"], 0)

    def test_bad_input_is_never_silently_accepted(self):
        for text in ("", "a,a\n1,2\n", "a,\n1,2\n", "a,b\n1\n", 'a\n"unterminated'):
            with self.subTest(text=text):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaises(TableTrailError):
                    analyze(self.path)

    def test_tab_delimiter_and_blank_records(self):
        self.path.write_text("a\tb\n\n1\t2\n", encoding="utf-8")
        self.assertEqual(analyze(self.path, delimiter="\t")["rows"], 1)

    def test_examples_have_intended_outcomes(self):
        contract = load_contract(ROOT / "examples/inventory.contract.json")
        clean = analyze(ROOT / "examples/inventory.csv", contract)
        bad = analyze(ROOT / "examples/inventory_with_issues.csv", contract)
        self.assertEqual(clean["status"], "pass")
        self.assertEqual(bad["issue_count"], 12)
        self.assertEqual(bad["failed_records"], 11)

    def test_issue_limit_zero_and_invalid_values(self):
        path = self.csv([["x"], ["bad"]])
        result = analyze(path, self.contract({"x": {"type": "integer"}}), max_issues=0)
        self.assertEqual((result["issue_count"], result["issues"]), (1, []))
        for value in (-1, 10001, True):
            with self.assertRaises(TableTrailError):
                analyze(path, max_issues=value)


class ComparisonTests(unittest.TestCase):
    def test_exact_missing_threshold_does_not_trigger_float_rounding_error(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.csv", Path(directory) / "b.csv"
            # 15% -> 20% is exactly five percentage points, not beyond five.
            a.write_text("x\n" + '""\n' * 3 + "ok\n" * 17, encoding="utf-8")
            b.write_text("x\n" + '""\n' * 4 + "ok\n" * 16, encoding="utf-8")
            self.assertEqual(compare(a, b, null_threshold=0.05)["changes"], [])

    def test_same_file_has_no_changes(self):
        path = ROOT / "examples/inventory.csv"
        self.assertEqual(compare(path, path)["changes"], [])

    def test_example_detects_added_column_nulls_and_means(self):
        report = compare(ROOT / "examples/inventory.csv", ROOT / "examples/inventory_next.csv")
        self.assertEqual(report["change_count"], 4)
        self.assertEqual({c["code"] for c in report["changes"]}, {"added_column", "missing_increase", "mean_shift"})

    def test_invalid_thresholds_rejected(self):
        for value in (-1, float("nan"), float("inf"), True):
            with self.assertRaises(TableTrailError):
                compare("unused", "unused", mean_threshold=value)

    def test_zero_and_negative_baseline_mean_and_removed_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.csv", Path(directory) / "b.csv"
            a.write_text("zero,negative,removed\n0,-10,x\n", encoding="utf-8")
            b.write_text("zero,negative\n1,-20\n", encoding="utf-8")
            result = compare(a, b)
            self.assertEqual(result["change_count"], 3)
            self.assertEqual([c["code"] for c in result["changes"]].count("mean_shift"), 2)

    def test_empty_baseline_to_populated_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.csv", Path(directory) / "b.csv"
            a.write_text("x\n", encoding="utf-8")
            b.write_text("x\n2\n", encoding="utf-8")
            self.assertIn("row_count", [c["code"] for c in compare(a, b)["changes"]])


if __name__ == "__main__":
    unittest.main()
