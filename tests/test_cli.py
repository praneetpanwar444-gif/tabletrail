import contextlib
import io
from html import unescape
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote

from tabletrail import Contract, analyze
from tabletrail.cli import main
from tabletrail.report import render_html

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "data.csv"
        self.source.write_text("a,b\n1,hello\n2,world\n", encoding="utf-8")

    def run_cli(self, args):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_profile_json_html_written(self):
        target = self.folder / "nested/report.json"
        html = self.folder / "nested/report.html"
        code, _, err = self.run_cli(["profile", str(self.source), "--json", str(target), "--html", str(html)])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(target.read_text())["rows"], 2)
        self.assertIn("Know your data.", html.read_text(encoding="utf-8"))

    def test_contract_draft_round_trips(self):
        contract = self.folder / "draft.json"
        self.assertEqual(self.run_cli(["init", str(self.source), "--output", str(contract)])[0], 0)
        self.assertEqual(self.run_cli(["validate", str(self.source), "--contract", str(contract)])[0], 0)

    def test_exit_codes_for_findings_and_input_errors(self):
        bad = ROOT / "examples/inventory_with_issues.csv"
        contract = ROOT / "examples/inventory.contract.json"
        self.assertEqual(self.run_cli(["validate", str(bad), "--contract", str(contract)])[0], 1)
        self.assertEqual(self.run_cli(["profile", str(self.folder / "missing.csv")])[0], 2)
        self.assertEqual(self.run_cli(["compare", str(self.source), str(self.source), "--null-threshold", "nan"])[0], 2)

    def test_input_cannot_be_overwritten(self):
        original = self.source.read_bytes()
        code, _, err = self.run_cli(["profile", str(self.source), "--json", str(self.source)])
        self.assertEqual(code, 2)
        self.assertIn("must not overwrite", err)
        self.assertEqual(self.source.read_bytes(), original)

    def test_output_paths_must_be_different(self):
        target = self.folder / "report.txt"
        self.assertEqual(self.run_cli(["profile", str(self.source), "--json", str(target), "--html", str(target)])[0], 2)
        self.assertFalse(target.exists())

    def test_contract_cannot_be_overwritten_by_report(self):
        contract = self.folder / "c.json"
        contract.write_text('{"version":1,"columns":{"a":{},"b":{}}}', encoding="utf-8")
        self.assertEqual(self.run_cli(["validate", str(self.source), "--contract", str(contract), "--html", str(contract)])[0], 2)

    def test_malformed_csv_produces_no_partial_report(self):
        self.source.write_text("a,b\n1,2\n3\n", encoding="utf-8")
        target = self.folder / "report.json"
        self.assertEqual(self.run_cli(["profile", str(self.source), "--json", str(target)])[0], 2)
        self.assertFalse(target.exists())

    def test_untrusted_csv_text_is_html_escaped_and_json_round_trips(self):
        self.source.write_text('x\n"</script><img src=x onerror=alert(1)>"\n', encoding="utf-8")
        contract = Contract.from_dict({"version": 1, "columns": {"x": {"type": "integer"}}})
        report = analyze(self.source, contract)
        html = render_html(report)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;/script&gt;", html)
        payload = html.split('<script id="report-data" type="application/json">')[1].split("</script>")[0]
        self.assertEqual(json.loads(payload), report)
        href = html.split('href="data:application/json;charset=utf-8,')[1].split('"')[0]
        self.assertEqual(json.loads(unquote(unescape(href))), report)
        self.assertNotIn("https://", html)

    def test_comparison_html_and_filters_are_available(self):
        target = self.folder / "comparison.html"
        self.assertEqual(self.run_cli(["compare", str(self.source), str(self.source), "--html", str(target)])[0], 0)
        text = target.read_text(encoding="utf-8")
        self.assertIn("See what changed.", text)
        self.assertIn('aria-label="Filter column profiles"', text)

    def test_python_module_entry_point(self):
        result = subprocess.run([sys.executable, "-m", "tabletrail", "--version"], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("TableTrail 0.1.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
