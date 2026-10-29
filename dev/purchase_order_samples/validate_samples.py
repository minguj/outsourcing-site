#!/usr/bin/env python3
"""Independent on-disk checks. Does not import generator data or writer code."""
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

DEV = Path(__file__).resolve().parent
PUBLIC = DEV.parents[1] / "frontend/public/samples/purchase-orders"
N = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
def require(condition, message):
    if not condition:
        raise ValueError(message)


def decimal(value):
    return None if value is None else Decimal(str(value))


def load_workbook(path):
    """Read XML afresh, independently of the fixture writer."""
    with ZipFile(path) as archive:
        require(archive.testzip() is None, f"손상된 ZIP: {path.name}")
        require(not any("externalLink" in name or name.endswith("vbaProject.bin") for name in archive.namelist()),
                f"외부 링크/매크로 금지: {path.name}")
        for name in archive.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                tree = ET.fromstring(archive.read(name))
                if name.endswith(".rels"):
                    require(not any(e.get("TargetMode") == "External" for e in tree), "외부 관계 금지")
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.get("Id"): item.get("Target") for item in relations}
        sheets = {}
        for sheet in book.find("s:sheets", N):
            target = targets[sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
            root = ET.fromstring(archive.read(str(PurePosixPath("xl") / target)))
            cells, formulas = {}, {}
            for cell in root.findall("s:sheetData/s:row/s:c", N):
                address = cell.get("r")
                if cell.get("t") == "inlineStr":
                    value = "".join(cell.find("s:is", N).itertext())
                else:
                    raw = cell.find("s:v", N)
                    value = None if raw is None or raw.text is None else Decimal(raw.text)
                cells[address] = value
                formula = cell.find("s:f", N)
                if formula is not None:
                    formulas[address] = formula.text
            require(any("체험용 가상 데이터" in str(value) for value in cells.values()), f"가상 데이터 고지 누락: {path.name}")
            setup = root.find("s:pageSetup", N)
            names = book.find("s:definedNames", N)
            area = next((n.text for n in names if n.get("name") == "_xlnm.Print_Area" and n.get("localSheetId") == str(len(sheets))), None) if names is not None else None
            sheets[sheet.get("name")] = {"cells": cells, "formulas": formulas,
                "merges": [m.get("ref") for m in root.findall("s:mergeCells/s:mergeCell", N)],
                "orientation": setup.get("orientation"), "fit_height": setup.get("fitToHeight"), "print_area": area,
                "filter": root.find("s:autoFilter", N).get("ref") if root.find("s:autoFilter", N) is not None else None}
        return sheets


def inspect():
    from validate_structured import check
    return check(PUBLIC, DEV, load_workbook)


def validate():
    report = {"demo_notice": "체험용 가상 데이터 검증 보고서", "status": "passed", "generation_errors": []}
    try:
        report["samples"] = inspect()
        files = sorted(PUBLIC.glob("*")) + sorted((DEV / "expected").glob("*.json"))
        report["sha256"] = {str(path.relative_to(DEV.parents[1])).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in files if path.is_file()}
    except Exception as error:
        report["status"] = "failed"
        report["generation_errors"] = [str(error)]
    (DEV / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    require(report["status"] == "passed", "생성 실수 검출: " + "; ".join(report["generation_errors"]))
    for sample in report["samples"]:
        print(json.dumps(sample["summary"], ensure_ascii=False))
    print("Validation passed; generation_errors=0")
    return report


if __name__ == "__main__":
    validate()
