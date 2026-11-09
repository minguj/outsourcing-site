"""초기 기획(대지 규모 + ZEB 시나리오) 데모 API.

도메인 계산은 zeb/domain 에 있고, 여기서는 입출력 변환만 한다.
브이월드 키(VWORLD_API_KEY)가 없으면 데모 샘플 필지로만 동작한다.

브이월드 조회 방식 (VWORLD_MODE)
 - browser (기본): 브이월드는 해외·클라우드 IP 를 차단한다. 운영 서버(시드니)에서는 호출이 막히므로
   방문자 브라우저(국내 IP)가 직접 조회하고, 원본 응답을 /feasibility 의 vworld_raw 로 보낸다.
   해석은 서버의 parse_land 가 맡는다. 키는 브이월드 지도 API 처럼 페이지에 전달되며 등록 도메인으로 제한된다.
 - server: 국내 IP 서버에서 운영할 때. 서버가 직접 조회한다.
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from datetime import date
from threading import Lock
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .adapters.base import Parcel, ParcelProvider, ProviderError
from .adapters.sample import RedevelopmentCatalog, SampleParcelProvider
from .adapters.vworld import VWorldParcelProvider, parse_land
from .domain.feasibility import ENGINE_VERSION, PlanOptions, SiteInput, run_feasibility
from .domain.rules import RuleBook, RuleNotFound

router = APIRouter(prefix="/api/demo/zeb")

Source = Literal["auto", "sample", "vworld"]
MAX_RAW_CHARS = 300_000

_sample = SampleParcelProvider()
_redev = RedevelopmentCatalog()
_vworld: VWorldParcelProvider | None = None
_vworld_key: str | None = None

# 브이월드 일일 호출 한도를 지키기 위한 전역 분당 상한 (데모 공개 페이지 보호)
VWORLD_PER_MINUTE = int(os.getenv("VWORLD_PER_MINUTE", "60"))
_calls: deque[float] = deque()
_calls_lock = Lock()


def _vworld_mode() -> str:
    return "server" if os.getenv("VWORLD_MODE", "browser").strip().lower() == "server" else "browser"


def _vworld_domain() -> str:
    return os.getenv("VWORLD_DOMAIN", "https://fitagent.co.kr")


def _vworld_provider() -> VWorldParcelProvider | None:
    global _vworld, _vworld_key
    key = os.getenv("VWORLD_API_KEY") or None
    if _vworld_mode() != "server":
        key = None
    if key != _vworld_key:
        _vworld_key = key
        _vworld = VWorldParcelProvider(key, _vworld_domain()) if key else None
    return _vworld


def _provider(source: Source) -> ParcelProvider:
    if source == "sample":
        return _sample
    vw = _vworld_provider()
    if source == "vworld" and not vw:
        if _vworld_mode() == "browser" and os.getenv("VWORLD_API_KEY"):
            raise HTTPException(409, "브이월드는 브라우저 조회 방식으로 설정되어 있습니다.")
        raise HTTPException(503, "브이월드 키가 설정되지 않아 실데이터를 조회할 수 없습니다. 샘플 필지를 이용해 주세요.")
    return vw or _sample


def _throttle(prov: ParcelProvider) -> None:
    if prov.name != "vworld":
        return
    now = time.monotonic()
    with _calls_lock:
        while _calls and now - _calls[0] > 60:
            _calls.popleft()
        if len(_calls) >= VWORLD_PER_MINUTE:
            raise HTTPException(429, "조회 요청이 많습니다. 잠시 후 다시 시도해 주세요.")
        _calls.append(now)


def _parcel_dict(p: Parcel) -> dict:
    return {**p.__dict__, "jurisdiction": p.jurisdiction}


@router.get("/meta")
def meta():
    rb = RuleBook()
    grades, _ = rb.zeb_grades()
    key = os.getenv("VWORLD_API_KEY") or None
    mode = _vworld_mode()
    return {
        "engine_version": ENGINE_VERSION,
        "parcel_source": "vworld" if key else "sample",
        "vworld_mode": mode if key else None,
        # 브라우저 조회 모드에서만 내려준다. 브이월드 키는 등록 도메인에서만 동작한다.
        "vworld_key": key if key and mode == "browser" else None,
        "vworld_domain": _vworld_domain() if key else None,
        "building_uses": rb.building_uses(),
        "zones": rb.zone_names(),
        "grades": [g.__dict__ for g in grades],
        "rule_versions": rb.versions(),
    }


@router.get("/rules")
def rules():
    rb = RuleBook()
    return {"zoning": rb.zoning, "zeb": rb.zeb, "assumptions": rb.assumptions, "equipment": rb.equipment}


@router.get("/parcels/search")
async def search_parcels(q: str = Query("", max_length=100), source: Source = "auto"):
    prov = _provider(source)
    if q.strip():
        _throttle(prov)
    try:
        items = await prov.search(q)
    except ProviderError as e:
        raise HTTPException(502, str(e)) from e
    return {"source": prov.name, "items": [i.__dict__ for i in items]}


async def _get_parcel(pnu: str, source: Source) -> Parcel:
    if not (pnu.isdigit() and len(pnu) == 19):
        raise HTTPException(422, "필지 고유번호(PNU)는 19자리 숫자입니다.")
    prov = _provider(source)
    _throttle(prov)
    try:
        p = await prov.get(pnu)
    except ProviderError as e:
        raise HTTPException(502, str(e)) from e
    if not p:
        raise HTTPException(404, "필지를 찾지 못했습니다.")
    return p


@router.get("/parcels/{pnu}")
async def get_parcel(pnu: str, source: Source = "auto"):
    return _parcel_dict(await _get_parcel(pnu, source))


@router.get("/redevelopment/search")
def search_redevelopment(q: str = Query("", max_length=100)):
    return {"source": "sample", "items": _redev.search(q)}


class ManualSite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site_area_m2: float = Field(gt=0, le=1_000_000)
    zone: str = Field(max_length=40)
    jurisdiction: str | None = Field(None, max_length=10, pattern=r"^\d*$")
    address: str | None = Field(None, max_length=100)
    land_use_plans: list[str] = Field(default_factory=list, max_length=30)


class VWorldRaw(BaseModel):
    """브라우저가 브이월드에서 받아 그대로 넘긴 원본 응답 (브라우저 조회 모드)."""

    model_config = ConfigDict(extra="forbid")
    pnu: str = Field(pattern=r"^\d{19}$")
    land_characteristics: dict
    land_use_attr: dict

    @model_validator(mode="after")
    def _size(self):
        if len(json.dumps([self.land_characteristics, self.land_use_attr], ensure_ascii=False)) > MAX_RAW_CHARS:
            raise ValueError("브이월드 응답이 너무 큽니다")
        return self


class FeasibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pnu: str | None = Field(None, max_length=19)
    source: Source = "auto"
    manual: ManualSite | None = None
    vworld_raw: VWorldRaw | None = None

    building_use: str = Field("공동주택", max_length=20)
    height_limit_m: float | None = Field(None, gt=0, le=600)
    floor_height_m: float | None = Field(None, gt=2, le=10)
    is_public: bool = False
    apply_zeb_incentive_grade: Literal["+", "1", "2", "3", "4", "5"] | None = None
    as_of: date | None = None

    @model_validator(mode="after")
    def _one_site(self):
        if sum(map(bool, (self.pnu, self.manual, self.vworld_raw))) != 1:
            raise ValueError("pnu, manual, vworld_raw 중 하나만 지정하세요")
        return self


@router.post("/feasibility")
async def feasibility(req: FeasibilityRequest):
    if req.vworld_raw or req.pnu:
        if req.vworld_raw:
            try:
                p = parse_land(req.vworld_raw.pnu, req.vworld_raw.land_characteristics, req.vworld_raw.land_use_attr)
            except ProviderError as e:
                raise HTTPException(422, str(e)) from None
        else:
            p = await _get_parcel(req.pnu, req.source)
        site = SiteInput(
            site_area_m2=p.area_m2,
            zone=p.zone,
            jurisdiction=p.jurisdiction,
            address=p.address,
            pnu=p.pnu,
            land_use_plans=tuple(p.land_use_plans),
            partial_plans=tuple(p.partial_plans),
            adjacent_plans=tuple(p.adjacent_plans),
            land_category=p.land_category,
            secondary_zone=p.secondary_zone,
            data_source=p.data_source,
        )
    else:
        m = req.manual
        site = SiteInput(
            site_area_m2=m.site_area_m2,
            zone=m.zone,
            jurisdiction=m.jurisdiction or None,
            address=m.address,
            land_use_plans=tuple(m.land_use_plans),
            data_source="manual",
        )

    opts = PlanOptions(
        building_use=req.building_use,
        height_limit_m=req.height_limit_m,
        floor_height_m=req.floor_height_m,
        is_public=req.is_public,
        apply_zeb_incentive_grade=req.apply_zeb_incentive_grade,
        as_of=req.as_of,
    )
    try:
        return run_feasibility(site, opts)
    except (RuleNotFound, ValueError, KeyError) as e:
        raise HTTPException(422, str(e)) from e
