"""조문에서 용도지역별 건폐율·용적률(%)을 뽑는다.

- 조 번호가 아니라 조 제목('건폐율', '용적률')으로 조문을 고른다. 2024년 서울 전부개정처럼 번호가 통째로 바뀌어도 찾는다.
- "제3종일반주거지역 : 250퍼센트" 처럼 용도지역 이름 바로 뒤에 숫자가 오는 경우만 인정한다.
  단서·완화 조항의 문장형 숫자는 잡지 않는다 (잘못 뽑느니 못 뽑고 사람에게 넘긴다).
- 같은 용도지역 값이 여러 개 나오면(예: 서울도심 상업지역 별도 기준) 모두 돌려주고, 판단은 비교 단계에서 한다.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .lawapi import Article

ZONE = (
    r"제[12]종전용주거지역|제[123]종일반주거지역|준주거지역"
    r"|중심상업지역|일반상업지역|근린상업지역|유통상업지역"
    r"|전용공업지역|일반공업지역|준공업지역"
    r"|보전녹지지역|생산녹지지역|자연녹지지역"
)
# 공백을 모두 지운 문장에서 찾는다 ("제3종 일반주거지역 : 250 퍼센트" 같은 띄어쓰기 차이 흡수)
_VALUE = re.compile(rf"({ZONE})[:：]?(\d{{1,4}})(?:퍼센트|%)")

KINDS = {"bcr": "건폐율", "far": "용적률"}


@dataclass
class Extracted:
    values: dict[str, dict[str, list[int]]] = field(default_factory=lambda: {"bcr": {}, "far": {}})
    articles: dict[str, list[str]] = field(default_factory=lambda: {"bcr": [], "far": []})


def extract(articles: list[Article]) -> Extracted:
    out = Extracted()
    for kind, word in KINDS.items():
        found: dict[str, list[int]] = defaultdict(list)
        for a in articles:
            if word not in a.title:
                continue
            out.articles[kind].append(f"제{a.number}조({a.title})")
            flat = _korean_numbers(re.sub(r"\s+", "", a.text))
            for zone, pct in _VALUE.findall(flat):
                v = int(pct)
                if v not in found[zone]:
                    found[zone].append(v)
        out.values[kind] = dict(found)
    return out


def _korean_numbers(s: str) -> str:
    """조례 표기 '1천퍼센트', '1천2백퍼센트' → '1000퍼센트', '1200퍼센트'."""
    s = re.sub(r"(\d+)천(\d+)백", lambda m: str(int(m[1]) * 1000 + int(m[2]) * 100), s)
    s = re.sub(r"(\d+)천(?!\d)", lambda m: str(int(m[1]) * 1000), s)
    return re.sub(r"(\d+)백(?!\d)", lambda m: str(int(m[1]) * 100), s)
