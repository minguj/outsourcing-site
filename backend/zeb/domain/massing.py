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
    target_floors: int | None = None  # 목표 층수. 없으면 최대 건축면적 기준(최소 층수)


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
    binding_constraint: str  # "용적률" | "높이" | "층수" | "목표 층수"
    far_utilization_pct: float
    bcr_used_pct: float  # 실제 사용 건폐율 (계획 건축면적 ÷ 대지면적)
    floors_min_full_far: int  # 용적률을 모두 쓰는 최소 층수 (건폐율 최대 사용 시)
    floors_max: int | None  # 높이·층수 제한에 따른 최대 층수 (제한이 없으면 None)
    floors_max_reason: str | None
    target_floors: int | None

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

    if z.collected:
        ledger.warn(
            "ORDINANCE_COLLECTED",
            f"{z.ordinance.source.title.replace(' (자동 수집)', '')} 값을 자동 수집해 적용했습니다(미검증). "
            "법제처 원문에서 뽑은 값이지만 사람이 확인하기 전이므로 참고용입니다.",
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

    if z.subarea and z.subarea["far"] < far:
        ledger.warn(
            "SUBAREA",
            f"{z.subarea['name']}에 해당하면 용적률이 {z.subarea['far']}%로 낮아집니다 ({z.subarea['note']}). "
            f"구 전체가 해당하지는 않으므로 지금은 {far}%로 계산했습니다. 대상지 위치를 확인하세요.",
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

    floors_max, cap_reason = (min(caps) if caps else (None, None))

    if inp.target_floors:
        # 목표 층수: 같은 연면적을 더 높게(건축면적은 작게) 짓거나, 더 낮게(연면적 일부 포기) 짓는다.
        ledger.record("floors_target", "목표 층수", inp.target_floors, "층", "입력값", sources=[INPUT])
        floors = inp.target_floors
        binding = "용적률" if floors >= floors_needed else "목표 층수"
        if floors_max is not None and floors > floors_max:
            ledger.warn(
                "TARGET_FLOORS_CAPPED",
                f"목표 {inp.target_floors}층은 {cap_reason} 제한({floors_max}층)을 넘어 {floors_max}층으로 계산했습니다.",
            )
            floors = floors_max
            # 잘린 층수로도 용적률을 다 쓸 수 있으면 결정 조건은 여전히 용적률이다
            binding = cap_reason if floors_max < floors_needed else "용적률"
    else:
        floors = floors_needed
        binding = "용적률"
        if floors_max is not None and floors_max < floors:
            floors = floors_max
            # 잘린 층수로도 용적률을 다 쓸 수 있으면 결정 조건은 여전히 용적률이다
            binding = cap_reason if floors_max < floors_needed else "용적률"

    gfa = min(max_gfa, max_ba * floors)
    building_area = gfa / floors
    height = floors * fh

    ledger.record(
        "floors",
        "계획 층수",
        floors,
        "층",
        "min(목표 층수, 높이·층수 제한)" if inp.target_floors else "min(용적률 소진 층수, 높이·층수 제한)",
        {
            **({"목표 층수": inp.target_floors} if inp.target_floors else {"용적률 소진 층수": floors_needed}),
            **{f"{n} 제한": c for c, n in caps},
        },
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
    if binding == "목표 층수":
        ledger.warn(
            "FAR_NOT_EXHAUSTED",
            f"목표 {floors}층으로는 허용 용적률의 {utilization:.1f}%만 사용합니다. "
            f"용적률을 모두 쓰려면 {floors_needed}층 이상이 필요합니다.",
            "info",
        )
    elif binding != "용적률":
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
        bcr_used_pct=_r(building_area / inp.site_area_m2 * 100, 1),
        floors_min_full_far=floors_needed,
        floors_max=floors_max,
        floors_max_reason=cap_reason,
        target_floors=inp.target_floors,
    )
