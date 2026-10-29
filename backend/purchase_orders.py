"""Sample-only parsing/review domain. No expected fixtures are read at runtime."""
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import re

if __package__:
    from .order_xlsx import fill_template, read_sheets, coordinates
else:
    from order_xlsx import fill_template, read_sheets, coordinates

PACKAGED = Path(__file__).resolve().parents[1] / "samples/purchase-orders"
DATA = PACKAGED if PACKAGED.exists() else Path(__file__).resolve().parents[1] / "frontend/public/samples/purchase-orders"
FORMATS = {
    "A": {"sheet": "인쇄발주서", "fields": {"번호": "line", "품목코드": "code", "품명": "name", "규격": "spec", "단위": "unit", "수량": "quantity", "단가": "price", "공급가액": "amount"},
          "customer": "C1", "ordered": "G7", "due": "G8"},
    "B": {"sheet": "orders_export", "fields": {"주문번호": "order_id", "주문일시": "ordered", "주문상태": "order_status", "판매상품번호": "vendor_sku", "상품명": "name", "옵션": "spec", "단위": "unit", "수량": "quantity", "판매단가": "price", "상품금액": "amount", "요청납기": "due"},
          "customer": "K2", "ordered": "B2"},
    "C": {"sheet": "구매발주서", "fields": {"번호": "line", "구매품번": "vendor_sku", "품목명": "name", "규격": "spec", "단위": "unit", "수량": "quantity", "단가": "price", "공급가액": "amount", "요청납기": "due", "비고": "note"},
          "customer": "A1", "ordered": "B5"},
}
MESSAGES = {"MISSING_QUANTITY": "필수 수량이 비어 있습니다.", "UNKNOWN_ITEM": "마스터에 없는 품목입니다.",
            "AMBIGUOUS_ITEM": "여러 품목에 쓰이는 별칭입니다. 직접 선택해 주세요.",
            "AMOUNT_MISMATCH": "기재 금액과 계산 공급가액이 다릅니다. 계산 금액의 사용 여부를 확인해 주세요."}


class ReviewError(ValueError):
    pass


def text(number):
    return None if number is None else format(Decimal(number), "f")


def money(number):
    return number.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def quantity(value):
    try:
        result = Decimal(value)
        if not result.is_finite() or result <= 0 or result > 1000000 or result.as_tuple().exponent < -3:
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise ReviewError("수량은 0보다 크고 1,000,000 이하인 소수점 세 자리 이내 숫자여야 합니다.") from None


def load_master(data=DATA):
    with (data / "item_master.csv").open(encoding="utf-8-sig", newline="") as file:
        return {r["품목코드"]: {"code": r["품목코드"], "name": r["표준명"], "unit": r["단위"],
                                 "price": Decimal(r["기준단가"]), "aliases": r["별칭"].split("|"), "registered": False, "pending": False} for r in csv.DictReader(file)}


MAX_REGISTERED = 20
PENDING_CODE = "미정"


def new_item(master, action):
    """Validate a session-only master item. Nothing is written to item_master.csv."""
    name = re.sub(r"\s+", " ", action.get("new_name") or "").strip()
    unit = (action.get("new_unit") or "").strip()
    if not 2 <= len(name) <= 40:
        raise ReviewError("표준품명은 2~40자로 입력해 주세요.")
    if not 1 <= len(unit) <= 10:
        raise ReviewError("단위는 1~10자로 입력해 주세요.")
    if any(item["name"] == name for item in master.values()):
        raise ReviewError("같은 표준품명이 이미 마스터에 있습니다. 목록에서 선택해 주세요.")
    try:
        price = Decimal((action.get("new_price") or "").replace(",", "").strip())
        if not price.is_finite() or price <= 0 or price > 10000000 or price.as_tuple().exponent < -2:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ReviewError("기준단가는 0보다 크고 10,000,000 이하인 숫자여야 합니다.") from None
    count = sum(item.get("registered", False) for item in master.values())
    if count >= MAX_REGISTERED:
        raise ReviewError("이번 체험에서 등록할 수 있는 신규 품목 수를 넘었습니다.")
    code = (action.get("new_code") or "").strip().upper()
    if code:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,9}", code):
            raise ReviewError("품목코드는 영문·숫자·하이픈 2~10자로 입력하거나 비워 두세요.")
        if code in master:
            raise ReviewError(f"품목코드 {code}은(는) 이미 마스터에 있습니다.")
        return {"code": code, "name": name, "unit": unit, "price": price, "aliases": [], "registered": True, "pending": False}
    # Code left blank: keep an internal key so different pending items never merge, but show "미정".
    key = next(f"미정-{n}" for n in range(1, MAX_REGISTERED + 2) if f"미정-{n}" not in master)
    return {"code": key, "name": name, "unit": unit, "price": price, "aliases": [], "registered": True, "pending": True}


def code_label(master, code):
    item = master.get(code)
    return PENDING_CODE if item and item.get("pending") else code


def parse_order(sample, data=DATA):
    if sample not in FORMATS:
        raise ReviewError("제공된 A/B/C 샘플만 지원합니다.")
    spec = FORMATS[sample]
    filename = f"purchase_order_{sample}.xlsx"
    sheet = read_sheets(data / filename)[spec["sheet"]]
    cells = sheet["cells"]
    # Recognize actual table labels, not a completed result keyed by file name.
    row_numbers = sorted({int(re.search(r"\d+$", address).group()) for address in cells})
    header = None
    columns = {}
    for row in row_numbers:
        found = {value: re.sub(r"\d", "", address) for address, value in cells.items()
                 if int(re.search(r"\d+$", address).group()) == row and isinstance(value, str)}
        if set(spec["fields"]) <= set(found):
            header = row
            columns = {field: found[label] for label, field in spec["fields"].items()}
            break
    if header is None:
        raise ReviewError("샘플 표 구조를 확인할 수 없습니다.")
    last = sheet["size"][1]
    rows = []
    layout = []
    for row in range(header + 1, last + 1):
        raw = {field: cells.get(f"{column}{row}") for field, column in columns.items()}
        if sample == "B":
            is_order = bool(raw.get("order_id"))
        else:
            line = raw.get("line")
            is_order = isinstance(line, Decimal) and line > 0 and line == line.to_integral()
        if not is_order:
            label = cells.get(f"A{row}")
            kind = "blank" if not any(cells.get(f"{chr(65+c)}{row}") is not None for c in range(sheet["size"][0])) else "subtotal" if str(label).startswith("소계") else "total" if str(label).startswith("총") else "layout"
            layout.append({"row": row, "kind": kind, "label": str(label or "")})
            continue
        source_cells = {field: f"{column}{row}" for field, column in columns.items()}
        if sample == "A":
            raw["due"] = cells[spec["due"]]
            source_cells["due"] = spec["due"]
        rows.append({"id": row, "raw": raw, "strict_spec": sample == "C",
                     "source": {"file": filename, "sheet": spec["sheet"], "row": row,
                                "cells": source_cells},
                     "edits": {}, "audit": []})
    if not rows or len(rows) > 20:
        raise ReviewError("샘플 표의 품목 행 수가 지원 범위를 벗어났습니다.")
    return {"sample": sample, "filename": filename, "sheet": spec["sheet"], "header_row": header,
            "customer": str(cells[spec["customer"]]), "ordered": str(cells[spec["ordered"]])[:10],
            "rows": rows, "layout_rows": layout, "preview": preview(sheet)}


def preview(sheet):
    merges, covered = {}, set()
    for area in sheet["merges"]:
        start, end = area.split(":")
        c1, r1 = coordinates(start)
        c2, r2 = coordinates(end)
        merges[(c1, r1)] = (c2 - c1 + 1, r2 - r1 + 1)
        covered.update((c, r) for c in range(c1, c2 + 1) for r in range(r1, r2 + 1) if (c, r) != (c1, r1))
    rows = []
    for r in range(1, sheet["size"][1] + 1):
        cells = []
        for c in range(1, sheet["size"][0] + 1):
            if (c, r) in covered:
                continue
            address = f"{chr(64+c)}{r}"
            value = sheet["cells"].get(address)
            span = merges.get((c, r), (1, 1))
            cells.append({"address": address, "text": text(value) if isinstance(value, Decimal) else str(value or ""),
                          "colspan": span[0], "rowspan": span[1], "style": sheet["styles"].get(address, 0)})
        rows.append({"number": r, "cells": cells})
    return rows


def is_canceled(row):
    return row["raw"].get("order_status") in ("취소", "취소완료")


def evaluate(row, master):
    raw, edits = row["raw"], row["edits"]
    restored = is_canceled(row) and bool(edits.get("restored"))
    if is_canceled(row) and not restored:
        return {"id": row["id"], "source": row["source"],
                "original": {key: text(value) if isinstance(value, Decimal) else value for key, value in raw.items()},
                "item_code": None, "item_registered": False, "name": raw["name"], "unit": raw["unit"], "quantity": text(raw.get("quantity")),
                "price": text(raw["price"]), "supply": None, "vat": None, "total": None,
                "due": raw["due"], "status": "canceled", "restored": False, "restored_only": False, "issues": [], "candidates": [], "exclude_reason": "", "audit": row["audit"]}
    name = str(raw["name"]).strip()
    code = raw.get("code")
    combined = " ".join(filter(None, [name, str(raw.get("spec") or "").strip()]))
    candidates = [code] if code in master else ([] if code else [key for key, item in master.items() if combined in [item["name"], *item["aliases"]]])
    if not code and not candidates and not (row.get("strict_spec") and raw.get("spec")):
        candidates = [key for key, item in master.items() if name in [item["name"], *item["aliases"]]]
    selected = edits.get("item_code") or (candidates[0] if len(candidates) == 1 else None)
    item = master.get(selected)
    count = edits.get("quantity", raw.get("quantity"))
    price = item["price"] if edits.get("item_code") else raw["price"]
    supply = money(count * price) if count is not None else None
    vat = money(supply * Decimal("0.10")) if supply is not None else None
    issues = []
    if count is None:
        issues.append("MISSING_QUANTITY")
    if not item:
        issues.append("AMBIGUOUS_ITEM" if len(candidates) > 1 else "UNKNOWN_ITEM")
    if supply is not None and supply != raw["amount"] and edits.get("confirmed_amount") != supply:
        issues.append("AMOUNT_MISMATCH")
    excluded = bool(edits.get("exclude_reason"))
    return {"id": row["id"], "source": row["source"],
            "original": {key: text(value) if isinstance(value, Decimal) else value for key, value in raw.items()},
            "item_code": selected, "item_registered": bool(item and item.get("registered")), "name": item["name"] if item else name, "unit": item["unit"] if edits.get("item_code") else raw["unit"],
            "quantity": text(count), "price": text(price), "supply": text(supply), "vat": text(vat),
            "total": text(supply + vat) if supply is not None else None,
            "due": raw["due"], "status": "excluded" if excluded else "review" if issues else "accepted",
            "issues": [{"code": key, "message": MESSAGES[key]} for key in issues],
            "candidates": candidates, "restored": restored, "restored_only": restored and edits == {"restored": True}, "exclude_reason": edits.get("exclude_reason", ""), "audit": row["audit"]}


def apply_review(row, master, action):
    if len(row["audit"]) >= 30:
        raise ReviewError("한 행의 변경 한도에 도달했습니다. 체험을 다시 시작해 주세요.")
    canceled = is_canceled(row) and not row["edits"].get("restored")
    if action["action"] == "restore":
        if not canceled:
            raise ReviewError("취소된 주문만 취소 철회할 수 있습니다.")
        # Restored rows go through the same matching/validation as any other order row.
        row["edits"] = {"restored": True}
        row["audit"].append({"action": "restore", "order_status": row["raw"]["order_status"]})
        return
    if canceled:
        raise ReviewError("취소 주문입니다. 먼저 취소 철회를 해 주세요.")
    if action["action"] == "reset":
        # Undo review edits first; a restored order with no other edits goes back to canceled.
        restored_only = row["edits"] == {"restored": True}
        row["edits"] = {} if restored_only or not row["edits"].get("restored") else {"restored": True}
        row["audit"].append({"action": "undo_restore" if restored_only else "reset"})
        return
    keep = {"restored": True} if row["edits"].get("restored") else {}
    if action["action"] == "exclude":
        reason = (action.get("reason") or "").strip()
        if len(reason) < 3:
            raise ReviewError("제외 사유를 세 글자 이상 입력해 주세요.")
        row["edits"] = {**keep, "exclude_reason": reason}
        row["audit"].append({"action": "exclude", "reason": reason})
        return
    # Work on a copy so rejected validation never partially updates the session.
    edits = {key: value for key, value in row["edits"].items() if key not in ("exclude_reason", "confirmed_amount")}
    if action["action"] == "register":
        if "UNKNOWN_ITEM" not in [i["code"] for i in evaluate(dict(row, edits=edits), master)["issues"]]:
            raise ReviewError("마스터에 없는 품목 행에서만 신규 품목을 등록할 수 있습니다.")
        item = new_item(master, action)
        master[item["code"]] = item
        edits["item_code"] = item["code"]
        row["edits"] = edits
        row["audit"].append({"action": "register", "item_code": item["code"], "name": item["name"],
                             "unit": item["unit"], "price": text(item["price"]), "quantity": text(edits.get("quantity"))})
        return
    if action.get("quantity") is not None:
        edits["quantity"] = quantity(action["quantity"])
    if action.get("item_code") is not None:
        if action["item_code"] not in master:
            raise ReviewError("마스터의 품목을 선택해 주세요.")
        edits["item_code"] = action["item_code"]
    preview = evaluate(dict(row, edits=edits), master)
    if action.get("confirmed_amount") is not None:
        supplied = action["confirmed_amount"]
        if supplied != preview["supply"] or preview["supply"] is None:
            raise ReviewError("현재 계산 금액과 확인한 금액이 다릅니다. 다시 검증해 주세요.")
        edits["confirmed_amount"] = Decimal(supplied)
    row["edits"] = edits
    row["audit"].append({"action": "resolve", "quantity": text(edits.get("quantity")),
                         "item_code": edits.get("item_code"), "confirmed_amount": text(edits.get("confirmed_amount"))})


def order_view(order, master):
    rows = [evaluate(row, master) for row in order["rows"]]
    accepted = [row for row in rows if row["status"] == "accepted"]
    review = sum(row["status"] == "review" for row in rows)
    groups = {}
    for row in accepted:
        key = (row["item_code"], row["unit"], Decimal(row["price"]), row["due"]) if order["sample"] == "B" else (row["id"],)
        if key not in groups:
            groups[key] = {"id": f"{order['sample']}-{len(groups)+1:02}", "item_code": row["item_code"], "name": row["name"],
                           "unit": row["unit"], "price": row["price"], "due": row["due"], "quantity": Decimal(0), "supply": Decimal(0), "sources": []}
        group = groups[key]
        group["quantity"] += Decimal(row["quantity"])
        group["supply"] += Decimal(row["supply"])
        group["sources"].append(row["source"])
    lines = []
    for group in groups.values():
        group["vat"] = money(group["supply"] * Decimal("0.10"))
        group["total"] = group["supply"] + group["vat"]
        lines.append({key: text(value) if isinstance(value, Decimal) else value for key, value in group.items()})
    totals = {key: text(sum((Decimal(line[key]) for line in lines), Decimal(0))) for key in ("supply", "vat", "total")}
    return {key: value for key, value in order.items() if key != "rows"} | {
        "rows": rows, "accepted": len(accepted), "review": review,
        "lines": lines, "canceled": sum(row["status"] == "canceled" for row in rows),
        "excluded": sum(row["status"] == "excluded" for row in rows),
        "ready": review == 0 and bool(accepted), "totals": totals}


def export_order(order, master, data=DATA):
    view = order_view(order, master)
    if not view["ready"]:
        raise ReviewError("미해결 행이 있거나 확정 행이 없어 최종 발행할 수 없습니다.")
    dates = sorted({line["due"] for line in view["lines"]})
    main = {"B4": view["customer"], "E4": f"DEMO-{view['sample']}-검수완료", "B5": view["ordered"], "E5": dates[0] if len(dates) == 1 else "납기별내역 시트 참조",
            "B6": f"검수 완료 / 제외 {view['excluded']}행 / 체험용 가상 문서"}
    tracking = {}
    numbers = {}
    formulas = {}
    by_id = {row["id"]: row for row in view["rows"]}
    if order["sample"] == "B":
        main["B7"] = "공급가액: 원본 행별 반올림 후 취합 / 부가세: 출력 행별 반올림"
    detail = [["체험용 가상 데이터 — 납기별 내역"], ["실제 거래용이 아닙니다. 모든 납기는 원본 기준입니다."], [],
              ["순번", "품목코드", "표준품명", "단위", "수량", "단가", "공급가액", "부가세", "합계", "요청납기"]]
    for output_number, line in enumerate(view["lines"], 1):
        excel_row = 9 + output_number
        values = [output_number, code_label(master, line["item_code"]), line["name"], line["unit"], Decimal(line["quantity"]),
                  Decimal(line["price"]), Decimal(line["supply"]), Decimal(line["vat"]), Decimal(line["total"])]
        main.update({f"{chr(65 + column)}{excel_row}": value for column, value in enumerate(values)})
        if order["sample"] == "B" and len(line["sources"]) > 1:
            terms = [f"ROUND({by_id[s['row']]['quantity']}*{by_id[s['row']]['price']},0)" for s in line["sources"]]
            formulas[f"G{excel_row}"] = "SUM(" + ",".join(terms) + ")"
        detail.append([*values, line["due"]])
        for origin in line["sources"]:
            numbers[origin["row"]] = output_number
    for index, row in enumerate(view["rows"], 5):
        provenance = {"source_cells": row["source"]["cells"], "original": row["original"],
                      "supply": row["supply"], "due": row["due"], "exclude_reason": row["exclude_reason"], "audit": row["audit"]}
        values = [numbers.get(row["id"], "제외"), row["source"]["file"],
                  row["source"]["sheet"], row["source"]["row"], ("검수 완료 · 취소 철회" if row["restored"] else "검수 완료") if row["status"] == "accepted" else "취소 제외" if row["status"] == "canceled" else "사유 기재 제외",
                  ", ".join(i["code"] for i in row["issues"]), json.dumps(provenance, ensure_ascii=False)]
        tracking.update({f"{chr(65 + column)}{index}": value for column, value in enumerate(values)})
    main.update({"G31": Decimal(view["totals"]["supply"]), "H31": Decimal(view["totals"]["vat"]), "I31": Decimal(view["totals"]["total"])})
    additions = {"납기별내역": detail}
    registered = sorted({line["item_code"] for line in view["lines"] if master[line["item_code"]].get("registered")})
    if registered:
        additions["신규등록품목"] = [["체험 중 신규 등록한 품목 — 마스터 반영 전 확인용"],
            ["이 시트의 품목은 체험 세션에만 존재하며 item_master.csv에는 저장되지 않습니다."],
            ["품목코드", "표준명", "단위", "기준단가", "원본 행"],
            *[["미정 (코드 부여 필요)" if master[code]["pending"] else code, master[code]["name"], master[code]["unit"], master[code]["price"],
               ", ".join(str(r["id"]) for r in view["rows"] if r["item_code"] == code and r["status"] == "accepted")] for code in registered]]
    if order["layout_rows"]:
        additions["비주문행기록"] = [["체험용 가상 데이터 — 주문에서 제외한 레이아웃 행"],
            ["원본 파일", "시트", "행", "분류", "원본 표기"],
            *[[order["filename"], order["sheet"], r["row"], r["kind"], r["label"]] for r in order["layout_rows"]]]
    return fill_template(data / "common_delivery_statement_template.xlsx",
                         {"xl/worksheets/sheet1.xml": main, "xl/worksheets/sheet2.xml": tracking}, additions,
                         {"xl/worksheets/sheet1.xml": formulas})
