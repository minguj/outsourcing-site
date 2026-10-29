"""Small deterministic OOXML writer for demo fixtures; no third-party packages."""
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)


def col(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def xml(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def workbook(path, sheets, title):
    """Sheets contain cells {row: values}, header_rows, merges, widths, formulas."""
    parts = {}
    types = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    for extension, content in (("rels", "application/vnd.openxmlformats-package.relationships+xml"),
                               ("xml", "application/xml")):
        ET.SubElement(types, "Default", Extension=extension, ContentType=content)
    overrides = [("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
                 ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
                 ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml")]
    book = ET.Element("workbook", xmlns=NS)
    ET.SubElement(book, "bookViews").append(ET.Element("workbookView"))
    book_sheets = ET.SubElement(book, "sheets")
    print_names = []
    relationships = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    for index, sheet in enumerate(sheets, 1):
        ET.SubElement(book_sheets, "sheet", name=sheet["name"], sheetId=str(index),
                      attrib={"{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id": f"rId{index}"})
        ET.SubElement(relationships, "Relationship", Id=f"rId{index}", Type=rel_type + "worksheet",
                      Target=f"worksheets/sheet{index}.xml")
        overrides.append((f"/xl/worksheets/sheet{index}.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"))
        root = ET.Element("worksheet", xmlns=NS)
        properties = ET.SubElement(root, "sheetPr")
        ET.SubElement(properties, "pageSetUpPr", fitToPage="1")
        last_row = max(sheet["cells"])
        last_col = max(len(values) for values in sheet["cells"].values())
        ET.SubElement(root, "dimension", ref=f"A1:{col(last_col)}{last_row}")
        views = ET.SubElement(root, "sheetViews")
        view = ET.SubElement(views, "sheetView", workbookViewId="0", showGridLines="1" if sheet.get("raw") else "0")
        freeze = sheet.get("freeze", 1)
        ET.SubElement(view, "pane", ySplit=str(freeze), topLeftCell=f"A{freeze + 1}",
                      activePane="bottomLeft", state="frozen")
        ET.SubElement(root, "sheetFormatPr", defaultRowHeight=str(sheet.get("row_height", 23)))
        columns = ET.SubElement(root, "cols")
        for index_col, width in enumerate(sheet.get("widths", [22] * last_col), 1):
            ET.SubElement(columns, "col", min=str(index_col), max=str(index_col), width=str(width), customWidth="1")
        data = ET.SubElement(root, "sheetData")
        for number, values in sorted(sheet["cells"].items()):
            row = ET.SubElement(data, "row", r=str(number))
            height = sheet.get("heights", {}).get(number, 34 if number in (1, 2) and not sheet.get("raw") else None)
            if height is not None:
                row.set("ht", str(height))
                row.set("customHeight", "1")
            for index_col, value in enumerate(values, 1):
                coordinate = f"{col(index_col)}{number}"
                style = 1 if number == 1 else 2 if number == 2 else 3 if number in sheet.get("header_rows", []) else 0
                if isinstance(value, (int, Decimal)):
                    style = 4
                if sheet.get("raw"):
                    style = 5 if number in sheet.get("header_rows", []) else 7 if isinstance(value, (int, Decimal)) else 6
                style = sheet.get("row_styles", {}).get(number, style)
                style = sheet.get("styles", {}).get(coordinate, style)
                cell = ET.SubElement(row, "c", r=coordinate, s=str(style))
                if coordinate in sheet.get("formulas", {}):
                    if coordinate not in sheet.get("styles", {}):
                        cell.set("s", "4")
                    ET.SubElement(cell, "f").text = sheet["formulas"][coordinate]
                    cached = sheet.get("formula_values", {}).get(coordinate)
                    if cached is None:
                        cell.set("t", "str")
                    ET.SubElement(cell, "v").text = "" if cached is None else str(cached)
                elif value is None:
                    pass
                elif isinstance(value, (int, Decimal)):
                    ET.SubElement(cell, "v").text = str(value)
                else:
                    cell.set("t", "inlineStr")
                    ET.SubElement(ET.SubElement(cell, "is"), "t").text = str(value)
        if sheet.get("filter"):
            ET.SubElement(root, "autoFilter", ref=sheet["filter"])
        if sheet.get("merges"):
            merges = ET.SubElement(root, "mergeCells", count=str(len(sheet["merges"])))
            for ref in sheet["merges"]:
                ET.SubElement(merges, "mergeCell", ref=ref)
        ET.SubElement(root, "printOptions", horizontalCentered="1")
        ET.SubElement(root, "pageMargins", left="0.25", right="0.25", top="0.4", bottom="0.4", header="0.2", footer="0.2")
        ET.SubElement(root, "pageSetup", paperSize="9", orientation=sheet.get("orientation", "landscape"),
                      fitToWidth=str(sheet.get("fit_width", 1)), fitToHeight=str(sheet.get("fit_height", 0)))
        footer = ET.SubElement(root, "headerFooter")
        ET.SubElement(footer, "oddFooter").text = "&C체험용 가상 데이터 · &P / &N"
        if sheet.get("print_area"):
            print_names.append((index - 1, sheet["name"], sheet["print_area"]))
        parts[f"xl/worksheets/sheet{index}.xml"] = xml(root)
    if print_names:
        names = ET.SubElement(book, "definedNames")
        for index, name, area in print_names:
            ET.SubElement(names, "definedName", name="_xlnm.Print_Area", localSheetId=str(index)).text = "'" + name.replace("'", "''") + "'!" + area
    ET.SubElement(book, "calcPr", calcId="191029", fullCalcOnLoad="1", forceFullCalc="1")
    ET.SubElement(relationships, "Relationship", Id="rIdStyles", Type=rel_type + "styles", Target="styles.xml")
    for name, content in overrides:
        ET.SubElement(types, "Override", PartName=name, ContentType=content)
    parts["[Content_Types].xml"] = xml(types)
    parts["xl/workbook.xml"] = xml(book)
    parts["xl/_rels/workbook.xml.rels"] = xml(relationships)
    parts["_rels/.rels"] = f'''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="{rel_type}officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>'''.encode()
    # Names, metadata and timestamps intentionally contain no local user identity.
    parts["docProps/core.xml"] = '''<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:creator>체험용 가상 데이터 생성기</dc:creator>
<dc:description>체험용 가상 데이터. 실제 회사 및 개인정보가 아닙니다.</dc:description>
<dcterms:created xsi:type="dcterms:W3CDTF">2026-10-29T00:00:00Z</dcterms:created>
</cp:coreProperties>'''.encode()
    parts["xl/styles.xml"] = '''<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.###"/></numFmts>
<fonts count="7">
<font><sz val="11"/><name val="맑은 고딕"/></font>
<font><b/><sz val="18"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><sz val="11"/><color rgb="FF92400E"/><name val="맑은 고딕"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="14"/><color rgb="FF16324F"/><name val="맑은 고딕"/></font>
<font><b/><sz val="28"/><color rgb="FF276C83"/><name val="맑은 고딕"/></font>
</fonts>
<fills count="7"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF16324F"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFEF3C7"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF276C83"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEEEEEE"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFE2EEF3"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/></border>
<border><left style="thin"><color rgb="FFD2D8DF"/></left><right style="thin"><color rgb="FFD2D8DF"/></right><top style="thin"><color rgb="FFD2D8DF"/></top><bottom style="thin"><color rgb="FFD2D8DF"/></bottom></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="15">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="4" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="5" borderId="1" xfId="0"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0"><alignment vertical="center"/></xf>
<xf numFmtId="164" fontId="4" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment vertical="center" horizontal="right"/></xf>
<xf numFmtId="0" fontId="3" fillId="4" borderId="0" xfId="0"><alignment vertical="center"/></xf>
<xf numFmtId="164" fontId="5" fillId="6" borderId="1" xfId="0" applyNumberFormat="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="6" fillId="0" borderId="0" xfId="0"><alignment vertical="center" horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="5" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1"><alignment vertical="center" horizontal="right"/></xf>
<xf numFmtId="0" fontId="5" fillId="0" borderId="0" xfId="0"><alignment vertical="center"/></xf>
</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''.encode()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        for name, content in sorted(parts.items()):
            info = ZipInfo(name, date_time=(2026, 10, 29, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            output.writestr(info, content)
