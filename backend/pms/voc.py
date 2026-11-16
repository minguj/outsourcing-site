"""민원(VOC) 분류 규칙 (I/O 없음).

- 분류·긴급도·담당 역할은 정해진 값만 쓴다. AI 응답도 이 값으로 검증해 받는다.
- AI에 보내기 전에 전화번호·이메일·사업장에 등록된 사람 이름을 가린다.
- AI를 쓸 수 없을 때(키 없음, 호출 실패, 사용량 초과)는 키워드 규칙으로 분류한다.
"""
from __future__ import annotations

import re

CATEGORIES = {"facility": "시설", "noise": "소음·생활", "billing": "요금·계약", "care": "돌봄·건강", "other": "기타"}
URGENCY = {"high": "긴급", "normal": "보통", "low": "낮음"}
ROUTE = {"facility": "site_manager", "noise": "site_manager", "billing": "accountant", "care": "care_staff",
         "other": "site_manager"}
STATUS_LABELS = {"received": "접수", "in_progress": "처리 중", "done": "완료"}
# 상태 이동: (지금, 다음) → (버튼 이름, 사유 필수 여부). 완료를 지우지 않고 '다시 열기'로 이력을 남긴다.
TRANSITIONS = {
    ("received", "in_progress"): ("처리 시작", False),
    ("in_progress", "done"): ("완료", False),
    ("in_progress", "received"): ("접수로 되돌리기", True),
    ("done", "in_progress"): ("다시 열기", True),
}
REASON_MAX = 200
MAX_CHARS = 500

PHONE_RE = re.compile(r"(?<!\d)0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

RULES = [
    ("care", ("약을", "약이", "약 ", "투약", "복약", "식사", "알레르기", "견과", "아파", "통증", "병원", "케어", "돌봄", "낙상", "넘어", "어지러", "열이")),
    ("billing", ("청구", "요금", "이용료", "관리비", "납부", "환불", "연체", "계약", "보증금", "영수증", "금액")),
    ("noise", ("소음", "시끄", "쿵쿵", "냄새", "담배", "층간", "이웃", "애완", "반려")),
    ("facility", ("누수", "물이", "보일러", "난방", "온수", "고장", "전기", "정전", "엘리베이터", "승강기", "문이", "도어락",
                  "에어컨", "곰팡이", "변기", "막혔", "조명", "전등", "수리")),
]
HIGH = ("누수", "물이 새", "물이 떨어", "가스", "화재", "불이", "연기", "낙상", "넘어", "쓰러", "의식", "정전", "응급",
        "피가", "갇혔", "갇혀", "갇힌", "숨", "알레르기")
LOW = ("문의", "궁금", "건의", "제안", "가능할까", "가능한지")


def redact(text: str, names: list[str]) -> str:
    out = EMAIL_RE.sub("[이메일]", text)
    out = PHONE_RE.sub("[전화번호]", out)
    for name in sorted({n for n in names if len(n) >= 2}, key=len, reverse=True):
        out = out.replace(name, "[이름]")
    return out


def _summary(text: str) -> str:
    first = re.split(r"(?<=[.!?。])\s|\n", text.strip(), maxsplit=1)[0]
    return first if len(first) <= 40 else first[:39] + "…"


def rule_classify(text: str) -> dict:
    category = "other"
    hits: list[str] = []
    for code, words in RULES:
        found = [w for w in words if w in text]
        if found:
            category, hits = code, found
            break
    if any(w in text for w in HIGH):
        urgency = "high"
    elif any(w in text for w in LOW):
        urgency = "low"
    else:
        urgency = "normal"
    reason = f"키워드: {', '.join(hits[:3])}" if hits else "맞는 키워드가 없어 기타로 분류"
    return {"category": category, "urgency": urgency, "summary": _summary(text), "reason": reason}


def normalize_ai(result: object) -> dict | None:
    """AI 응답을 정해진 값으로 검증한다. 맞지 않으면 None (규칙 분류로 대신한다)."""
    if not isinstance(result, dict):
        return None
    category, urgency = result.get("category"), result.get("urgency")
    summary, reason = result.get("summary"), result.get("reason")
    if category not in CATEGORIES or urgency not in URGENCY:
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None
    reason = reason.strip() if isinstance(reason, str) else ""
    return {"category": category, "urgency": urgency, "summary": summary.strip()[:80], "reason": reason[:120]}
