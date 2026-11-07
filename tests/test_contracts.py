import json
from pathlib import Path
import tempfile
import unittest

from tabletrail import Contract, load_contract
from tabletrail.errors import TableTrailError


class ContractTests(unittest.TestCase):
    def test_invalid_contracts_fail_with_actionable_error(self):
        base = {"version": 1, "columns": {"x": {}}}
        invalid = [[], {}, {**base, "version": True}, {**base, "name": ""},
                   {**base, "allow_extra_columns": "yes"}, {**base, "typo": True},
                   {**base, "unique_keys": [["unknown"]]}, {**base, "unique_keys": [["x", "x"]]},
                   {**base, "null_values": [1]}, {**base, "columns": {"x": {"requird": True}}}]
        rules = [{"type": "float"}, {"type": []}, {"type": "integer", "min": 5, "max": 1},
                 {"min": 1}, {"type": "number", "min": True}, {"type": "number", "max": float("nan")},
                 {"pattern": "["}, {"pattern": None}, {"enum": []}, {"enum": [1]},
                 {"min_length": True}, {"min_length": 3, "max_length": 2}, {"required": 1}]
        invalid.extend({**base, "columns": {"x": r}} for r in rules)
        for data in invalid:
            with self.subTest(data=data):
                with self.assertRaises(TableTrailError):
                    Contract.from_dict(data)

    def test_duplicate_keys_rejected_in_nested_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text('{"version":1,"columns":{"x":{"type":"string","type":"integer"}}}', encoding="utf-8")
            with self.assertRaisesRegex(TableTrailError, "Duplicate JSON key"):
                load_contract(path)

    def test_invalid_json_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            with self.assertRaises(TableTrailError):
                load_contract(path)
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(TableTrailError):
                load_contract(path)

    def test_minimal_valid_contract(self):
        contract = Contract.from_dict({"version": 1, "columns": {"x": {}}})
        self.assertEqual(contract.columns["x"].type, "string")
        self.assertFalse(contract.columns["x"].required)
