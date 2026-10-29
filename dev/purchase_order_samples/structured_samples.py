"""Three deliberately different authoring/export paths for fictional fixtures."""
from decimal import Decimal, ROUND_HALF_UP
import json

from xlsx_fixture import col, workbook

SHEETS = {"A": "인쇄발주서", "B": "orders_export", "C": "구매발주서"}
HEADERS = {
    "A": ["번호", "품목코드", "품명", "규격", "단위", "수량", "단가", "공급가액"],
    "B": ["주문번호", "주문일시", "주문상태", "판매상품번호", "상품명", "옵션", "수량", "판매단가", "상품금액", "단위", "가상구매처", "가상담당자", "회신주소", "요청납기", "데이터구분", "결제수단", "판매채널"],
    "C": ["번호", "구매품번", "품목명", "규격", "단위", "수량", "단가", "공급가액", "요청납기", "비고"],
}
MAPPING = {
    "A": {"code": "B", "name": "C", "spec": "D", "unit": "E", "quantity": "F", "unit_price": "G", "stated_amount": "H"},
    "B": {"order_id": "A", "ordered": "B", "status": "C", "vendor_sku": "D", "name": "E", "spec": "F", "quantity": "G", "unit_price": "H", "stated_amount": "I", "unit": "J"},
    "C": {"vendor_sku": "B", "name": "C", "spec": "D", "unit": "E", "quantity": "F", "unit_price": "G", "stated_amount": "H", "due": "I", "note": "J"},
}


def entry(row, item, qty, *, issue=None, amount=None, name=None, spec="", price=None, code=None, canceled=False):
    return {"row": row, "item": item, "quantity": qty, "issue": issue, "amount": amount,
            "name": name, "spec": spec, "price": price, "code": code, "canceled": canceled}


def definitions():
    return {
        "A": [entry(12, "S001", "2", spec="80g / 2,500매"), entry(13, "S002", "1", spec="180ml"),
              entry(14, "S010", "10", spec="48mm"), entry(15, "S009", None, issue="MISSING_QUANTITY", amount=9000, spec="100매"),
              entry(16, "S007", "2", spec="6롤"), entry(17, "S012", "3", spec="10매"),
              entry(18, "S014", "2", spec="500ml"), entry(19, "S006", "3", issue="AMOUNT_MISMATCH", amount=13000, spec="1L"),
              entry(20, "S011", "2", spec="중형"), entry(21, "S015", "4", spec="5개")],
        "B": [entry(2, "S009", "3", name="청소물티슈", spec="100매 / 낱팩"),
              entry(3, "S010", "2", name="박스테이프", spec="48mm"),
              entry(4, "S009", "5", name="청소물티슈", spec="100매 / 낱팩"),
              entry(5, None, "2", name="위생장갑", price=8000, canceled=True),
              entry(6, "S014", "2", name="손세정제500", spec="500ml"),
              entry(7, "S003", "2", name="위생장갑", spec="M"),
              entry(8, "S009", "4", name="청소물티슈", spec="100매 / 낱팩"),
              entry(9, None, "1", name="위생장갑", price=8000, issue="AMBIGUOUS_ITEM"),
              entry(10, "S010", "3", name="박스테이프", spec="48mm"),
              entry(11, None, "1", name="가상 포장필름", price=9900, canceled=True),
              entry(12, "S013", "6", name="소독솜100", spec="100매"),
              entry(13, None, "2", name="가상 정전기제거패드", price=6900, issue="UNKNOWN_ITEM"),
              entry(14, "S014", "3", name="손세정제500", spec="500ml"),
              entry(15, "S011", "4", name="중형지퍼백", spec="중형"),
              entry(16, "S013", "2", name="소독솜100", spec="100매"),
              entry(17, "S009", "10", name="청소물티슈", canceled=True),
              entry(18, "S011", "1", name="중형지퍼백", spec="중형"),
              entry(19, "S003", "1", name="위생장갑", spec="M")],
        "C": [entry(12, "S005", "2.75", name="다목적세정제", spec="원액"),
              entry(13, "S006", "6", name="주방세제", spec="1L"),
              entry(15, None, "2", name="가상 내열필터", spec="HT-01", price=18000, issue="UNKNOWN_ITEM"),
              entry(16, "S012", "2", name="행주", spec="10매"),
              entry(17, "S015", "5", name="스펀지 수세미", spec="5개"),
              entry(19, "S003", "3", name="니트릴장갑", spec="M"),
              entry(20, "S004", "2", name="니트릴장갑", spec="L"),
              entry(21, "S013", None, name="알코올솜", spec="100매", amount=8400, issue="MISSING_QUANTITY"),
              entry(23, "S014", "4", name="핸드워시", spec="500ml"),
              entry(24, "S009", "6", name="물티슈", spec="100매", amount=10000, issue="AMOUNT_MISMATCH"),
              entry(25, "S016", "1", name="마스크", spec="KF94 50매")],
    }


def number(value):
    if value is None:
        return None
    d = Decimal(value)
    return int(d) if d == d.to_integral() else str(d)


def rounded(value):
    return value.quantize(Decimal(1), rounding=ROUND_HALF_UP)


def prepare(case, entries, master):
    result = []
    for index, row in enumerate(entries, 1):
        item = master.get(row["item"])
        price = Decimal(row["price"] if row["price"] is not None else item[4])
        qty = None if row["quantity"] is None else Decimal(row["quantity"])
        amount = Decimal(row["amount"]) if row["amount"] is not None else rounded(qty * price)
        unit = item[3] if item else ("박스" if row["name"] == "위생장갑" else "개")
        raw = {"name": row["name"] or item[1], "spec": row["spec"] or None, "unit": unit,
               "quantity": qty, "unit_price": price, "stated_amount": amount}
        if case == "A":
            raw["code"] = row["item"]
        elif case == "B":
            raw.update(order_id=f"DEMO-SHOP-{1000 + index}", ordered=f"2026-11-02 {8 + index // 4:02}:{index % 4 * 12:02}:00",
                       status=("취소완료" if row["row"] == 17 else "취소") if row["canceled"] else "결제완료",
                       vendor_sku="SHOP-" + (row["item"] or f"UNLISTED-{index:02}"))
        else:
            raw.update(vendor_sku=f"RM-DEMO-{index:03}", due="2026-11-09" if row["row"] < 18 else "2026-11-12",
                       note="원액 기준 계량" if row["item"] == "S005" else "생산동 입고 / 가상")
        result.append(dict(row, raw=raw))
    return result


def source(case, row):
    return {"file": f"purchase_order_{case}.xlsx", "sheet": SHEETS[case], "row": row,
            "cells": {key: f"{column}{row}" for key, column in MAPPING[case].items()}}


def expected(case, rows, master, notice, layout):
    ledger, issues, canceled, output = [], [], [], []
    grouped = {}
    for row in rows:
        raw = row["raw"]
        origin = source(case, row["row"])
        calculated = None if raw["quantity"] is None else rounded(raw["quantity"] * raw["unit_price"])
        decision = "취소 제외" if row["canceled"] else "확인 필요" if row["issue"] else "확정 가능"
        ledger.append({"source": origin, "input": {key: number(value) if isinstance(value, Decimal) else value for key, value in raw.items()},
                       "decision": decision, "issue_codes": [row["issue"]] if row["issue"] else [],
                       "calculated_amount": number(calculated), "output_group": None})
        if row["canceled"]:
            canceled.append({"source": origin, "reason": raw["status"], "matching_skipped": True})
        elif row["issue"]:
            candidates = ["S003", "S004"] if row["issue"] == "AMBIGUOUS_ITEM" else []
            issues.append({"source": origin, "code": row["issue"], "intentional": True, "expected_decision": "확인 필요",
                           "candidate_item_codes": candidates, "calculated_amount": number(calculated),
                           "stated_amount": number(raw["stated_amount"]),
                           "difference": number(raw["stated_amount"] - calculated) if calculated is not None else None})
        else:
            item = master[row["item"]]
            # B aggregates only accepted source rows with the same master code/unit/price.
            key = (item[0], item[3], raw["unit_price"]) if case == "B" else (row["row"],)
            if key not in grouped:
                group = {"group_id": f"{case}-{len(output) + 1:02}", "item_code": item[0], "standard_name": item[1],
                         "unit": item[3], "quantity": Decimal(0), "unit_price": raw["unit_price"],
                         "supply_amount": Decimal(0), "sources": []}
                grouped[key] = group
                output.append(group)
            group = grouped[key]
            group["quantity"] += raw["quantity"]
            group["supply_amount"] += calculated
            group["sources"].append(origin)
            ledger[-1]["output_group"] = group["group_id"]
    for group in output:
        group["vat"] = rounded(group["supply_amount"] * Decimal("0.10"))
        group["total_amount"] = group["supply_amount"] + group["vat"]
    totals = {key: number(sum((group[key] for group in output), Decimal(0))) for key in ("supply_amount", "vat", "total_amount")}
    for group in output:
        for key in ("quantity", "unit_price", "supply_amount", "vat", "total_amount"):
            group[key] = number(group[key])
    result = {"schema_version": 2, "demo_notice": notice, "sample": case, "source_file": f"purchase_order_{case}.xlsx",
              "source_sheet": SHEETS[case], "column_mapping": MAPPING[case],
              "layout_rows": [{"source": {"file": f"purchase_order_{case}.xlsx", "sheet": SHEETS[case], "row": n}, "kind": kind}
                              for n, kind in layout.items()],
              "processing_rules": {"cancellation_before_matching": case == "B", "aggregate": "item_code+unit+unit_price" if case == "B" else "none",
                                   "spec_matching": "unique name+spec first, then name; never choose by price",
                                   "money": "KRW, Decimal, supply rounded per source row; VAT 10% ROUND_HALF_UP per output line",
                                   "review_rows_in_totals": False},
              "summary": {"order_rows": len(rows), "accepted_source_rows": sum(r["decision"] == "확정 가능" for r in ledger),
                          "review_rows": len(issues), "canceled_rows": len(canceled), "output_lines": len(output),
                          **totals, "status": "검수 전 부분 합계 / 최종 발행 보류"},
              "rows": ledger, "accepted_output_lines": output, "excluded_orders": canceled}
    return result, {"schema_version": 2, "demo_notice": notice, "intentional_errors": issues,
                    "excluded_orders": canceled, "generation_errors": []}


def style_table(cells, first, last, width):
    return {f"{col(c)}{r}": 13 if isinstance(cells[r][c - 1], (int, Decimal)) else 12
            for r in range(first, last + 1) for c in range(1, width + 1) if r in cells and c <= len(cells[r])}


def build_a(rows, notice):
    cells = {1: ["NU", None, "(가상)누리문구"], 2: [None, None, "소형 거래처 정기 발주 · 체험용 가상 데이터"],
             3: [None, None, "가상담당A · buyer-a@example.invalid"], 5: ["발  주  서"],
             7: ["문서번호", None, "DEMO-A-20261102", None, "발주일", None, "2026-11-02"],
             8: ["공급처", None, "(가상)모아소모품 도매", None, "납기", None, "2026-11-05"],
             9: ["요청담당", None, "가상담당A", None, "금액기준", None, "KRW / VAT 별도"],
             11: HEADERS["A"], 23: ["기재 금액 단순 합계 (검수 전)", None, None, None, None, None, None, None],
             24: ["정산 금액이 아닙니다. 누락 수량과 금액 차이를 확인한 뒤 발행하세요."],
             26: ["요청사항", "분할 납품 시 사전 회신 바랍니다. (가상 요청)"],
             27: [None, "입고 확인 후 수령 서명 · 모든 거래 정보는 가상입니다."],
             29: ["요청: 가상담당A", None, None, None, "수령 확인란 (체험용)"],
             31: [notice]}
    for i, row in enumerate(rows, 1):
        r = row["raw"]
        cells[row["row"]] = [i, r["code"], r["name"], r["spec"], r["unit"], r["quantity"], r["unit_price"], r["stated_amount"]]
    styles = style_table(cells, 11, 21, 8)
    styles.update({f"{col(c)}11": 3 for c in range(1, 9)})
    styles.update({"A1": 10, "C1": 14, "C2": 0, "C3": 0, "A5": 1, "A23": 9, "H23": 9, "A31": 2})
    for r in (7, 8, 9):
        styles.update({f"A{r}": 11, f"C{r}": 12, f"E{r}": 11, f"G{r}": 12})
    return [{"name": SHEETS["A"], "cells": cells, "styles": styles, "header_rows": [11], "freeze": 11,
             "widths": [6, 12, 24, 17, 8, 10, 14, 17], "row_height": 23,
             "heights": {1: 30, 2: 23, 3: 23, 5: 38, 24: 32, 26: 30, 27: 30, 31: 34},
             "merges": ["A1:B3", "C1:H1", "C2:H2", "C3:H3", "A5:H5", "A7:B7", "C7:D7", "E7:F7", "G7:H7",
                        "A8:B8", "C8:D8", "E8:F8", "G8:H8", "A9:B9", "C9:D9", "E9:F9", "G9:H9",
                        "A23:G23", "A24:H24", "B26:H26", "B27:H27", "A29:D29", "E29:H29", "A31:H31"],
             "formulas": {"H23": "SUM(H12:H21)"}, "formula_values": {"H23": sum(r["raw"]["stated_amount"] for r in rows)},
             "orientation": "portrait", "fit_height": 1, "print_area": "$A$1:$H$31"}]


def build_b(rows, notice):
    cells = {1: HEADERS["B"]}
    for row in rows:
        r = row["raw"]
        cells[row["row"]] = [r["order_id"], r["ordered"], r["status"], r["vendor_sku"], r["name"], r["spec"],
                             r["quantity"], r["unit_price"], r["stated_amount"], r["unit"], "(가상)데모쇼핑몰 B", "가상운영B",
                             "buyer-b@example.invalid", "2026-11-06", "체험용 가상 데이터", "가상 카드결제", "DEMO-MALL"]
    return [{"name": SHEETS["B"], "cells": cells, "raw": True, "header_rows": [1], "freeze": 1,
             "row_height": 20, "filter": "A1:Q19", "fit_width": 0, "fit_height": 0, "print_area": "$A$1:$Q$19",
             "widths": [25, 23, 14, 23, 27, 23, 10, 14, 16, 9, 27, 16, 32, 16, 27, 20, 18]},
            {"name": "export_info", "raw": True, "cells": {1: ["field", "value"], 2: ["data_notice", notice],
             3: ["exported_at", "2026-11-02 14:00:00"], 4: ["source", "가상 쇼핑몰 관리자 > 주문 내역 내려받기"],
             5: ["amount_policy", "KRW / 세전 상품금액 / 배송비와 할인 없음"],
             6: ["contact", "가상운영B / buyer-b@example.invalid"]}, "widths": [24, 100], "header_rows": [1], "freeze": 1}]


def build_c(rows, notice):
    cells = {1: ["(가상)모듈제조", None, None, None, "구매 발주서"],
             2: [None, None, None, None, "PURCHASE ORDER / 체험용 가상 데이터"],
             4: ["발주번호", "DEMO-MFG-C-1102", None, None, None, "구매담당", "가상구매C"],
             5: ["발주일", "2026-11-02", None, None, None, "회신주소", "buyer-c@example.invalid"],
             6: ["공급업체", "(가상)모아소모품 도매", None, None, None, "납품 장소", "가상 생산동 자재 입고장"],
             8: ["입고 조건", "품목별 요청 납기 준수 / 단위·규격 확인 후 입고 (가상)"],
             10: HEADERS["C"], 11: ["01 / 생산라인 청소·포장"], 14: [None] * 10,
             18: ["02 / 작업자 위생·소모품"], 22: [None] * 10,
             26: ["소계 (기재 공급가액)", None, None, None, None, None, None, None, None, None],
             27: [None] * 10, 28: ["총 발주 기재액 (검수 전)", None, None, None, None, None, None, None, None, None],
             29: ["구분행·빈 행·합계행은 품목이 아닙니다. 검수 전 합계는 최종 정산 금액이 아닙니다."],
             31: [notice]}
    for index, row in enumerate(rows, 1):
        r = row["raw"]
        cells[row["row"]] = [index, r["vendor_sku"], r["name"], r["spec"], r["unit"], r["quantity"], r["unit_price"], r["stated_amount"], r["due"], r["note"]]
    styles = style_table(cells, 10, 28, 10)
    styles.update({f"{col(c)}10": 3 for c in range(1, 11)})
    styles.update({"A1": 14, "A2": 0, "E1": 1, "E2": 0, "A11": 8, "A18": 8,
                   "A26": 9, "H26": 9, "A28": 9, "H28": 9, "A29": 0, "A31": 2})
    for r in (4, 5, 6):
        styles.update({f"A{r}": 11, f"B{r}": 12, f"F{r}": 11, f"G{r}": 12})
    item_rows = [r["row"] for r in rows]
    formula = "+".join(f"H{r}" for r in item_rows)
    amount = sum(r["raw"]["stated_amount"] for r in rows)
    return [{"name": SHEETS["C"], "cells": cells, "styles": styles, "header_rows": [10], "freeze": 10,
             "row_height": 24, "heights": {1: 32, 2: 26, 11: 27, 14: 10, 18: 27, 22: 10, 27: 10, 29: 30, 31: 35},
             "widths": [12, 20, 24, 16, 8, 11, 13, 17, 18, 29],
             "merges": ["A1:D2", "E1:J1", "E2:J2", "B4:E4", "G4:J4", "B5:E5", "G5:J5", "B6:E6", "G6:J6",
                        "B8:J8", "A11:J11", "A18:J18", "A26:G26", "A28:G28", "A29:J29", "A31:J31"],
             "formulas": {"H26": formula, "H28": "H26"}, "formula_values": {"H26": amount, "H28": amount},
             "orientation": "landscape", "fit_height": 1, "print_area": "$A$1:$J$31"}]


def build_all(public, dev, master_rows, notice):
    master = {row[0]: row for row in master_rows}
    builders = {"A": build_a, "B": build_b, "C": build_c}
    for case, definitions_rows in definitions().items():
        rows = prepare(case, definitions_rows, master)
        layout = {11: "section", 14: "blank", 18: "section", 22: "blank", 26: "subtotal", 27: "blank", 28: "total"} if case == "C" else {}
        workbook(public / f"purchase_order_{case}.xlsx", builders[case](rows, notice), f"체험용 가상 발주서 {case}")
        expected_doc, errors = expected(case, rows, master, notice, layout)
        (dev / "expected").mkdir(parents=True, exist_ok=True)
        for suffix, document in (("expected", expected_doc), ("errors", errors)):
            (dev / "expected" / f"{case}.{suffix}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
