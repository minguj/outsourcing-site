"""반복 결제(구독·고정지출) 감지 (I/O 없음).

흐름: 승인취소 짝 제거 → 가맹점 key로 묶기 → 금액대가 크게 다르면 나누기(같은 통신사 회선 2개 등)
→ 결제 간격으로 주기(주·월·연) 판단 → 금액 성격(고정·변동·환율 영향) → 다음 결제 예정일·신뢰도·신호.

판단 기준 (숫자는 모두 상수로 두고 테스트로 고정한다)
- 월 주기: 간격 26~35일. 한 달 빠진 간격(54~66일)은 1번까지 허용하되 신뢰도를 깎는다.
- 주 주기: 간격 6~8일.
- 최소 횟수: 3회. 사전에 있는 서비스는 2회부터. 연간 결제 서비스는 1회도 '연간 결제 추정'으로 남긴다.
- 무료체험 전환: 첫 결제가 1,000원 이하이고 그다음부터 정상 금액.
- 가격 인상: 고정 금액 구독에서 마지막 금액이 처음(체험 제외)보다 5% 이상 높을 때. 해외결제는 원래 통화 금액으로 비교해
  환율 때문에 원화 금액만 흔들린 것은 인상으로 보지 않는다.
- 해지 추정: 다음 결제 예정일이 지나고 유예일(월 10일, 주 3일)까지 결제가 없을 때.
"""
from __future__ import annotations

import calendar
import statistics
from datetime import date, timedelta

from .merchants import VARIABLE_OK

MONTHLY = (26, 35)
MONTHLY_SKIP = (54, 66)
WEEKLY = (6, 8)
GRACE_DAYS = {"monthly": 10, "weekly": 3, "yearly": 30}
TRIAL_MAX = 1000
PRICE_UP_RATIO = 0.05
SPLIT_GAP = 0.4
VARIABLE_CV = 0.01


def effective(transactions: list[dict]) -> list[dict]:
    """승인취소된 승인 건을 빼고, 승인 건만 날짜순으로 돌려준다."""
    cancelled = {t["approval_id"] for t in transactions if t["type"] == "cancel"}
    kept = [t for t in transactions if t["type"] == "approval" and t["id"] not in cancelled]
    return sorted(kept, key=lambda t: (t["date"], t["id"]))


def _basis(t: dict) -> float:
    """금액 비교 기준: 해외결제는 원래 통화 금액, 아니면 원화."""
    return t["orig_amount"] if t.get("orig_currency") else t["amount"]


def split_by_amount(txs: list[dict]) -> list[list[dict]]:
    """금액을 정렬했을 때 바로 옆 금액과 40% 넘게 벌어지면 다른 묶음으로 나눈다. 체험 결제(1,000원 이하)는 정상 금액
    묶음 중 가장 이른 묶음에 붙인다."""
    trials = [t for t in txs if t["amount"] <= TRIAL_MAX and not t.get("orig_currency")]
    normal = sorted((t for t in txs if t not in trials), key=_basis)
    clusters: list[list[dict]] = []
    for t in normal:
        if clusters and _basis(t) <= _basis(clusters[-1][-1]) * (1 + SPLIT_GAP):
            clusters[-1].append(t)
        else:
            clusters.append([t])
    if trials and clusters:
        first = min(clusters, key=lambda c: min(x["date"] for x in c))
        first.extend(trials)
    elif trials:
        clusters.append(trials)
    return [sorted(c, key=lambda t: (t["date"], t["id"])) for c in clusters]


def add_months(d: date, months: int, day: int | None = None) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(day or d.day, calendar.monthrange(y, m)[1]))


def _cadence(dates: list[date]) -> tuple[str | None, int]:
    """(주기, 빠진 달 수). 주기를 판단할 수 없으면 (None, 0)."""
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    if gaps and all(WEEKLY[0] <= g <= WEEKLY[1] for g in gaps):
        return "weekly", 0
    skips = sum(1 for g in gaps if MONTHLY_SKIP[0] <= g <= MONTHLY_SKIP[1])
    if gaps and skips <= 1 and all(MONTHLY[0] <= g <= MONTHLY[1] or MONTHLY_SKIP[0] <= g <= MONTHLY_SKIP[1] for g in gaps):
        return "monthly", skips
    return None, 0


def analyze(txs: list[dict], info: dict | None, as_of: date) -> dict | None:
    """같은 가맹점·같은 금액대 결제 묶음 하나를 분석한다. 반복 결제가 아니면 None."""
    known = info is not None
    dates = [date.fromisoformat(t["date"]) for t in txs]
    cadence, skips = _cadence(dates)
    n = len(txs)
    if cadence is None:
        if known and info.get("cadence") == "yearly" and n == 1:
            cadence = "yearly"
        else:
            return None
    min_count = 2 if known else 3
    if cadence != "yearly" and n < min_count:
        return None

    trial = n >= 2 and txs[0]["amount"] <= TRIAL_MAX < txs[1]["amount"]
    paid = txs[1:] if trial else txs
    bases = [_basis(t) for t in paid]
    amounts = [t["amount"] for t in paid]
    foreign = paid[-1].get("orig_currency")
    category = info["category"] if known else "other"

    steady_basis = len(set(bases)) == 1
    if category in VARIABLE_OK or (not foreign and _cv(amounts) > VARIABLE_CV and not _is_step(bases)):
        amount_type = "variable"
        expected = round(statistics.median(amounts[-3:]))
    elif foreign and steady_basis and len(set(amounts)) > 1:
        amount_type = "fx"
        expected = round(statistics.mean(amounts[-3:]))
    else:
        amount_type = "fixed"
        expected = amounts[-1]

    last = dates[-1]
    if cadence == "monthly":
        next_date = add_months(last, 1, day=dates[-1].day)
    elif cadence == "weekly":
        next_date = last + timedelta(days=7)
    else:
        next_date = add_months(last, 12)
    cancelled = as_of > next_date + timedelta(days=GRACE_DAYS[cadence])

    signals = []
    if trial:
        signals.append({"type": "trial_conversion", "date": paid[0]["date"],
                        "detail": f"{txs[0]['amount']:,}원 체험 후 {paid[0]['amount']:,}원 정기결제로 전환"})
    if amount_type == "fixed" and len(bases) >= 2 and bases[-1] >= bases[0] * (1 + PRICE_UP_RATIO):
        changed = next(t for t in paid if _basis(t) == bases[-1])
        signals.append({"type": "price_increase", "date": changed["date"],
                        "detail": f"{_money(paid[0])} → {_money(paid[-1])}", "from": amounts[0], "to": amounts[-1]})
    if amount_type == "fx":
        signals.append({"type": "fx", "date": paid[-1]["date"],
                        "detail": f"{foreign} {bases[-1]:g} 고정, 원화 금액은 환율에 따라 {min(amounts):,}~{max(amounts):,}원"})
    if cancelled:
        signals.append({"type": "likely_cancelled", "date": next_date.isoformat(),
                        "detail": f"{next_date.isoformat()} 예정 결제가 없어 해지된 것으로 보입니다"})

    confidence = {1: 50, 2: 60, 3: 72, 4: 82}.get(n, 90)
    if known:
        confidence += 7
    confidence -= 15 * skips
    return {
        "cadence": cadence, "count": n, "first_date": txs[0]["date"], "last_date": txs[-1]["date"],
        "amount_type": amount_type, "expected_amount": expected, "last_amount": amounts[-1],
        "currency": foreign, "next_date": next_date.isoformat(), "status": "cancelled" if cancelled else "active",
        "monthly_equivalent": monthly_equivalent(expected, cadence), "confidence": max(0, min(99, confidence)),
        "signals": signals, "transaction_ids": [t["id"] for t in txs],
    }


def monthly_equivalent(amount: int, cadence: str) -> int:
    if cadence == "weekly":
        return amount * 52 // 12
    if cadence == "yearly":
        return amount // 12
    return amount


def _cv(values: list[float]) -> float:
    if len(values) < 2 or statistics.mean(values) == 0:
        return 0.0
    return statistics.pstdev(values) / statistics.mean(values)


def _is_step(values: list[float]) -> bool:
    """값이 한두 번 바뀐 뒤 그대로 유지되는 계단 모양이면 True (가격 인상)."""
    changes = sum(1 for a, b in zip(values, values[1:]) if a != b)
    return changes <= 1 or (changes == 2 and values[-1] == values[-2])


def _money(t: dict) -> str:
    if t.get("orig_currency"):
        return f"{t['orig_currency']} {t['orig_amount']:g}"
    return f"{t['amount']:,}원"
