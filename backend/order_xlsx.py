"""Read the provided OOXML fixtures and fill their common output template."""
from decimal import Decimal
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
N = {"s": NS}


def coordinates(address):
    import re
    column = 0
    for char in re.match(r"[A-Z]+", address).group():
        column = column * 26 + ord(char) - 64
    return column, int(re.search(r"\d+$", address).group())


def read_sheets(path):
    result = {}
    with ZipFile(path) as archive:
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(t.itertext()) for t in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        for entry in book.find("s:sheets", N):
            target = targets[entry.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
            part = str(PurePosixPath("xl") / target) if not target.startswith("/") else target.lstrip("/")
            sheet = ET.fromstring(archive.read(part))
            cells = {}
            for cell in sheet.findall("s:sheetData/s:row/s:c", N):
                value = cell.find("s:v", N)
                if cell.get("t") == "inlineStr":
                    parsed = "".join(cell.find("s:is", N).itertext())
                elif value is None or value.text is None:
                    parsed = None
                elif cell.get("t") == "s":
                    parsed = shared[int(value.text)]
                elif cell.get("t") == "str":
                    parsed = value.text
                else:
                    parsed = Decimal(value.text)
                cells[cell.get("r")] = parsed
            filter_node = sheet.find("s:autoFilter", N)
            dimension = sheet.find("s:dimension", N).get("ref").split(":")[-1]
            result[entry.get("name")] = {"cells": cells, "filter": filter_node.get("ref") if filter_node is not None else None,
                "merges": [m.get("ref") for m in sheet.findall("s:mergeCells/s:mergeCell", N)],
                "styles": {c.get("r"): int(c.get("s", "0")) for c in sheet.findall("s:sheetData/s:row/s:c", N)},
                "size": coordinates(dimension)}
    return result


def fill_template(path, values_by_sheet, additional_sheets=None, formula_overrides=None):
    """Keep the real template styles/formulas, including numeric formula caches."""
    output = BytesIO()
    with ZipFile(path) as source, ZipFile(output, "w") as target:
        additions = additional_sheets or {}
        book = ET.fromstring(source.read("xl/workbook.xml"))
        rels = ET.fromstring(source.read("xl/_rels/workbook.xml.rels"))
        types = ET.fromstring(source.read("[Content_Types].xml"))
        count = len(book.find("s:sheets", N))
        for offset, (name, grid) in enumerate(additions.items(), count + 1):
            relation_id = f"demoSheet{offset}"
            ET.SubElement(book.find("s:sheets", N), f"{{{NS}}}sheet", name=name, sheetId=str(offset),
                attrib={"{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id": relation_id})
            ET.SubElement(rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship", Id=relation_id,
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", Target=f"worksheets/sheet{offset}.xml")
            ET.SubElement(types, "{http://schemas.openxmlformats.org/package/2006/content-types}Override",
                PartName=f"/xl/worksheets/sheet{offset}.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
            worksheet = ET.Element(f"{{{NS}}}worksheet")
            ET.SubElement(worksheet, f"{{{NS}}}dimension", ref=f"A1:J{len(grid)}")
            cols = ET.SubElement(worksheet, f"{{{NS}}}cols")
            for index in range(1, 11):
                ET.SubElement(cols, f"{{{NS}}}col", min=str(index), max=str(index), width="30" if index == 3 else "18", customWidth="1")
            data = ET.SubElement(worksheet, f"{{{NS}}}sheetData")
            for r, values in enumerate(grid, 1):
                row = ET.SubElement(data, f"{{{NS}}}row", r=str(r))
                for c, value in enumerate(values, 1):
                    cell = ET.SubElement(row, f"{{{NS}}}c", r=f"{chr(64+c)}{r}", s="4" if isinstance(value, (int, Decimal)) else "0")
                    if isinstance(value, (int, Decimal)):
                        ET.SubElement(cell, f"{{{NS}}}v").text = str(value)
                    else:
                        cell.set("t", "inlineStr")
                        ET.SubElement(ET.SubElement(cell, f"{{{NS}}}is"), f"{{{NS}}}t").text = str(value)
            target.writestr(f"xl/worksheets/sheet{offset}.xml", ET.tostring(worksheet, encoding="utf-8", xml_declaration=True))
        for info in source.infolist():
            content = source.read(info.filename)
            replacement = {"xl/workbook.xml": book, "xl/_rels/workbook.xml.rels": rels, "[Content_Types].xml": types}.get(info.filename)
            if replacement is not None:
                content = ET.tostring(replacement, encoding="utf-8", xml_declaration=True)
            if info.filename in values_by_sheet:
                root = ET.fromstring(content)
                for address, value in values_by_sheet[info.filename].items():
                    cell = root.find(f"s:sheetData/s:row/s:c[@r='{address}']", N)
                    if cell is None:
                        raise ValueError("출력 템플릿 셀을 찾을 수 없습니다.")
                    for child in list(cell):
                        if child.tag != f"{{{NS}}}f":
                            cell.remove(child)
                    cell.attrib.pop("t", None)
                    override = (formula_overrides or {}).get(info.filename, {}).get(address)
                    if override is not None:
                        formula = cell.find("s:f", N)
                        if formula is None:
                            formula = ET.SubElement(cell, f"{{{NS}}}f")
                        formula.text = override
                    if isinstance(value, (int, Decimal)):
                        ET.SubElement(cell, f"{{{NS}}}v").text = str(value)
                    else:
                        # Text is always inline text, never a spreadsheet formula.
                        cell.set("t", "inlineStr")
                        ET.SubElement(ET.SubElement(cell, f"{{{NS}}}is"), f"{{{NS}}}t").text = str(value)
                content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(info, content)
    return output.getvalue()
