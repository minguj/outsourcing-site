"""청구·수납 계산 (I/O 없음).

금액은 모두 원 단위 정수다. 소수 계산 결과는 10원 미만을 버린다.

가정 (데모용, 사업장 요금표로 바꿀 수 있다)
- 청구 기간은 달력 기준 한 달이다.
- 월 이용료는 그 달에 계약이 유효한 날수만큼 일할 계산한다. (입주일·퇴거일 모두 포함)
- 부가 서비스는 그 달에 기록된 이용 건수 × 사업장 단가로 청구한다.
- 납부 기한은 다음 달 사업장 납부일이다.
- 연체료는 납부 기한 다음 날부터 기준일까지, 남은 원금에 사업장 연체 이율(연)을 날수로 나눠 단리로 계산한다.
  남은 원금은 기준일 현재 금액으로 본다 (기간 중 부분 납부 시점별 분할 계산은 하지 않는 데모 단순화).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date


def floor10(value: float) -> int:
    return int(value // 10 * 10)


def month_range(month: str) -> tuple[date, date]:
    year, mon = (int(part) for part in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last)


def occupied_days(start: date, end: date | None, month: str) -> int:
    first, last = month_range(month)
    begin = max(start, first)
    finish = min(end or last, last)
    return max(0, (finish - begin).days + 1)


def prorated_fee(monthly_fee: int, start: date, end: date | None, month: str) -> int:
    first, last = month_range(month)
    days = occupied_days(start, end, month)
    total = (last - first).days + 1
    if days == total:
        return monthly_fee
    return floor10(monthly_fee * days / total)


def due_date(month: str, due_day: int) -> date:
    _, last = month_range(month)
    year, mon = (last.year + 1, 1) if last.month == 12 else (last.year, last.month + 1)
    return date(year, mon, min(due_day, calendar.monthrange(year, mon)[1]))


@dataclass
class Line:
    code: str
    label: str
    quantity: int
    unit_price: int
    amount: int


@dataclass
class Draft:
    lines: list[Line] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(line.amount for line in self.lines)


def build_invoice(contract: dict, month: str, usages: list[dict], price_table: dict) -> Draft | None:
    """계약 1건의 월 청구서 초안. 그 달에 유효한 날이 없으면 None."""
    start = date.fromisoformat(contract["start_date"])
    end = date.fromisoformat(contract["end_date"]) if contract.get("end_date") else None
    days = occupied_days(start, end, month)
    if days == 0:
        return None
    draft = Draft()
    first, last = month_range(month)
    total_days = (last - first).days + 1
    rent = prorated_fee(contract["monthly_fee"], start, end, month)
    label = "월 이용료" if days == total_days else f"월 이용료 (일할 {days}/{total_days}일)"
    draft.lines.append(Line("monthly_fee", label, 1, rent, rent))
    counts: dict[str, int] = {}
    for usage in usages:
        counts[usage["service"]] = counts.get(usage["service"], 0) + usage["quantity"]
    for code in sorted(counts):
        item = price_table[code]
        draft.lines.append(Line(code, item["label"], counts[code], item["price"], counts[code] * item["price"]))
    return draft


def outstanding(total: int, payments: list[dict]) -> int:
    return max(0, total - sum(p["amount"] for p in payments))


def late_fee(principal_left: int, due: date, as_of: date, annual_rate_pct: float) -> int:
    days = (as_of - due).days
    if principal_left <= 0 or days <= 0:
        return 0
    return floor10(principal_left * annual_rate_pct / 100 * days / 365)


def invoice_status(total: int, payments: list[dict], due: date, as_of: date) -> str:
    left = outstanding(total, payments)
    if left == 0:
        return "paid"
    if as_of > due:
        return "overdue"
    return "partial" if left < total else "issued"
