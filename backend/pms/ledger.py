"""회계 분개 내보내기 (I/O 없음).

한 사업장·한 달의 청구와 수납을 회계 프로그램에 올릴 분개로 바꾼다. (데모용 단순 계정)
- 청구: 그 달 말일자로 (차) 매출채권 / (대) 이용료수익·서비스수익
- 수납: 받은 날짜로 (차) 보통예금 / (대) 매출채권 — 받은 날이 그 달인 수납만
- 연체료는 화면에서 계산만 하고 아직 청구하지 않으므로 분개에 넣지 않는다.
차변 합계와 대변 합계가 같아야 내보낸다.
"""
from __future__ import annotations

import csv
import io

from .billing import month_range

ACCOUNTS = {"ar": "매출채권", "rent": "이용료수익", "service": "서비스수익", "cash": "보통예금"}


def journal(month: str, invoices: list[dict], payments: list[dict], names: dict[str, str]) -> list[dict]:
    """invoices: 그 사업장의 청구서 전체, payments: 그 사업장 청구서에 대한 수납 전체."""
    first, last = month_range(month)
    rows: list[dict] = []
    no = 0
    for inv in sorted((i for i in invoices if i["month"] == month), key=lambda i: i["id"]):
        no += 1
        who = names.get(inv["resident_id"], inv["resident_id"])
        rent = sum(l["amount"] for l in inv["lines"] if l["code"] == "monthly_fee")
        service = inv["total"] - rent
        entry = [("ar", inv["total"], 0)]
        if rent:
            entry.append(("rent", 0, rent))
        if service:
            entry.append(("service", 0, service))
        for account, debit, credit in entry:
            rows.append({"date": last.isoformat(), "no": f"{month}-{no:03d}", "account": ACCOUNTS[account],
                         "debit": debit, "credit": credit, "memo": f"{month} 이용료 청구 {who}", "ref": inv["id"]})
    for pay in sorted(payments, key=lambda p: (p["paid_on"], p["id"])):
        if not first.isoformat() <= pay["paid_on"] <= last.isoformat():
            continue
        no += 1
        inv = next(i for i in invoices if i["id"] == pay["invoice_id"])
        who = names.get(inv["resident_id"], inv["resident_id"])
        for account, debit, credit in (("cash", pay["amount"], 0), ("ar", 0, pay["amount"])):
            rows.append({"date": pay["paid_on"], "no": f"{month}-{no:03d}", "account": ACCOUNTS[account],
                         "debit": debit, "credit": credit, "memo": f"{inv['month']} 이용료 수납 {who}", "ref": pay["id"]})
    return rows


def totals(rows: list[dict]) -> dict:
    debit = sum(r["debit"] for r in rows)
    credit = sum(r["credit"] for r in rows)
    return {"debit": debit, "credit": credit, "balanced": debit == credit}


def to_csv(rows: list[dict]) -> str:
    """엑셀에서 한글이 깨지지 않도록 BOM 을 붙인다."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(["전표일자", "전표번호", "계정과목", "차변", "대변", "적요", "참조"])
    for r in rows:
        writer.writerow([r["date"], r["no"], r["account"], r["debit"], r["credit"], r["memo"], r["ref"]])
    return "﻿" + out.getvalue()
