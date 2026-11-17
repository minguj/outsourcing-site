"""가맹점명 정리와 알려진 서비스 사전 (I/O 없음).

카드사·은행 거래내역의 가맹점명은 결제대행사 접두어(KCP*, NICE*), 법인 표기, 대소문자, 공백이 제각각이다.
정리한 이름(key)으로 같은 가맹점끼리 묶고, 알려진 서비스 사전과 대조해 서비스명·분류를 붙인다.
사전에 없는 가맹점은 AI 분류(enrich_ai.py)나 규칙 기본값으로 채운다.
"""
from __future__ import annotations

import re

CATEGORIES = {
    "ott": "영상(OTT)", "music": "음악", "cloud": "클라우드·저장공간", "software": "소프트웨어·AI",
    "membership": "멤버십", "content": "도서·콘텐츠", "education": "교육", "fitness": "운동",
    "telecom": "통신", "insurance": "보험", "housing": "주거·관리비", "utility": "공과금", "other": "기타",
}
# 같은 분류에 2개 이상 있으면 '중복 구독'으로 알려 주는 분류
DUPLICATE_SENSITIVE = {"ott", "music", "cloud", "content"}
# 금액이 매달 조금씩 달라지는 것이 정상인 고정지출 분류 (가격 인상 신호에서 뺀다)
VARIABLE_OK = {"telecom", "utility", "housing"}

PREFIX_RE = re.compile(r"^(KCP|NICE|KICC|INICIS|TOSS|PAYCO|KSNET|KG|GOOGLE|APPLE|PAYPAL)\s*\*\s*")
NOISE_RE = re.compile(r"\(주\)|주식회사|㈜|CORP\.?|INC\.?|LTD\.?|\.COM|\.KR|/BILL")
SPACE_RE = re.compile(r"[\s\-_.,*()/+]+")

# (key에 들어 있으면 맞는 조각들, 서비스명, 분류, 종류, 주기) — 위에서부터 먼저 맞는 것을 쓴다.
# 서비스명이 None 이면 가맹점명을 그대로 쓴다 (보험사처럼 이름 자체가 구분이 되는 경우).
# 종류: subscription(구독) | fixed(고정지출). 주기: monthly | yearly
KNOWN = [
    (("NETFLIX", "넷플릭스"), "넷플릭스", "ott", "subscription", "monthly"),
    (("YOUTUBEPREMIUM", "YOUTUBE"), "유튜브 프리미엄", "ott", "subscription", "monthly"),
    (("TVING", "티빙"), "티빙", "ott", "subscription", "monthly"),
    (("WAVVE", "웨이브"), "웨이브", "ott", "subscription", "monthly"),
    (("DISNEYPLUS", "디즈니플러스"), "디즈니+", "ott", "subscription", "monthly"),
    (("MELON", "멜론"), "멜론", "music", "subscription", "monthly"),
    (("SPOTIFY",), "스포티파이", "music", "subscription", "monthly"),
    (("쿠팡와우",), "쿠팡 와우 멤버십", "membership", "subscription", "monthly"),
    (("배민클럽",), "배민클럽", "membership", "subscription", "monthly"),
    (("네이버플러스",), "네이버플러스 멤버십", "membership", "subscription", "monthly"),
    (("ICLOUD",), "iCloud+", "cloud", "subscription", "monthly"),
    (("GOOGLEONE",), "Google One", "cloud", "subscription", "monthly"),
    (("OPENAI", "CHATGPT"), "ChatGPT Plus", "software", "subscription", "monthly"),
    (("MICROSOFT365", "MICROSOFT"), "Microsoft 365", "software", "subscription", "yearly"),
    (("KT통신", "SKT통신", "LGU통신"), "휴대폰 요금", "telecom", "fixed", "monthly"),
    (("SK브로드밴드", "KT인터넷"), "인터넷·TV", "telecom", "fixed", "monthly"),
    (("화재보험", "생명보험", "보험료"), None, "insurance", "fixed", "monthly"),
    (("관리비",), "아파트 관리비", "housing", "fixed", "monthly"),
    (("도시가스",), "도시가스", "utility", "fixed", "monthly"),
    (("한국전력",), "전기요금", "utility", "fixed", "monthly"),
    (("애니타임피트니스", "피트니스"), "피트니스", "fitness", "subscription", "monthly"),
]


def normalize(raw: str) -> str:
    """가맹점명 → 묶음용 key. 예: 'KCP*쿠팡와우 월회비' → '쿠팡와우월회비', 'NETFLIX.COM' → 'NETFLIX'."""
    s = raw.strip().upper()
    s = PREFIX_RE.sub("", s)
    s = NOISE_RE.sub(" ", s)
    s = SPACE_RE.sub("", s)
    return s


def lookup(key: str) -> dict | None:
    for pieces, name, category, kind, cadence in KNOWN:
        if any(p in key for p in pieces):
            return {"service": name, "category": category, "kind": kind, "cadence": cadence}
    return None


def canonical(key: str, cache: dict[str, dict] | None = None) -> str:
    """같은 서비스의 여러 표기를 한 묶음으로 보는 id.
    사전에 있으면 서비스명, AI가 정기 결제로 정리했으면 AI 서비스명, 둘 다 아니면 정리한 가맹점명 그대로."""
    known = lookup(key)
    if known:
        return f"svc:{known['service']}" if known["service"] else f"key:{key}"
    ai = (cache or {}).get(key)
    if ai and ai.get("recurring"):
        return f"ai:{ai['service']}"
    return f"key:{key}"


def label(category: str) -> str:
    return CATEGORIES.get(category, CATEGORIES["other"])
