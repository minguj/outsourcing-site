"""Reverse export: a reviewed statement rendered in a customer's own A/B/C form.

The customer's original sample XLSX is the template. Only its item table is rewritten,
and rows below the table (totals, notes, merges, print area) shift with it. Customer item
numbers and names come from that customer's own order rows (reverse of the master match).
"""
from decimal import Decimal
from io import BytesIO
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

if __package__:
    from .order_xlsx import NS, N, coordinates, fill_template
    from .purchase_orders import DATA, ReviewError, code_label, evaluate, order_view, parse_order, text
else:
    from order_xlsx import NS, N, coordinates, fill_template
    from purchase_orders import DATA, ReviewError, code_label, evaluate, order_view, parse_order, text

FORMATS = {
    "A": {"title": "인쇄용 발주서 양식", "part": "xl/worksheets/sheet1.xml", "sheet": "인쇄발주서",
          "table": (12, 21), "styles": {"num": "13", "text": "12", "total": "9"}},
    "B": {"title": "쇼핑몰 주문 내역 양식", "part": "xl/worksheets/sheet1.xml", "sheet": "orders_export",
          "table": (2, 19), "styles": {"num": "7", "text": "6", "total": "7"}},
    "C": {"title": "제조업 구매 발주서 양식", "part": "xl/worksheets/sheet1.xml", "sheet": "구매발주서",
          "table": (11, 25), "styles": {"num": "13", "text": "12", "total": "9"}},
}


def won(value):
    return f"{int(value):,}원"


# Contact/request cells that belong to the form's own customer. They are cleared when
# another customer's statement is rendered in this form, so no foreign contact leaks in.
OWN_CELLS = {"A": ["A1", "C2", "C3", "C9", "B26", "B27", "A29"], "C": ["G4", "G5", "G6", "B8"], "B": []}


def column(index):
    name = ""
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def shift_ref(ref, after, delta):
    """Shift row numbers greater than `after` inside A1 / $A$1 / A1:B2 style references."""
    def move(match):
        number = int(match.group(3))
        return f"{match.group(1)}{match.group(2)}{number + delta if number > after else number}"
    return re.sub(r"(\$?[A-Z]{1,3})(\$?)(\d+)", move, ref)


def customer_mapping(target, session_orders, master):
    """Our item code -> how the target customer writes that item, learned from its own order rows."""
    order = session_orders.get(target) or parse_order(target)
    mapping = {}
    for row in order["rows"]:
        view = evaluate(row, master)
        code = view["item_code"]
        if not code or code in mapping:
            continue
        raw = row["raw"]
        mapping[code] = {"sku": raw.get("vendor_sku") or raw.get("code") or "", "name": str(raw.get("name") or "").strip(),
                         "spec": str(raw.get("spec") or "").strip(), "row": row["id"], "file": row["source"]["file"]}
    return mapping


def cell(ref, value, style):
    node = ET.Element(f"{{{NS}}}c", r=ref, s=style)
    if value is None or value == "":
        return node
    if isinstance(value, (int, Decimal)):
        ET.SubElement(node, f"{{{NS}}}v").text = str(value)
    else:
        node.set("t", "inlineStr")
        ET.SubElement(ET.SubElement(node, f"{{{NS}}}is"), f"{{{NS}}}t").text = str(value)
    return node


def set_value(root, ref, value, formula=None):
    """Replace a cell value (and optional formula) in place; text is never a formula."""
    node = root.find(f"s:sheetData/s:row/s:c[@r='{ref}']", N)
    if node is None:
        raise ValueError(f"양식 셀 {ref}을(를) 찾을 수 없습니다.")
    for child in list(node):
        node.remove(child)
    node.attrib.pop("t", None)
    if formula:
        ET.SubElement(node, f"{{{NS}}}f").text = formula
    if isinstance(value, (int, Decimal)):
        ET.SubElement(node, f"{{{NS}}}v").text = str(value)
    elif value is not None:
        node.set("t", "inlineStr")
        ET.SubElement(ET.SubElement(node, f"{{{NS}}}is"), f"{{{NS}}}t").text = str(value)


def rewrite_table(root, start, end, rows):
    """Replace sheet rows start..end with `rows` (lists of (value, style)); shift everything below."""
    data = root.find("s:sheetData", N)
    delta = len(rows) - (end - start + 1)
    for row in list(data):
        number = int(row.get("r"))
        if start <= number <= end:
            data.remove(row)
        elif number > end:
            row.set("r", str(number + delta))
            for node in row:
                node.set("r", shift_ref(node.get("r"), end, delta))
    position = next((i for i, row in enumerate(data) if int(row.get("r")) > start + len(rows) - 1), len(data))
    for offset, values in enumerate(rows):
        number = start + offset
        row = ET.Element(f"{{{NS}}}row", r=str(number))
        for index, (value, style) in enumerate(values, 1):
            row.append(cell(f"{column(index)}{number}", value, style))
        data.insert(position + offset, row)
    merges = root.find("s:mergeCells", N)
    if merges is not None:
        for merge in list(merges):
            first, last = (coordinates(part)[1] for part in merge.get("ref").split(":"))
            if start <= first <= end:
                merges.remove(merge)
            else:
                merge.set("ref", shift_ref(merge.get("ref"), end, delta))
        merges.set("count", str(len(merges)))
    for tag in ("s:dimension", "s:autoFilter"):
        node = root.find(tag, N)
        if node is not None:
            # A range ending on the table's last row (B's filter) follows the new last row.
            node.set("ref", shift_ref(node.get("ref"), end - 1, delta))
    return delta


def table_rows(target, view, master, mapping, styles):
    num, txt = styles["num"], styles["text"]
    output, records = [], []
    by_id = {row["id"]: row for row in view["rows"]}
    for number, line in enumerate(view["lines"], 1):
        order_ids = [str(by_id[s["row"]]["original"].get("order_id") or "") for s in line["sources"]] if view["sample"] == "B" else []
        order_ids = [value for value in order_ids if value]
        known = mapping.get(line["item_code"])
        name = known["name"] if known else line["name"]
        spec = known["spec"] if known else ""
        sku = (known["sku"] if known else "") if target != "A" else code_label(master, line["item_code"])
        quantity, price, supply = Decimal(line["quantity"]), Decimal(line["price"]), Decimal(line["supply"])
        note = "검수 완료" if known else "거래처 품번 미등록 · 표준품명 표기"
        if target == "A":
            values = [(number, num), (sku, txt), (name, txt), (spec, txt), (line["unit"], txt), (quantity, num), (price, num), (supply, num)]
        elif target == "B":
            order_id = (order_ids[0] + (f" 외 {len(order_ids) - 1}건" if len(order_ids) > 1 else "")) if order_ids else f"DEMO-{view['sample']}-회신-{number:02}"
            values = [(order_id, txt), (view["ordered"], txt), ("납품확정", txt), (sku, txt), (name, txt), (spec, txt),
                      (quantity, num), (price, num), (supply, num), (line["unit"], txt), (view["customer"], txt), ("", txt),
                      ("", txt), (line["due"], txt), ("체험용 가상 데이터", txt), ("", txt), ("DEMO-MALL", txt)]
        else:
            values = [(number, num), (sku, txt), (name, txt), (spec, txt), (line["unit"], txt), (quantity, num), (price, num),
                      (supply, num), (line["due"], txt), (note, txt)]
        output.append(values)
        records.append([str(number), code_label(master, line["item_code"]), line["name"], sku or "(없음)", name,
                        f"{known['file']} {known['row']}행" if known else "기존 발주 기록 없음 → 표준품명 사용",
                        ", ".join(order_ids)])
    return output, records


def export_customer_format(order, session_orders, master, target, data=DATA):
    if target not in FORMATS:
        raise ReviewError("A/B/C 거래처 양식만 지원합니다.")
    view = order_view(order, master)
    if not view["ready"]:
        raise ReviewError("미해결 행이 있거나 확정 행이 없어 최종 발행할 수 없습니다.")
    spec = FORMATS[target]
    mapping = customer_mapping(target, session_orders, master)
    rows, records = table_rows(target, view, master, mapping, spec["styles"])
    start, end = spec["table"]
    totals = {key: Decimal(view["totals"][key]) for key in ("supply", "vat", "total")}
    dates = sorted({line["due"] for line in view["lines"]})
    due = dates[0] if len(dates) == 1 else " / ".join(dates)
    last = start + len(rows) - 1
    if target == "B":
        styles = spec["styles"]
        rows.append([("합계 (검수 완료)", styles["text"])] + [("", styles["text"])] * 7 +
                    [(totals["supply"], styles["num"])] + [("", styles["text"])] * 8)
    output = BytesIO()
    with ZipFile(data / f"purchase_order_{target}.xlsx") as source, ZipFile(output, "w") as zipped:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == spec["part"]:
                root = ET.fromstring(content)
                delta = rewrite_table(root, start, end, rows)
                if view["sample"] != target:
                    for ref in OWN_CELLS[target]:
                        row = coordinates(ref)[1]
                        set_value(root, ref if row < start else f"{ref[0]}{row + delta}", "—")
                if target == "A":
                    set_value(root, "A5", "납  품  회  신  서")
                    set_value(root, "C7", f"DEMO-{view['sample']}-회신")
                    set_value(root, "G7", view["ordered"])
                    set_value(root, "G8", due)
                    set_value(root, "C1", view["customer"])
                    set_value(root, f"A{23 + delta}", "공급가액 합계 (검수 완료)")
                    set_value(root, f"H{23 + delta}", totals["supply"], f"SUM(H{start}:H{last})")
                    set_value(root, f"A{24 + delta}", f"부가세 {won(totals['vat'])} 별도 · 합계 {won(totals['total'])}. 우리 회사 검수 결과를 거래처 양식으로 회신한 체험용 문서입니다.")
                elif target == "C":
                    set_value(root, "E1", "납품 회신서")
                    set_value(root, "E2", "DELIVERY REPLY / 체험용 가상 데이터")
                    set_value(root, "A1", view["customer"])
                    set_value(root, "B4", f"DEMO-{view['sample']}-회신")
                    set_value(root, "B5", view["ordered"])
                    set_value(root, f"A{26 + delta}", "소계 (검수 완료 공급가액)")
                    set_value(root, f"H{26 + delta}", totals["supply"], f"SUM(H{start}:H{last})")
                    set_value(root, f"A{28 + delta}", f"총 공급가액 (부가세 {won(totals['vat'])} 별도 · 합계 {won(totals['total'])})")
                    set_value(root, f"H{28 + delta}", totals["supply"], f"H{26 + delta}")
                    set_value(root, f"A{29 + delta}", "우리 회사 검수 결과를 거래처 양식으로 회신한 체험용 문서입니다. 구매품번은 거래처의 기존 발주 기록에서 역변환했습니다.")
                content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            elif info.filename == "xl/workbook.xml":
                root = ET.fromstring(content)
                for name in root.iter(f"{{{NS}}}definedName"):
                    if name.get("name") == "_xlnm.Print_Area":
                        name.text = shift_ref(name.text, end - 1, len(rows) - (end - start + 1))
                content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            elif target == "B" and info.filename == "xl/worksheets/sheet2.xml":
                root = ET.fromstring(content)
                set_value(root, "B2", "체험용 가상 데이터 — 우리 회사 검수 결과를 쇼핑몰 주문 내역 양식으로 회신했습니다.")
                set_value(root, "B4", f"(가상)모아소모품 도매 > {view['sample']} 거래처 검수 완료 거래명세서")
                set_value(root, "B5", f"KRW / 공급가액 {won(totals['supply'])} / 부가세 {won(totals['vat'])} / 합계 {won(totals['total'])}")
                if view["sample"] != target:
                    set_value(root, "B6", "—")
                content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            zipped.writestr(info, content)
    record = [["체험용 가상 데이터 — 거래처 양식 회신 변환기록"],
              [f"원본: {view['sample']} 거래처 검수 완료 거래명세서 → 출력: {target} 거래처의 {spec['title']}"],
              ["출력 순번", "우리 품목코드", "표준품명", "거래처 품번", "거래처 품명", "역변환 근거", "원본 주문번호"], *records]
    return fill_template(BytesIO(output.getvalue()), {}, {"회신변환기록": record})
