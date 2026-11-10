"""조문에서 용도지역별 건폐율·용적률(%)을 뽑는다.

- 조 번호가 아니라 조 제목으로 조문을 고른다. 2024년 서울 전부개정처럼 번호가 통째로 바뀌어도 찾는다.
  제목에 '용도지역'과 '건폐율'/'용적률'이 함께 있는 조(예: 제48조 용도지역 안에서의 용적률)만 본다.
  '용도구역·지역·지구안에서의 건폐율'(여수 제33조)처럼 '용도'와 '지역'이 떨어져 있는 제목도 같은 조로 본다.
  '그 밖의 용적률'(학교이적지 등 특수 부지 값), '강화', '완화' 조는 같은 용도지역 이름에 다른 숫자가 붙어 있어 제외한다.
  (실제 서울 조례 제49조에 "제3종일반주거지역: 200퍼센트"(학교이적지)가 있다.)
  그런 조가 없으면 아무 값도 뽑지 않는다. 다른 조로 대신 읽으면 특수 부지 값을 기본값으로 잘못 제안하게 된다.
- "제3종일반주거지역 : 250퍼센트" 처럼 용도지역 이름 바로 뒤에 숫자가 오는 경우만 인정한다.
  단서·완화 조항의 문장형 숫자는 잡지 않는다 (잘못 뽑느니 못 뽑고 사람에게 넘긴다).
- 같은 용도지역 값이 여러 개 나오면 모두 돌려주고, 판단은 비교 단계에서 한다.
  기본값 목록은 보통 제1항에 있고 예외(주거 비율별 주상복합, 취락지구 등)는 ②항·'다만' 뒤에 온다. 그래서 그 앞부분에서
  찾은 값을 primary 로 따로 모은다 (일괄 수집에서 값이 여러 개일 때 우선 쓴다).
- 천 단위 쉼표("1,300퍼센트")와 법령식 한글 단위("1천퍼센트", "1천300퍼센트", "1천2백퍼센트")를 숫자로 바꿔 읽는다.
- 조문 오타 '준주거지 : 500 퍼센트'(태백, '역' 빠짐)처럼 이름 끝 '역'이 빠지고 바로 쌍점이 오면 용도지역 이름으로 고쳐 읽는다.
- "100분의 60 이하"(= 60퍼센트) 형식도 읽는다 (군포: "제1종 전용주거지역 : 100분의 40 이하").
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
# 이름과 숫자 사이에 '일반건축은', '일반건축물:' 이 끼는 형식도 받는다 (수원: "제2종일반주거지역: 일반건축은 250퍼센트 이하(다만, 공동주택…)")
_LABEL = r"(?:일반건축물?(?:은|는|[:：])?)?"
# 단위: 퍼센트·%. 실제 조문의 오타 '퍼센터'(아산), '센트'(옥천)도 받는다
_UNIT = r"(?:퍼센트|퍼센터|센트|%)"
_VALUE = re.compile(rf"({ZONE})[:：]?{_LABEL}(\d{{1,4}}){_UNIT}")
_SUBAREA = re.compile(rf"({ZONE})[:：]?\d{{1,4}}{_UNIT}\(단,([^:：()]+)[:：](\d{{1,4}}){_UNIT}\)")

# 이름 끝 '역'이 빠진 오타 (태백 제56조 "준주거지 : 500 퍼센트"). 쌍점이 바로 뒤에 올 때만 고친다
_ZONE_TYPO = re.compile(r"(" + ZONE.replace("지역", "") + r")지(?=[:：])")
KINDS = {"bcr": "건폐율", "far": "용적률"}
# '용도지역', '용도구역·지역·지구' (괄호 안까지 넘어가지 않게 한다)
_ZONING_TITLE = re.compile(r"용도[^()]{0,8}지역")
# '그 밖의 용도지역ㆍ지구 등에서의 건폐율'(수원 제67조)은 용도지구·구역 값을 정한 조라 제외한다
_OTHER_TITLE = re.compile(r"그\s*밖의")


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
        chosen = [a for a in candidates if _ZONING_TITLE.search(a.title) and not _OTHER_TITLE.search(a.title)]
        for a in chosen:
            out.articles[kind].append(f"제{a.number}조({a.title})")
            flat = _normalize_numbers(re.sub(r"\s+", "", _normalize_spaced(a.text)))
            flat = _ZONE_TYPO.sub(r"\1지역", flat)
            for zone, pct in _VALUE.findall(flat):
                v = int(pct)
                if v not in found[zone]:
                    found[zone].append(v)
            out.texts[kind] += flat
            # 예외 표시는 첫 값 이후부터 찾는다 (군포처럼 목록 앞 본문에 '다만,'이 먼저 나오는 경우)
            first = _VALUE.search(flat)
            cut = _EXCEPTION_START.search(flat, first.start()) if first else None
            head = flat[: cut.start()] if cut else flat
            for zone, pct in _VALUE.findall(head):
                if int(pct) not in primary[zone]:
                    primary[zone].append(int(pct))
            for zone, name, pct in _SUBAREA.findall(flat):
                out.subareas[kind].setdefault(name, {})[zone] = int(pct)
        out.values[kind] = dict(found)
        out.primary[kind] = dict(primary)
    return out


def _normalize_spaced(s: str) -> str:
    """공백을 지우기 전에 처리해야 하는 표기. 공백을 먼저 지우면 다음 호 번호가 숫자에 붙는다
    (전주: '100분의 40 2. 제2종…' → '100분의402' 로 읽혀 402% 가 됐다)."""
    s = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", s)
    # 100분의 60 = 60퍼센트 ("100분 의 280" 처럼 띄어 써도)
    return re.sub(r"100\s*분\s*의\s*(\d{1,4})(?!\d)", r"\1퍼센트", s)


def _normalize_numbers(s: str) -> str:
    """'1천퍼센트'·'1천300퍼센트'·'1천2백퍼센트' → '1000퍼센트'·'1300퍼센트'·'1200퍼센트'."""
    # 법령 표기: 1천500 = 1500, 1천50 = 1050 (천 뒤 숫자가 바로 붙는 형식)
    s = re.sub(r"(\d+)천(\d{1,3})(?=퍼센트|%)", lambda m: str(int(m[1]) * 1000 + int(m[2])), s)
    s = re.sub(r"(\d+)천(\d+)백", lambda m: str(int(m[1]) * 1000 + int(m[2]) * 100), s)
    s = re.sub(r"(\d+)천(?!\d)", lambda m: str(int(m[1]) * 1000), s)
    return re.sub(r"(\d+)백(?!\d)", lambda m: str(int(m[1]) * 100), s)
