"""구독·고정지출 데모 가상 거래내역. 사람·가맹점 일부(학원·보험사·아파트)는 가상이다.

가상 사용자 3명 × 2026-05-01 ~ 2026-11-15 (기준일). 실제 카드사·은행 거래내역처럼 가맹점명이 제각각이고,
승인취소·해외결제·같은 통신사 회선 2개·계절에 따라 달라지는 공과금·일반 소비가 섞여 있다.
일반 소비 금액·날짜는 고정 시드로 만들어 매번 같은 데이터가 나온다.
"""
from __future__ import annotations

import calendar
import random
from datetime import date, timedelta

START = date(2026, 5, 1)
AS_OF = date(2026, 11, 15)
MONTHS = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]

PERSONAS = [
    {"id": "jisoo", "name": "김지수", "summary": "28세 직장인 · 디지털 구독이 많은 편",
     "accounts": [{"id": "card-a", "label": "신용카드"}, {"id": "bank-a", "label": "입출금 계좌(자동이체)"}]},
    {"id": "junghoon", "name": "박정훈", "summary": "41세 · 4인 가족 · 고정지출 중심",
     "accounts": [{"id": "card-b", "label": "신용카드"}, {"id": "bank-b", "label": "입출금 계좌(자동이체)"}]},
    {"id": "haneul", "name": "이하늘", "summary": "22세 대학생 · 체험으로 시작한 구독",
     "accounts": [{"id": "card-c", "label": "체크카드"}]},
]


class _Builder:
    def __init__(self, pid: str):
        self.pid, self.items, self.seq = pid, [], 0

    def add(self, day: date, merchant: str, amount: int, account: str, *, method: str = "card",
            usd: float | None = None, hour: int = 9) -> dict:
        self.seq += 1
        tx = {"id": f"{self.pid}-{self.seq:04d}", "account": account, "date": day.isoformat(),
              "at": f"{day.isoformat()}T{hour:02d}:{(self.seq * 7) % 60:02d}:00+09:00", "merchant_raw": merchant,
              "amount": amount, "type": "approval", "method": method,
              "orig_amount": usd, "orig_currency": "USD" if usd is not None else None}
        self.items.append(tx)
        return tx

    def cancel(self, original: dict, day: date) -> None:
        self.seq += 1
        self.items.append({**original, "id": f"{self.pid}-{self.seq:04d}", "date": day.isoformat(),
                           "at": f"{day.isoformat()}T18:00:00+09:00", "type": "cancel",
                           "approval_id": original["id"]})

    def monthly(self, merchant: str, amounts: list[int] | int, day: int, account: str, *, months: list[str] = MONTHS,
                method: str = "card", usd: float | None = None) -> None:
        for i, ym in enumerate(months):
            y, m = map(int, ym.split("-"))
            d = date(y, m, min(day, calendar.monthrange(y, m)[1]))
            if d > AS_OF or (isinstance(amounts, list) and i >= len(amounts)):
                break
            amount = amounts[i] if isinstance(amounts, list) else amounts
            self.add(d, merchant, amount, account, method=method, usd=usd)

    def random_spend(self, rng: random.Random, merchants: list[tuple[str, int, int]], per_month: int, account: str):
        d = START
        while d <= AS_OF:
            for _ in range(rng.randint(per_month - 2, per_month + 2)):
                name, low, high = rng.choice(merchants)
                day = d + timedelta(days=rng.randint(0, 27))
                if day <= AS_OF:
                    self.add(day, name, rng.randrange(low, high, 100), account, hour=rng.randint(8, 22))
            d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _jisoo() -> list[dict]:
    b, rng = _Builder("jisoo"), random.Random(11)
    # 9월부터 결제대행이 바뀌어 같은 넷플릭스가 다른 이름으로 찍힌다 (표기가 달라도 한 묶음으로 봐야 한다)
    b.monthly("NETFLIX.COM", [13500, 13500, 13500, 17000], 5, "card-a", months=MONTHS[:4])
    b.monthly("넷플릭스(NETFLIX)", [17000, 17000, 17000], 5, "card-a", months=MONTHS[4:])
    b.monthly("GOOGLE*YouTubePremium", 14900, 12, "card-a")
    b.add(date(2026, 9, 20), "TVING(티빙)", 100, "card-a")
    b.add(date(2026, 10, 20), "TVING(티빙)", 13900, "card-a")
    b.monthly("WATCHA 왓챠", 7900, 8, "card-a", months=MONTHS[:4])
    b.monthly("멜론(카카오엔터)", 10900, 3, "card-a")
    b.monthly("SPOTIFY KOREA", 11990, 15, "card-a", months=MONTHS[2:])
    b.monthly("KCP*쿠팡와우 월회비", 7890, 22, "card-a")
    b.monthly("배민클럽 정기결제", 3990, 1, "card-a")
    b.monthly("OPENAI *CHATGPT SUBSCR", [27640, 28020, 27880, 27310, 28450, 28190], 18, "card-a", usd=20.0)
    b.monthly("NOTION LABS INC", [13820, 14010, 13940, 13660, 14230, 14090], 9, "card-a", usd=10.0)
    b.monthly("APPLE*ICLOUD", 4400, 27, "card-a")
    b.monthly("KT통신요금자동납부", [58300, 61200, 57800, 59900, 62400, 60100], 25, "bank-a", method="auto_transfer")
    b.random_spend(rng, [("(주)우아한형제들", 12000, 32000), ("스타벅스 강남역점", 4500, 12000),
                         ("GS25 역삼점", 1500, 9000), ("쿠팡(주)", 9000, 60000)], 14, "card-a")
    order = b.add(date(2026, 10, 2), "쿠팡(주)", 45900, "card-a")
    b.cancel(order, date(2026, 10, 3))
    return b.items


def _junghoon() -> list[dict]:
    b, rng = _Builder("junghoon"), random.Random(22)
    b.monthly("한결아파트관리비", [215400, 198700, 223900, 241300, 230800, 207600], 25, "bank-b", method="auto_transfer")
    b.monthly("서울도시가스", [38200, 24100, 15800, 14900, 16700, 27300], 20, "bank-b", method="auto_transfer")
    b.monthly("한국전력공사", [41000, 47800, 89600, 96200, 58400, 44100], 18, "bank-b", method="auto_transfer")
    b.monthly("KT통신요금자동납부", [45100, 45300, 45100, 45200, 45100, 45400], 21, "bank-b", method="auto_transfer")
    b.monthly("KT통신요금자동납부", 69800, 26, "bank-b", method="auto_transfer")
    b.monthly("SK브로드밴드", 33000, 15, "bank-b", method="auto_transfer")
    b.monthly("한결화재보험 자동이체", 87400, 10, "bank-b", method="auto_transfer")
    b.monthly("한결생명보험 보험료", 152000, 28, "bank-b", method="auto_transfer")
    b.monthly("디즈니플러스", 9900, 9, "card-b")
    b.monthly("WAVVE 웨이브", 7900, 14, "card-b")
    b.monthly("네이버플러스 멤버십", 4900, 2, "card-b")
    b.add(date(2026, 6, 11), "MICROSOFT*365 FAMILY", 119000, "card-b")
    b.monthly("다온수학학원", 380000, 25, "card-b")
    b.monthly("애니타임피트니스 강서점", 79000, 1, "card-b", months=MONTHS[:4])
    b.random_spend(rng, [("이마트 가양점", 20000, 180000), ("GS칼텍스 강서주유소", 40000, 90000),
                         ("(주)우아한형제들", 15000, 45000)], 12, "card-b")
    return b.items


def _haneul() -> list[dict]:
    b, rng = _Builder("haneul"), random.Random(33)
    b.add(date(2026, 8, 3), "SPOTIFY KOREA", 100, "card-c")
    b.monthly("SPOTIFY KOREA", 11990, 3, "card-c", months=MONTHS[4:])
    b.monthly("밀리의서재", 9900, 17, "card-c", months=MONTHS[:6])
    b.monthly("RIDI 리디셀렉트", 4900, 7, "card-c")
    b.monthly("CJ헬로모바일 요금", [16500, 17200, 16500, 16900, 16500, 17400], 23, "card-c")
    d = date(2026, 9, 7)
    while d <= AS_OF:
        b.add(d, "프레시위클리 밀키트구독", 19900, "card-c")
        d += timedelta(days=7)
    b.random_spend(rng, [("CU 단국대점", 1200, 8000), ("메가커피 죽전점", 1500, 5500),
                         ("단국대학교 생활협동조합", 3500, 7000)], 18, "card-c")
    return b.items


def build() -> dict:
    return {
        "as_of": AS_OF.isoformat(), "period": {"from": START.isoformat(), "to": AS_OF.isoformat()},
        "personas": PERSONAS,
        "transactions": {"jisoo": _jisoo(), "junghoon": _junghoon(), "haneul": _haneul()},
        "overrides": {p["id"]: {} for p in PERSONAS},
        "cancellations": {p["id"]: {} for p in PERSONAS},
        "ai_runs": 0,
    }
