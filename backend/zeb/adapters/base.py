from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ParcelSummary:
    pnu: str
    address: str
    lat: float | None = None
    lng: float | None = None


@dataclass
class Parcel:
    pnu: str
    address: str
    area_m2: float
    zone: str
    # 토지이용계획: 필지에 '포함'되는 지역·지구 / 일부만 걸치는('저촉') / 경계에 '접함'
    land_use_plans: list[str] = field(default_factory=list)
    partial_plans: list[str] = field(default_factory=list)
    adjacent_plans: list[str] = field(default_factory=list)
    land_category: str | None = None  # 지목 (대, 도로, 하천 ...)
    secondary_zone: str | None = None  # 토지특성 용도지역2 (두 용도지역에 걸친 필지)
    lat: float | None = None
    lng: float | None = None
    data_source: str = "sample"  # "sample" | "vworld"
    reference_year: str | None = None  # 토지특성 기준년도
    tags: list[str] = field(default_factory=list)

    @property
    def jurisdiction(self) -> str:
        """PNU 앞 5자리 = 시군구코드 (앞 2자리 = 시도코드)."""
        return self.pnu[:5]


class ProviderError(RuntimeError):
    """외부 데이터 조회 실패. 샘플 데이터로 조용히 대체하지 않는다."""


class ParcelProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int = 10) -> list[ParcelSummary]: ...

    async def get(self, pnu: str) -> Parcel | None: ...
