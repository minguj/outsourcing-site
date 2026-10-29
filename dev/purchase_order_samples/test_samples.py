"""Negative checks distinguish planted review cases from generation mistakes."""
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import generate_samples as generator
import validate_samples as validator


class SampleTests(unittest.TestCase):
    def test_all_saved_fixtures_match_independent_controls(self):
        result = validator.inspect()
        self.assertEqual(sum(row["summary"]["accepted_source_rows"] for row in result), 29)
        self.assertEqual(sum(row["summary"]["review_rows"] for row in result), 7)
        self.assertEqual(sum(row["summary"]["canceled_rows"] for row in result), 3)

    def mutate_and_check(self, filename, cell, child, value):
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary) / "samples"
            shutil.copytree(validator.PUBLIC, public)
            file = public / filename
            contents = io.BytesIO()
            with ZipFile(file) as source, ZipFile(contents, "w") as destination:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename == "xl/worksheets/sheet1.xml":
                        root = ET.fromstring(data)
                        target_cell = root.find(f"s:sheetData/s:row/s:c[@r='{cell}']", validator.N)
                        self.assertIsNotNone(target_cell)
                        if child == "numeric":
                            target_cell.attrib.pop("t", None)
                            for node in list(target_cell):
                                target_cell.remove(node)
                            ET.SubElement(target_cell, f"{{{validator.N['s']}}}v").text = value
                        else:
                            target = target_cell.find(f"s:{child}", validator.N)
                            self.assertIsNotNone(target)
                            target.text = value
                        data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                    destination.writestr(info, data)
            file.write_bytes(contents.getvalue())
            with patch.object(validator, "PUBLIC", public):
                with self.assertRaises(ValueError):
                    validator.inspect()

    def test_unplanned_normal_amount_change_is_rejected(self):
        self.mutate_and_check("purchase_order_A.xlsx", "H12", "v", "50001")

    def test_canceled_order_status_change_is_rejected(self):
        self.mutate_and_check("purchase_order_B.xlsx", "C5", "is/s:t", "결제완료")

    def test_section_row_misclassified_as_order_is_rejected(self):
        self.mutate_and_check("purchase_order_C.xlsx", "A11", "numeric", "1")

    def test_aggregate_must_keep_all_original_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            dev = Path(temporary)
            shutil.copytree(validator.DEV / "expected", dev / "expected")
            path = dev / "expected/B.expected.json"
            expected = json.loads(path.read_text(encoding="utf-8"))
            expected["accepted_output_lines"][0]["sources"].pop()
            path.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
            with patch.object(validator, "DEV", dev), self.assertRaises(ValueError):
                validator.inspect()

    def test_options_disambiguate_but_price_never_does(self):
        path = validator.DEV / "expected/B.expected.json"
        expected = json.loads(path.read_text(encoding="utf-8"))
        rows = {r["source"]["row"]: r for r in expected["rows"]}
        self.assertEqual(rows[7]["input"]["name"], rows[9]["input"]["name"])
        self.assertEqual(rows[7]["input"]["unit_price"], rows[9]["input"]["unit_price"])
        self.assertEqual(rows[7]["decision"], "확정 가능")
        self.assertEqual(rows[9]["decision"], "확인 필요")
        self.assertEqual(rows[9]["issue_codes"], ["AMBIGUOUS_ITEM"])

    def test_incorrect_template_formula_is_rejected(self):
        self.mutate_and_check("common_delivery_statement_template.xlsx", "G10", "f", "E10+F10")

    def test_generation_is_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(generator, "PUBLIC", root / "public"), patch.object(generator, "DEV", root / "dev"):
                generator.generate()
                first = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
                generator.generate()
                second = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
