"""Independent read-back and financial controls; never imports fixture definitions."""
from collections import defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import json

CONTROL = {
    "A": {"sheet": "인쇄발주서", "header": 11, "rows": list(range(12, 22)), "accepted": 8, "output": 8, "supply": 122400,
          "issues": {15: "MISSING_QUANTITY", 19: "AMOUNT_MISMATCH"}, "canceled": [],
          "headers": ["번호", "품목코드", "품명", "규격", "단위", "수량", "단가", "공급가액"],
          "map": {"code": "B", "name": "C", "spec": "D", "unit": "E", "quantity": "F", "unit_price": "G", "stated_amount": "H"}},
    "B": {"sheet": "orders_export", "header": 1, "rows": list(range(2, 20)), "accepted": 13, "output": 6, "supply": 110500,
          "issues": {9: "AMBIGUOUS_ITEM", 13: "UNKNOWN_ITEM"}, "canceled": [5, 11, 17],
          "headers": ["주문번호", "주문일시", "주문상태", "판매상품번호", "상품명", "옵션", "수량", "판매단가", "상품금액", "단위", "가상구매처", "가상담당자", "회신주소", "요청납기", "데이터구분", "결제수단", "판매채널"],
          "map": {"order_id": "A", "ordered": "B", "status": "C", "vendor_sku": "D", "name": "E", "spec": "F", "quantity": "G", "unit_price": "H", "stated_amount": "I", "unit": "J"}},
    "C": {"sheet": "구매발주서", "header": 10, "rows": [12, 13, 15, 16, 17, 19, 20, 21, 23, 24, 25], "accepted": 8, "output": 8, "supply": 126000,
          "issues": {15: "UNKNOWN_ITEM", 21: "MISSING_QUANTITY", 24: "AMOUNT_MISMATCH"}, "canceled": [],
          "headers": ["번호", "구매품번", "품목명", "규격", "단위", "수량", "단가", "공급가액", "요청납기", "비고"],
          "map": {"vendor_sku": "B", "name": "C", "spec": "D", "unit": "E", "quantity": "F", "unit_price": "G", "stated_amount": "H", "due": "I", "note": "J"}},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dec(value):
    return None if value is None else Decimal(str(value))


def rounded(value):
    return value.quantize(Decimal(1), rounding=ROUND_HALF_UP)


def check(public, dev, read):
    with (public / "item_master.csv").open(encoding="utf-8-sig", newline="") as file:
        records = list(csv.DictReader(file))
    master = {r["품목코드"]: r for r in records}
    require(len(master) == len(records) == 16, "마스터 품목 수/중복 오류")
    aliases = defaultdict(set)
    for code, item in master.items():
        require(item["데이터구분"] == "체험용 가상 데이터" and dec(item["기준단가"]) > 0, "마스터 고지/단가 오류")
        for alias in [item["표준명"], *item["별칭"].split("|")]:
            aliases[alias].add(code)
    require(aliases["위생장갑"] == {"S003", "S004"}, "모호한 별칭 후보 유지 필요")
    require({key for key, codes in aliases.items() if len(codes) > 1} == {"위생장갑"}, "의도 외 중복 별칭")
    results = []
    for case, control in CONTROL.items():
        filename = f"purchase_order_{case}.xlsx"
        book = read(public / filename)
        sheet = book[control["sheet"]]
        cells = sheet["cells"]
        expected = json.loads((dev / "expected" / f"{case}.expected.json").read_text(encoding="utf-8"))
        errors = json.loads((dev / "expected" / f"{case}.errors.json").read_text(encoding="utf-8"))
        require(expected["schema_version"] == 2, "기대 결과 v2 필요")
        actual_header = [cells.get(f"{chr(65 + i)}{control['header']}") for i in range(len(control["headers"]))]
        require(actual_header == control["headers"], f"{case}: 열 이름/구조 오류")
        require(expected["column_mapping"] == control["map"], f"{case}: 매핑 오류")
        require(len(expected["rows"]) == len(control["rows"]), f"{case}: 주문 행 수 오류")
        if case == "A":
            require("A1:B3" in sheet["merges"] and len(sheet["merges"]) >= 15, "A: 로고/메타데이터 병합 누락")
            require(sheet["orientation"] == "portrait" and sheet["fit_height"] == "1" and sheet["print_area"].endswith("$A$1:$H$31"), "A: 한 페이지 인쇄 설정 오류")
            require(cells["C7"] == "DEMO-A-20261102" and cells["G8"] == "2026-11-05", "A: 문서번호/납기 오류")
            require(sheet["formulas"]["H23"] == "SUM(H12:H21)" and cells["H23"] == 144400, "A: 원본 기재 합계 오류")
            require("요청" in str(cells["A26"]), "A: 요청사항 누락")
        elif case == "B":
            require(sheet["merges"] == [] and sheet["filter"] == "A1:Q19", "B: 원시 데이터 표 구조 오류")
            require(not sheet["formulas"] and "export_info" in book, "B: 원시 표/내보내기 정보 오류")
            require(all(cells[f"O{row}"] == "체험용 가상 데이터" for row in control["rows"]), "B: 행별 가상 고지 누락")
        else:
            numeric_rows = [row for row in range(11, 29) if isinstance(cells.get(f"A{row}"), Decimal)]
            require(numeric_rows == control["rows"], "C: 실제 주문행 식별 오류")
            layout = {11: "section", 14: "blank", 18: "section", 22: "blank", 26: "subtotal", 27: "blank", 28: "total"}
            require({r["source"]["row"]: r["kind"] for r in expected["layout_rows"]} == layout, "C: 구분/빈/합계행 기대 결과 오류")
            require(all(r["source"]["file"] == filename and r["source"]["sheet"] == control["sheet"] for r in expected["layout_rows"]), "C: 비주문행 원본 추적 오류")
            require(all(cells.get(f"{chr(65 + i)}{r}") is None for r in (14, 22, 27) for i in range(10)), "C: 빈 행 오류")
            require(cells["A11"].startswith("01 /") and cells["A18"].startswith("02 /") and cells["A26"].startswith("소계"), "C: 구분행/소계 표기 오류")
            require(cells["F12"] == Decimal("2.75") and cells["C19"] == "니트릴장갑" and cells["D19"] == "M", "C: 소수 수량/규격 분리 오류")
            require(cells["H26"] == cells["H28"] == 180400 and sheet["formulas"]["H28"] == "H26", "C: 합계행 오류")
            require(sheet["formulas"]["H26"] == "+".join(f"H{r}" for r in control["rows"]), "C: 합계 수식에 구분/빈/합계행이 섞이면 안 됨")
        groups = {}
        review_count = accepted_count = canceled_count = 0
        seen_sources = []
        actual_issues = []
        for row, expected_row in zip(control["rows"], expected["rows"]):
            source = {"file": filename, "sheet": control["sheet"], "row": row,
                      "cells": {key: f"{column}{row}" for key, column in control["map"].items()}}
            raw = {key: cells.get(f"{column}{row}") for key, column in control["map"].items()}
            if case == "B":
                require(raw["vendor_sku"] not in master, "B: 판매상품번호를 내부 품목코드와 혼동하면 안 됨")
            require(expected_row["source"] == source, f"{case}:{row}: 원본 추적 오류")
            for key, value in raw.items():
                expected_value = expected_row["input"][key]
                require(value == (dec(expected_value) if key in ("quantity", "unit_price", "stated_amount") else expected_value), f"{case}:{row}: {key} 값 오류")
            calculated = None if raw["quantity"] is None else rounded(raw["quantity"] * raw["unit_price"])
            require(dec(expected_row["calculated_amount"]) == calculated, f"{case}:{row}: 검산 오류")
            if row in control["canceled"]:
                require(raw["status"] in ("취소", "취소완료") and expected_row["decision"] == "취소 제외", f"B:{row}: 취소 제외 오류")
                require(expected_row["issue_codes"] == [] and expected_row["output_group"] is None, "취소 주문은 매칭·오류 처리·취합에서 제외")
                canceled_count += 1
                continue
            require(raw.get("status", "결제완료") == "결제완료", "취소 상태를 정상 처리하면 안 됨")
            code = raw.get("code")
            combined = " ".join(str(raw[k] or "").strip() for k in ("name", "spec")).strip()
            candidates = {code} if code in master else set() if code else aliases.get(combined) or aliases.get(raw["name"], set())
            issues = []
            if raw["quantity"] is None:
                issues.append("MISSING_QUANTITY")
            if not candidates:
                issues.append("UNKNOWN_ITEM")
            elif len(candidates) > 1:
                issues.append("AMBIGUOUS_ITEM")
            if calculated is not None and calculated != raw["stated_amount"]:
                issues.append("AMOUNT_MISMATCH")
            planted = [control["issues"][row]] if row in control["issues"] else []
            require(issues == planted == expected_row["issue_codes"], f"{case}:{row}: 의도 외 오류 {issues}")
            if issues:
                require(expected_row["decision"] == "확인 필요" and expected_row["output_group"] is None, "검수 행 임의 확정 금지")
                error = next(e for e in errors["intentional_errors"] if e["source"]["row"] == row)
                require(error["source"] == source and error["code"] == issues[0] and error["intentional"] is True, "오류 위치/종류 오류")
                require(error["expected_decision"] == "확인 필요", "오류 기대 판정 오류")
                require(dec(error["calculated_amount"]) == calculated and dec(error["stated_amount"]) == raw["stated_amount"], "오류 금액 기록 불일치")
                require(dec(error["difference"]) == (raw["stated_amount"] - calculated if calculated is not None else None), "금액 차액 오류")
                if issues == ["AMBIGUOUS_ITEM"]:
                    require(sorted(candidates) == error["candidate_item_codes"] == ["S003", "S004"], "가격으로 모호한 품목을 확정하면 안 됨")
                review_count += 1
                actual_issues.append({"row": row, "code": issues[0]})
                continue
            require(expected_row["decision"] == "확정 가능", "정상 행 판정 오류")
            code = next(iter(candidates))
            item = master[code]
            require(raw["unit"] == item["단위"] and raw["unit_price"] == dec(item["기준단가"]), "의도 외 단위/단가 오류")
            key = (code, raw["unit"], raw["unit_price"]) if case == "B" else (row,)
            if key not in groups:
                groups[key] = {"code": code, "quantity": Decimal(0), "supply": Decimal(0), "price": raw["unit_price"], "sources": [], "id": expected_row["output_group"]}
            group = groups[key]
            require(group["id"] == expected_row["output_group"], "취합 그룹 연결 오류")
            group["quantity"] += raw["quantity"]
            group["supply"] += calculated
            group["sources"].append(source)
            seen_sources.append(row)
            accepted_count += 1
        require((accepted_count, review_count, canceled_count, len(groups)) == (control["accepted"], len(control["issues"]), len(control["canceled"]), control["output"]), f"{case}: 판정/취합 개수 오류")
        require(len(errors["intentional_errors"]) == review_count and errors["generation_errors"] == [], "의도적 오류/생성 오류 구분 실패")
        require([e["source"]["row"] for e in expected["excluded_orders"]] == control["canceled"], "취소 추적 누락")
        require(errors["excluded_orders"] == expected["excluded_orders"] and all(e["matching_skipped"] for e in errors["excluded_orders"]), "취소는 검수 전 제외해야 함")
        require(len(expected["accepted_output_lines"]) == len(groups), "출력 품목 수 오류")
        supply = vat = Decimal(0)
        flattened = []
        for group, output in zip(groups.values(), expected["accepted_output_lines"]):
            line_vat = rounded(group["supply"] * Decimal("0.10"))
            require(output["item_code"] == group["code"] and output["standard_name"] == master[group["code"]]["표준명"], "마스터 표준화 오류")
            require(output["sources"] == group["sources"] and output["group_id"] == group["id"], "취합 원본 행/셀 전체 추적 오류")
            require(output["unit"] == master[group["code"]]["단위"] and dec(output["unit_price"]) == group["price"], "취합 단위/단가 오류")
            require(dec(output["quantity"]) == group["quantity"] and dec(output["supply_amount"]) == group["supply"], "취합 수량/공급가액 오류")
            require(dec(output["vat"]) == line_vat and dec(output["total_amount"]) == group["supply"] + line_vat, "취합 부가세/합계 오류")
            flattened.extend(s["row"] for s in output["sources"])
            supply += group["supply"]
            vat += line_vat
        require(sorted(flattened) == seen_sources and len(set(flattened)) == accepted_count, "중복/누락 원본 추적 오류")
        require(supply == control["supply"] and vat == Decimal(control["supply"]) / 10, f"{case}: 독립 고정 금액 검산 실패")
        summary = expected["summary"]
        require((summary["order_rows"], summary["accepted_source_rows"], summary["review_rows"], summary["canceled_rows"], summary["output_lines"]) == (len(control["rows"]), accepted_count, review_count, canceled_count, len(groups)), "요약 행 수 오류")
        require(dec(summary["supply_amount"]) == supply and dec(summary["vat"]) == vat and dec(summary["total_amount"]) == supply + vat, "부분 합계 오류")
        results.append({"sample": case, "summary": summary, "intentional_errors": actual_issues})
    template = read(public / "common_delivery_statement_template.xlsx")
    formulas = template["거래명세서"]["formulas"]
    require(len(formulas) == 63, "템플릿 수식 개수 오류")
    for row in range(10, 30):
        require(formulas[f"G{row}"] == f'IF(COUNT(E{row}:F{row})<2,"",ROUND(E{row}*F{row},0))', "템플릿 공급가액 수식 오류")
        require(formulas[f"H{row}"] == f'IF(G{row}="","",ROUND(G{row}*10%,0))', "템플릿 VAT 수식 오류")
        require(formulas[f"I{row}"] == f'IF(G{row}="","",G{row}+H{row})', "템플릿 합계 수식 오류")
    for column in "GHI":
        require(formulas[f"{column}31"] == f'IF(COUNT({column}10:{column}29)=0,"",SUM({column}10:{column}29))', "템플릿 합산 수식 오류")
    return results
