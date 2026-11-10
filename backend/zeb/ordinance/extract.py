"""조문에서 용도지역별 건폐율·용적률(%)을 뽑는다.

- 조 번호가 아니라 조 제목으로 조문을 고른다. 2024년 서울 전부개정처럼 번호가 통째로 바뀌어도 찾는다.
  제목에 '용도지역'과 '건폐율'/'용적률'이 함께 있는 조(예: 제48조 용도지역 안에서의 용적률)만 본다.
  '그 밖의 용적률'(학교이적지 등 특수 부지 값), '강화', '완화' 조는 같은 용도지역 이름에 다른 숫자가 붙어 있어 제외한다.
  (실제 서울 조례 제49조에 "제3종일반주거지역: 200퍼센트"(학교이적지)가 있다.)
  그런 조가 없으면 아무 값도 뽑지 않는다. 다른 조로 대신 읽으면 특수 부지 값을 기본값으로 잘못 제안하게 된다.
- "제3종일반주거지역 : 250퍼센트" 처럼 용도지역 이름 바로 뒤에 숫자가 오는 경우만 인정한다.
  단서·완화 조항의 문장형 숫자는 잡지 않는다 (잘못 뽑느니 못 뽑고 사람에게 넘긴다).
- 같은 용도지역 값이 여러 개 나오면 모두 돌려주고, 판단은 비교 단계에서 한다.
  기본값 목록은 보통 제1항에 있고 예외(주거 비율별 주상복합, 취락지구 등)는 ②항·'다만' 뒤에 온다. 그래서 그 앞부분에서
  찾은 값을 primary 로 따로 모은다 (일괄 수집에서 값이 여러 개일 때 우선 쓴다).
- 천 단위 쉼표("1,300퍼센트")와 법령식 한글 단위("1천퍼센트", "1천300퍼센트", "1천2백퍼센트")를 숫자로 바꿔 읽는다.
- "중심상업지역: 1천퍼센트(단, 서울도심: 800퍼센트)" 의 괄호 값은 구역별 기준(subareas)으로 따로 모은다.
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
_SUBAREA = re.compile(rf"({ZONE})[:：]?\d{{1,4}}(?:퍼센트|%)\(단,([^:：()]+)[:：](\d{{1,4}})(?:퍼센트|%)\)")

KINDS = {"bcr": "건폐율", "far": "용적률"}


@dataclass
class Extracted:
    values: dict[str, dict[str, list[int]]] = field(default_factory=lambda: {"bcr": {}, "far": {}})
    articles: dict[str, list[str]] = field(default_factory=lambda: {"bcr": [], "far": []})
    # kind → 구역 이름(예: 서울도심) → 용도지역 → 값
    subareas: dict[str, dict[str, dict[str, int]]] = field(default_factory=lambda: {"bcr": {}, "far": {}})
    # 제1항(②항·'다만' 앞)에서 찾은 값. kind → 용도지역 → 값 목록
    primary: dict[str, dict[str, list[int]]] = field(default_factory=lambda: {"bcr": {}, "far": {}})
    # 읽은 조문 전문(공백 제거·숫자 정규화 후). 못 찾은 용도지역 진단용
    texts: dict[str, str] = field(default_factory=lambda: {"bcr": "", "far": ""})

# 기본값 목록이 끝나고 예외가 시작되는 표시 (공백을 지운 문장 기준)
_EXCEPTION_START = re.compile(r"②|다만|제1항에도불구하고")


def extract(articles: list[Article]) -> Extracted:
    out = Extracted()
    for kind, word in KINDS.items():
        found: dict[str, list[int]] = defaultdict(list)
        primary: dict[str, list[int]] = defaultdict(list)
        candidates = [a for a in articles if word in a.title]
        chosen = [a for a in candidates if "용도지역" in a.title]
        for a in chosen:
            out.articles[kind].append(f"제{a.number}조({a.title})")
            flat = _normalize_numbers(re.sub(r"\s+", "", a.text))
            for zone, pct in _VALUE.findall(flat):
                v = int(pct)
                if v not in found[zone]:
                    found[zone].append(v)
            out.texts[kind] += flat
            head = _EXCEPTION_START.split(flat, maxsplit=1)[0]
            for zone, pct in _VALUE.findall(head):
                if int(pct) not in primary[zone]:
                    primary[zone].append(int(pct))
            for zone, name, pct in _SUBAREA.findall(flat):
                out.subareas[kind].setdefault(name, {})[zone] = int(pct)
        out.values[kind] = dict(found)
        out.primary[kind] = dict(primary)
    return out


def _normalize_numbers(s: str) -> str:
    """'1,300퍼센트' → '1300퍼센트', '1천퍼센트'·'1천2백퍼센트' → '1000퍼센트'·'1200퍼센트'."""
    s = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", s)
    # 법령 표기: 1천500 = 1500, 1천50 = 1050 (천 뒤 숫자가 바로 붙는 형식)
    s = re.sub(r"(\d+)천(\d{1,3})(?=퍼센트|%)", lambda m: str(int(m[1]) * 1000 + int(m[2])), s)
    s = re.sub(r"(\d+)천(\d+)백", lambda m: str(int(m[1]) * 1000 + int(m[2]) * 100), s)
    s = re.sub(r"(\d+)천(?!\d)", lambda m: str(int(m[1]) * 1000), s)
    return re.sub(r"(\d+)백(?!\d)", lambda m: str(int(m[1]) * 100), s)
