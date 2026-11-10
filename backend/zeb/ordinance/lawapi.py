"""법제처 국가법령정보 공동활용(Open API) 자치법규 조회.

- 목록: http://www.law.go.kr/DRF/lawSearch.do?target=ordin  (자치법규명, 자치법규ID, 자치법규일련번호, 공포일자, 시행일자, 지자체기관명)
- 본문: http://www.law.go.kr/DRF/lawService.do?target=ordin  (조문번호, 조제목, 조내용 …)
- OC(인증값)는 신청 시 등록한 서버 IP·도메인에서만 동작한다. 그래서 고정 IP 가 있는 배포 서버에서 실행한다.
- 운영 서버에 바로 설치된 파이썬에서도 돌도록 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

BASE = "https://www.law.go.kr/DRF"

class LawApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrdinanceVersion:
    name: str
    ordinance_id: str
    serial: str  # 자치법규일련번호 (MST). 개정될 때마다 바뀐다
    promulgated_on: str  # YYYY-MM-DD
    effective_on: str | None
    org: str | None


@dataclass(frozen=True)
class Article:
    number: str  # 예: "44"
    title: str  # 예: "용도지역안에서의 건폐율"
    text: str  # 조·항·호 내용을 이어 붙인 전문


def _urlopen(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fitagent-ordinance-watch/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8")


def _norm_key(k: str) -> str:
    return k.replace(" ", "")


def _walk(obj: Any):
    """중첩된 응답에서 dict 를 모두 꺼낸다. 응답 최상위 이름이 문서에 없어 구조에 기대지 않는다."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _texts(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts(v)


def _norm_title(s: str) -> str:
    """조례명 비교용: 공백과 '[제명개정 2020. 10. 5.]' 같은 꼬리표를 뗀다 (청도군)."""
    return re.sub(r"\[[^\]]*\]", "", s).replace(" ", "")


def _date(v: Any) -> str | None:
    s = "".join(ch for ch in str(v or "") if ch.isdigit())
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else None


class LawClient:
    def __init__(self, oc: str, fetch: Callable[[str], str] = _urlopen):
        if not oc:
            raise LawApiError("법제처 API 인증값(LAW_OC)이 없습니다.")
        self.oc = oc
        self.fetch = fetch

    def _get(self, path: str, params: dict[str, str]) -> Any:
        url = f"{BASE}/{path}?" + urllib.parse.urlencode({"OC": self.oc, "type": "JSON", **params})
        try:
            body = self.fetch(url)
        except OSError as e:  # urllib 오류(URLError·HTTPError·timeout). 문구에 URL(인증값 포함)이 섞이지 않게 형식만 남긴다
            raise LawApiError(f"법제처 API 연결 실패 ({type(e).__name__})") from None
        try:
            data = json.loads(body)
        except ValueError:
            raise LawApiError("법제처 API 응답이 JSON 이 아닙니다 (인증값·등록 IP 확인).") from None
        if isinstance(data, dict) and "result" in data and "msg" in data and len(data) <= 3:
            # 예: {"result": "사용자 정보 검증에 실패하였습니다.", "msg": "...서버장비의 IP주소 및 도메인주소를 등록해 주세요."}
            raise LawApiError(f"법제처 API 거부: {data['result']} {data['msg']}".replace(self.oc, "***"))
        return data

    def latest(
        self, name: str, org: str | None = None, agency_ok: Callable[[str], bool] | None = None
    ) -> OrdinanceVersion:
        """현행 자치법규 중 이름이 정확히 같은 것. agency_ok 로 지자체기관명을 거른다 (예: 강원·경남 고성군)."""
        params = {"target": "ordin", "query": name, "display": "100", "nw": "1"}
        if org:
            params["org"] = org
        data = self._get("lawSearch.do", params)
        want = _norm_title(name)
        hits, other_agency, similar = [], [], []
        for d in _walk(data):
            row = {_norm_key(k): v for k, v in d.items()}
            if not row.get("자치법규ID"):
                continue
            title = str(row.get("자치법규명", ""))
            if _norm_title(title) == want:
                if agency_ok is None or agency_ok(str(row.get("지자체기관명", ""))):
                    hits.append(row)
                else:
                    other_agency.append(str(row.get("지자체기관명", "")))
            else:
                similar.append(f"{title}({row.get('지자체기관명', '')})")
        if not hits:
            # 원인 진단용: 같은 이름인데 기관명이 달랐는지(도 이름 변경 등), 비슷한 이름이 있었는지
            hint = ""
            if other_agency:
                hint = f" — 같은 이름이 다른 기관명으로 있음: {', '.join(sorted(set(other_agency))[:3])}"
            elif similar:
                hint = f" — 검색 결과: {', '.join(similar[:3])}"
            raise LawApiError(f"자치법규를 찾지 못했습니다: {name}{hint}")
        row = max(hits, key=lambda r: str(r.get("공포일자", "")))
        return OrdinanceVersion(
            name=name,
            ordinance_id=str(row["자치법규ID"]),
            serial=str(row.get("자치법규일련번호", "")),
            promulgated_on=_date(row.get("공포일자")) or "",
            effective_on=_date(row.get("시행일자")),
            org=row.get("지자체기관명"),
        )

    def articles(self, version: OrdinanceVersion) -> list[Article]:
        params = {"target": "ordin"}
        if version.serial:
            params["MST"] = version.serial
        else:
            params["ID"] = version.ordinance_id
        data = self._get("lawService.do", params)
        out = []
        for d in _walk(data):
            row = {_norm_key(k): v for k, v in d.items()}
            if "조내용" not in row or str(row.get("조문여부", "Y")).upper() == "N":
                continue
            text = " ".join(t.strip() for t in _texts(d) if isinstance(t, str) and t.strip())
            head = _HEAD.search(str(row.get("조내용", "")))
            if head:
                number = head.group(1) + (f"의{head.group(2)}" if head.group(2) else "")
            else:
                number = str(row.get("조문번호", "")).lstrip("0")
            title = str(row.get("조제목") or (head.group(3) if head and head.group(3) else ""))
            out.append(Article(number, title, text))
        return out


# "제44조(용도지역 안에서의 건폐율)" / "제49조의2(…)"
_HEAD = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*(?:\(([^)]*)\))?")
