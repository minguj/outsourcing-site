"""건축 규모 산정 (초기 기획용 볼륨 검토).

단순화한 가정
 - 지상 연면적(용적률 산정용)만 다룬다. 지하층·주차장 면적은 제외.
 - 기준층 면적 = 건축면적(정형 매스, 전 층 동일 바닥면적).
 - 정북일조·도로사선 등 형태 규제는 '높이 제한(m)' 입력으로만 반영한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .rules import RuleBook
from .trace import INPUT, Ledger, Source


@dataclass(frozen=True)
class MassingInput:
    site_area_m2: float
    zone: str
    jurisdiction: str | None
    building_use: str
    height_limit_m: float | None = None
    floor_height_m: float | None = None
    far_incentive_rate: float = 0.0  # % (ZEB 인증 완화 등)
    incentive_source: Source | None = None


@dataclass(frozen=True)
class MassingResult:
    bcr_pct: float
    far_pct: float
    far_effective_pct: float
    max_building_area_m2: float
    max_gfa_m2: float
    floors: int
    building_area_m2: float
    gfa_m2: float
    height_m: float
    floor_height_m: float
    binding_constraint: str  # "용적률" | "높이" | "층수"
    far_utilization_pct: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _r(x: float, nd: int = 2) -> float:
    return round(x + 0.0, nd)


def compute_massing(inp: MassingInput, rules: RuleBook, ledger: Ledger, floor_height_default: float) -> MassingResult:
    if inp.site_area_m2 <= 0:
        raise ValueError("대지면적은 0보다 커야 합니다")

    ledger.record("site_area", "대지면적", _r(inp.site_area_m2), "㎡", "입력값", sources=[INPUT])

    z = rules.resolve_zone(inp.zone, inp.jurisdiction, inp.building_use)

    # 1) 건폐율 -----------------------------------------------------------
    if z.ordinance:
        bcr = min(z.ordinance.bcr, z.national.bcr)
        ledger.record(
            "bcr",
            "적용 건폐율",
            bcr,
            "%",
            "min(조례 건폐율, 법정 상한)",
            {"조례": z.ordinance.bcr, "법정 상한": z.national.bcr},
            [z.ordinance.source, z.national.source],
        )
    else:
        bcr = z.national.bcr
        ledger.record(
            "bcr", "적용 건폐율", bcr, "%", "법정 상한 (조례 미등록)", {"법정 상한": bcr}, [z.national.source]
        )
        ledger.warn(
            "ORDINANCE_MISSING",
            f"관할 지자체({inp.jurisdiction or '미상'}) 도시계획 조례가 등록되지 않아 법정 상한을 적용했습니다. "
            "실제 허용치는 이보다 낮을 수 있습니다.",
            "critical",
        )

    # 2) 용적률 -----------------------------------------------------------
    if z.use_override_far:
        ord_far, ord_src = z.use_override_far
        label = f"조례 ({inp.building_use} 기준)"
    elif z.ordinance:
        ord_far, ord_src = z.ordinance.far, z.ordinance.source
        label = "조례"
    else:
        ord_far, ord_src = None, None
        label = ""

    if ord_far is not None:
        far = min(ord_far, z.national.far)
        ledger.record(
            "far",
            "적용 용적률",
            far,
            "%",
            f"min({label} 용적률, 법정 상한)",
            {label: ord_far, "법정 상한": z.national.far},
            [ord_src, z.national.source],
        )
    else:
        far = z.national.far
        ledger.record(
            "far", "적용 용적률", far, "%", "법정 상한 (조례 미등록)", {"법정 상한": far}, [z.national.source]
        )

    far_eff = far
    if inp.far_incentive_rate > 0:
        far_eff = far * (1 + inp.far_incentive_rate / 100)
        ledger.record(
            "far_effective",
            "인센티브 반영 용적률",
            _r(far_eff),
            "%",
            "적용 용적률 × (1 + 완화비율)",
            {"적용 용적률": far, "완화비율(%)": inp.far_incentive_rate},
            [inp.incentive_source] if inp.incentive_source else [],
        )
        ledger.warn(
            "INCENTIVE_APPLIED",
            "ZEB 인증 용적률 완화를 반영했습니다. 건축위원회 심의 및 허가조건으로 확정되는 값입니다.",
            "info",
        )

    # 3) 최대 건축면적 / 연면적 --------------------------------------------
    max_ba = inp.site_area_m2 * bcr / 100
    ledger.record(
        "max_building_area",
        "최대 건축면적",
        _r(max_ba),
        "㎡",
        "대지면적 × 건폐율",
        {"대지면적": _r(inp.site_area_m2), "건폐율(%)": bcr},
    )
    max_gfa = inp.site_area_m2 * far_eff / 100
    ledger.record(
        "max_gfa",
        "최대 지상 연면적",
        _r(max_gfa),
        "㎡",
        "대지면적 × 용적률",
        {"대지면적": _r(inp.site_area_m2), "용적률(%)": _r(far_eff)},
    )

    # 4) 층수 -------------------------------------------------------------
    fh = inp.floor_height_m or floor_height_default
    fh_src = INPUT if inp.floor_height_m else rules.assumption_source(f"building_uses.{inp.building_use}.floor_height")
    ledger.record(
        "floor_height", "층고", fh, "m", "입력값" if inp.floor_height_m else "용도별 가정값", sources=[fh_src]
    )

    floors_needed = max(1, math.ceil(round(max_gfa / max_ba, 9)))
    ledger.record(
        "floors_by_far",
        "용적률 소진에 필요한 층수",
        floors_needed,
        "층",
        "올림(최대 연면적 ÷ 최대 건축면적)",
        {"최대 연면적": _r(max_gfa), "최대 건축면적": _r(max_ba)},
    )

    caps: list[tuple[int, str]] = []
    if inp.height_limit_m:
        by_height = max(1, math.floor(round(inp.height_limit_m / fh, 9)))
        ledger.record(
            "floors_by_height",
            "높이 제한에 따른 최대 층수",
            by_height,
            "층",
            "내림(높이 제한 ÷ 층고)",
            {"높이 제한(m)": inp.height_limit_m, "층고(m)": fh},
            [INPUT],
        )
        caps.append((by_height, "높이"))
    zone_floor_cap = z.ordinance.max_floors if z.ordinance else None
    if zone_floor_cap:
        ledger.record(
            "floors_by_zone",
            "용도지역 층수 제한",
            zone_floor_cap,
            "층",
            "용도지역 세분 기준",
            sources=[z.ordinance.source],
        )
        caps.append((zone_floor_cap, "층수"))

    floors = floors_needed
    binding = "용적률"
    for cap, name in caps:
        if cap < floors:
            floors, binding = cap, name

    gfa = min(max_gfa, max_ba * floors)
    building_area = gfa / floors
    height = floors * fh

    ledger.record(
        "floors",
        "계획 층수",
        floors,
        "층",
        "min(용적률 소진 층수, 높이·층수 제한)",
        {"용적률 소진 층수": floors_needed, **{f"{n} 제한": c for c, n in caps}},
    )
    ledger.record(
        "gfa",
        "계획 지상 연면적",
        _r(gfa),
        "㎡",
        "min(최대 연면적, 최대 건축면적 × 계획 층수)",
        {"최대 연면적": _r(max_gfa), "최대 건축면적": _r(max_ba), "계획 층수": floors},
    )
    ledger.record(
        "building_area",
        "계획 건축면적(기준층)",
        _r(building_area),
        "㎡",
        "계획 연면적 ÷ 계획 층수",
        {"계획 연면적": _r(gfa), "계획 층수": floors},
    )
    ledger.record("height", "건물 높이(추정)", _r(height), "m", "계획 층수 × 층고", {"계획 층수": floors, "층고": fh})

    utilization = gfa / max_gfa * 100
    if binding != "용적률":
        ledger.warn(
            "FAR_NOT_EXHAUSTED",
            f"{binding} 제한 때문에 허용 용적률의 {utilization:.1f}%만 사용합니다. "
            "층고 조정이나 형태 검토로 개선 여지가 있는지 확인하세요.",
        )

    return MassingResult(
        bcr_pct=bcr,
        far_pct=far,
        far_effective_pct=_r(far_eff),
        max_building_area_m2=_r(max_ba),
        max_gfa_m2=_r(max_gfa),
        floors=floors,
        building_area_m2=_r(building_area),
        gfa_m2=_r(gfa),
        height_m=_r(height),
        floor_height_m=fh,
        binding_constraint=binding,
        far_utilization_pct=_r(utilization, 1),
    )
