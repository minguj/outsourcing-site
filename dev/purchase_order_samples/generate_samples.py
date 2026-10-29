#!/usr/bin/env python3
"""Regenerate the fictional order fixtures, then independently validate them."""
import argparse
import csv
from pathlib import Path

from xlsx_fixture import workbook
from structured_samples import build_all

DEV = Path(__file__).resolve().parent
PUBLIC = DEV.parents[1] / "frontend/public/samples/purchase-orders"
NOTICE = "체험용 가상 데이터 — 모든 회사·담당자·연락처는 가상이며 실제 거래에 사용할 수 없습니다."
MASTER = [
    ("S001", "A4 복사용지 80g", "A4용지|복사지80", "박스", 25000),
    ("S002", "종이컵 180ml", "6.5온스컵|종이컵6.5", "박스", 13000),
    ("S003", "니트릴장갑 M", "니트릴M|위생장갑|위생장갑 M", "박스", 8000),
    ("S004", "니트릴장갑 L", "니트릴L|위생장갑|위생장갑 L", "박스", 8500),
    ("S005", "다목적세정제", "만능세정액|다목적클리너|다목적세정제 원액", "L", 3200),
    ("S006", "주방세제 1L", "설거지세제|주방세정1L", "병", 4500),
    ("S007", "키친타월 6롤", "주방타월6롤|키친6롤", "팩", 6000),
    ("S008", "쓰레기봉투 50L", "50리터봉투|휴지통봉투50", "팩", 7500),
    ("S009", "물티슈 100매", "물티슈100|청소물티슈", "팩", 1800),
    ("S010", "포장테이프 48mm", "박스테이프|테이프48", "롤", 1200),
    ("S011", "지퍼백 중형", "지퍼백M|중형지퍼백", "팩", 3500),
    ("S012", "행주 10매", "청소행주10|행주묶음", "팩", 4000),
    ("S013", "알코올솜 100매", "소독솜100|알콜솜", "박스", 2800),
    ("S014", "핸드워시 500ml", "손세정제500|핸드500", "병", 3800),
    ("S015", "스펀지 수세미 5개", "수세미5입|스펀지5", "팩", 2200),
    ("S016", "마스크 KF94 50매", "KF94묶음|보건마스크50", "박스", 15000),
]
ITEMS = {row[0]: row for row in MASTER}
def template():
    headers = ["순번", "품목코드", "표준품명", "단위", "수량", "단가", "공급가액", "부가세", "합계"]
    cells = {1: ["공통 거래명세서 출력 템플릿"], 2: [NOTICE],
             3: ["공급자", "(가상)모아소모품 도매", None, "담당", "가상공급담당", None, "연락", "supplier@example.invalid"],
             4: ["공급받는자", "(가상)거래처명 입력", None, "명세서번호", "DEMO-출력번호"],
             5: ["발주일", "YYYY-MM-DD", None, "납기일", "YYYY-MM-DD"],
             6: ["발행 상태", "확인 필요 행이 남으면 최종 발행하지 않음"],
             7: ["계산 기준", "KRW · 세전 단가 · 공급가액/부가세 각각 행별 원 단위 반올림"],
             9: headers}
    formulas = {}
    for row in range(10, 30):
        cells[row] = [None] * 9
        formulas[f"G{row}"] = f'IF(COUNT(E{row}:F{row})<2,"",ROUND(E{row}*F{row},0))'
        formulas[f"H{row}"] = f'IF(G{row}="","",ROUND(G{row}*10%,0))'
        formulas[f"I{row}"] = f'IF(G{row}="","",G{row}+H{row})'
    cells[31] = ["확정 행 합계", None, None, None, None, None, None, None, None]
    for column in "GHI":
        formulas[f"{column}31"] = f'IF(COUNT({column}10:{column}29)=0,"",SUM({column}10:{column}29))'
    cells[33] = ["입력 안내", "확정 행만 입력. 검수 제외 행을 0원으로 변환하지 않음. 원본 추적은 다음 시트에 기록."]
    tracking = {1: ["원본 행 추적 / 검수 기록"], 2: [NOTICE],
                4: ["출력 순번", "원본 파일명", "원본 시트", "원본 행", "검수 상태", "오류 코드", "확인 메모"]}
    for row in range(5, 25):
        tracking[row] = [None] * 7
    workbook(PUBLIC / "common_delivery_statement_template.xlsx", [
        {"name": "거래명세서", "cells": cells, "header_rows": [9], "formulas": formulas,
         "merges": ["A1:I1", "A2:I2", "B6:I6", "B7:I7", "B33:I33"],
         "widths": [15, 16, 30, 10, 12, 15, 18, 16, 18], "freeze": 9},
        {"name": "원본추적", "cells": tracking, "header_rows": [4],
         "merges": ["A1:G1", "A2:G2"], "widths": [14, 34, 24, 14, 18, 30, 45], "freeze": 4},
    ], "공통 거래명세서 템플릿")


def generate():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    with (PUBLIC / "item_master.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["품목코드", "표준명", "별칭", "단위", "기준단가", "데이터구분"])
        for row in MASTER:
            writer.writerow([*row, "체험용 가상 데이터"])
    build_all(PUBLIC, DEV, MASTER, NOTICE)
    template()
    (PUBLIC / "README.txt").write_text(
        NOTICE + "\n\nA: 한 페이지 인쇄 발주서 / 10품목 행.\n"
        "B: 쇼핑몰 원시 주문 18행 / 취소 3행 제외 / 정상 13행을 6품목으로 취합.\n"
        "C: 제조업 구매 발주서 / 주문 11행과 구분·빈 행·합계행 분리.\n"
        "검수 대상은 A 2행, B 2행, C 3행. 검수 완료 전 최종 발행 불가.\n"
        "금액은 KRW, 부가세 별도 공급가액. 별칭 구분자는 | 입니다.\n"
        "공통 템플릿에는 확정한 행만 입력하며 원본 파일·시트·행을 별도 시트에 기록합니다.\n"
        "정답·의도적 오류 목록은 개발용 dev/purchase_order_samples/expected/에 분리되어 있습니다.\n",
        encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate existing fixtures without rewriting them")
    options = parser.parse_args()
    if not options.check:
        generate()
    from validate_samples import validate
    validate()
