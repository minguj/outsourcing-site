"""브이월드(VWorld) 오픈API 어댑터.

사용 API
 1) 검색 API 2.0   (지번 주소 → PNU, 좌표)         /req/search  type=address, category=parcel
 2) 토지특성정보   (PNU → 토지면적, 용도지역명)     /ned/data/getLandCharacteristics
 3) 토지이용계획   (PNU → 지역·지구 목록)            /ned/data/getLandUseAttr

주의
 - 브이월드 인증키는 '서비스 URL(도메인)'에 묶인다. 배포 도메인을 키 발급 시 등록하고
   같은 값을 VWORLD_DOMAIN 으로 넘긴다.
 - 응답 필드명은 아래 FIELD_MAP 한곳에서만 다룬다. 키 발급 후
   `python scripts/check_vworld.py <지번주소>` 로 실제 응답을 확인하고 필요하면 이 표만 고친다.
 - 조회 실패 시 샘플 데이터로 대체하지 않고 ProviderError 를 던진다.
   (실데이터인 척하는 샘플 결과가 보고서로 나가는 것이 가장 나쁜 실패이기 때문)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import Parcel, ParcelSummary, ProviderError

BASE = "https://api.vworld.kr"

FIELD_MAP = {
    # 토지특성정보
    "lc_container": ("landCharacteristicss", "field"),
    "lc_area": ("lndpclAr",),
    "lc_zone": ("prposArea1Nm",),
    "lc_year": ("stdrYear",),
    "lc_address": ("ldCodeNm",),
    "lc_lot": ("mnnmSlno",),
    "lc_zone2": ("prposArea2Nm",),
    "lc_land_category": ("lndcgrCodeNm",),
    # 토지이용계획
    "lu_container": ("landUses", "field"),
    "lu_name": ("prposAreaDstrcCodeNm", "prposAreaDstrcNm"),
    "lu_relation": ("cnflcAtNm",),  # 포함 / 저촉(일부 걸침) / 접함(경계만 맞닿음)
}

NO_ZONE = {"", "지정되지않음", "미지정", "None"}


def _dig(obj: Any, path: tuple[str, ...]) -> Any:
    for k in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _first(row: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        if row.get(k) not in (None, ""):
            return row[k]
    return None


def _as_list(v: Any) -> list[dict]:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


class _TTLCache:
    def __init__(self, ttl: float = 3600) -> None:
        self.ttl = ttl
        self._d: dict[str, tuple[float, Any]] = {}

    def get(self, k: str) -> Any:
        hit = self._d.get(k)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        return None

    def set(self, k: str, v: Any) -> None:
        self._d[k] = (time.monotonic(), v)


class VWorldParcelProvider:
    name = "vworld"

    def __init__(self, api_key: str, domain: str, timeout: float = 8.0, client: httpx.AsyncClient | None = None):
        self.key = api_key
        self.domain = domain
        self._client = client or httpx.AsyncClient(base_url=BASE, timeout=timeout)
        self._cache = _TTLCache()

    async def _get(self, path: str, params: dict) -> dict:
        q = {"key": self.key, "domain": self.domain, "format": "json", **params}
        # 오류 문구는 화면까지 전달된다. httpx 예외 문자열에는 요청 URL(인증키 포함)이 들어 있으므로
        # 예외를 그대로 문자열로 만들지 않고, 상태 코드·예외 종류만 담은 문구를 직접 만든다.
        try:
            r = await self._client.get(path, params=q)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(self._redact(f"브이월드 서버 응답 오류 (HTTP {e.response.status_code})")) from None
        except httpx.HTTPError as e:
            raise ProviderError(f"브이월드 서버에 연결하지 못했습니다 ({type(e).__name__})") from None
        except ValueError:
            raise ProviderError("브이월드 응답을 해석하지 못했습니다") from None
        status = _dig(data, ("response", "status"))
        if status and status not in ("OK", "NOT_FOUND"):
            err = _dig(data, ("response", "error", "text")) or status
            raise ProviderError(self._redact(f"브이월드 오류: {err}"))
        return data

    def _redact(self, text: str) -> str:
        return text.replace(self.key, "***") if self.key else text

    async def search(self, query: str, limit: int = 10) -> list[ParcelSummary]:
        if not query.strip():
            return []
        data = await self._get(
            "/req/search",
            {
                "service": "search",
                "request": "search",
                "version": "2.0",
                "crs": "EPSG:4326",
                "size": limit,
                "page": 1,
                "query": query,
                "type": "address",
                "category": "parcel",
                "errorformat": "json",
            },
        )
        items = _as_list(_dig(data, ("response", "result", "items")))
        out = []
        for it in items:
            pnu = it.get("id")
            addr = _dig(it, ("address", "parcel")) or it.get("title") or ""
            pt = it.get("point") or {}
            if pnu:
                out.append(ParcelSummary(pnu, addr, _float(pt.get("y")), _float(pt.get("x"))))
        return out

    async def get(self, pnu: str) -> Parcel | None:
        cached = self._cache.get(pnu)
        if cached:
            return cached

        lc = await self._get("/ned/data/getLandCharacteristics", {"pnu": pnu, "numOfRows": 10, "pageNo": 1})
        if not _as_list(_dig(lc, FIELD_MAP["lc_container"])):
            return None
        lu = await self._get("/ned/data/getLandUseAttr", {"pnu": pnu, "numOfRows": 100, "pageNo": 1})
        parcel = parse_land(pnu, lc, lu)
        self._cache.set(pnu, parcel)
        return parcel


def parse_land(pnu: str, land_characteristics: dict, land_use_attr: dict) -> Parcel:
    """토지특성 + 토지이용계획 원본 응답 → Parcel.

    서버가 직접 조회한 응답(VWorldParcelProvider)과, 브라우저가 조회해 보낸 응답(브라우저 조회 모드)이
    모두 이 함수 하나로 해석된다. 해석 규칙을 한곳에 두어 테스트가 두 경로를 함께 지킨다.
    """
    rows = [r for r in _as_list(_dig(land_characteristics, FIELD_MAP["lc_container"])) if isinstance(r, dict)]
    rows = [r for r in rows if str(r.get("pnu", pnu)) == pnu] or rows
    if not rows:
        raise ProviderError("토지특성 정보가 없는 필지입니다.")
    # 가장 최근 기준년도 행
    row = max(rows, key=lambda r: str(_first(r, FIELD_MAP["lc_year"]) or ""))
    area = _float(_first(row, FIELD_MAP["lc_area"]))
    zone = _first(row, FIELD_MAP["lc_zone"])
    if area is None or area <= 0 or not zone:
        raise ProviderError("토지특성 응답에서 면적/용도지역을 찾지 못했습니다.")

    # 관계별로 나눈다. '접함'(인접 필지의 지역·지구)을 이 필지의 규제로 취급하면 잘못된 경고가 나간다.
    by_rel: dict[str, set[str]] = {"포함": set(), "저촉": set(), "접함": set()}
    for r in _as_list(_dig(land_use_attr, FIELD_MAP["lu_container"])):
        if not isinstance(r, dict):
            continue
        name = _first(r, FIELD_MAP["lu_name"])
        if not name:
            continue
        rel = str(_first(r, FIELD_MAP["lu_relation"]) or "포함")
        by_rel.setdefault(rel, set()).add(str(name)[:60])
    included = by_rel["포함"]
    partial = by_rel["저촉"] - included
    adjacent = by_rel["접함"] - included - partial

    address = " ".join(
        str(x) for x in (_first(row, FIELD_MAP["lc_address"]), _first(row, FIELD_MAP["lc_lot"])) if x
    )
    category = _first(row, FIELD_MAP["lc_land_category"])
    return Parcel(
        pnu=pnu,
        address=(address or pnu)[:100],
        area_m2=area,
        zone=normalize_zone(str(zone)),
        land_use_plans=sorted(included),
        partial_plans=sorted(partial),
        adjacent_plans=sorted(adjacent),
        land_category=str(category)[:20] if category else None,
        secondary_zone=_zone2(row),
        data_source="vworld",
        reference_year=str(_first(row, FIELD_MAP["lc_year"]) or ""),
    )


def _float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _zone2(row: dict) -> str | None:
    z = _first(row, FIELD_MAP["lc_zone2"])
    return None if z is None or str(z).strip() in NO_ZONE else normalize_zone(str(z))


def normalize_zone(name: str) -> str:
    """'제2종 일반주거지역' 같은 표기 차이를 규칙 키 형태로 맞춘다."""
    return name.replace(" ", "")
