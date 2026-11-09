"""에너지 소요량, 신재생 설비 잠재량, ZEB 등급별 설비 시나리오.

자립률(%) = 1차에너지 순생산량 / 1차에너지 소요량 × 100

설비 선택은 '단위 생산량당 비용'이 낮은 설비부터 물리적 한계(옥상·입면·공지·열수요)까지 채우는
탐욕 알고리즘이다. 설비별 비용이 용량에 선형이고 상한만 있는 문제(분할 배낭 문제)이므로
연속 해 기준 최적이며, 정수 단위로 올림하는 만큼만 오차가 생긴다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .rules import Grade, RuleBook
from .trace import Ledger


def _r(x: float, nd: int = 1) -> float:
    return round(x + 0.0, nd)


@dataclass(frozen=True)
class EquipmentOption:
    key: str
    name: str
    unit: str
    unit_cost_krw: float
    production_per_unit: float  # 1차에너지 kWh/yr
    max_units: int
    limit_reason: str

    @property
    def cost_per_kwh(self) -> float:
        return self.unit_cost_krw / self.production_per_unit if self.production_per_unit > 0 else math.inf


@dataclass
class EquipmentPick:
    key: str
    name: str
    unit: str
    units: int
    production_kwh: float
    cost_krw: float
    utilization_pct: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Scenario:
    target_grade: str
    target_label: str
    required_pct: float
    feasible: bool
    achieved_pct: float
    achieved_grade: str | None
    total_cost_krw: float
    cost_per_gfa_krw: float
    picks: list[EquipmentPick] = field(default_factory=list)
    shortfall_kwh: float = 0.0
    mandatory: bool = False
    note: str | None = None

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["picks"] = [p.to_dict() for p in self.picks]
        return d


def grade_for(pct: float, grades: list[Grade]) -> Grade | None:
    for g in grades:  # 높은 등급부터 정렬되어 있음
        if pct + 1e-9 >= g.min_self_sufficiency:
            return g
    return None


def build_options(
    rules: RuleBook,
    ledger: Ledger,
    *,
    building_area: float,
    site_area: float,
    gfa: float,
    height: float,
    assumptions: dict,
) -> list[EquipmentOption]:
    pef_e = assumptions["primary_energy_factor"]["electricity"]["value"]
    pef_f = assumptions["primary_energy_factor"]["fuel"]["value"]
    site = assumptions["site"]
    a_src = rules.assumption_source
    options: list[EquipmentOption] = []

    for eq in rules.equipment["equipment"]:
        key = eq["key"]
        eq_src = a_src(f"equipment.{key}", "설비 라이브러리 단가·성능 가정")

        if eq["output"] == "electricity":
            per_unit = eq["specific_yield"]["value"] * pef_e
            formula = "연간 발전량 × 전력 1차에너지 환산계수"
            inputs = {"연간 발전량(kWh/kWp)": eq["specific_yield"]["value"], "환산계수": pef_e}
        elif eq["output"] == "renewable_heat":
            cap = eq["capacity_per_unit"]["value"]
            hrs = eq["full_load_hours"]["value"]
            cop = eq["cop"]["value"]
            per_unit = cap * hrs * (1 - 1 / cop) * pef_f
            formula = "용량 × 전부하시간 × (1 − 1/COP) × 연료 환산계수"
            inputs = {"용량(kW)": cap, "전부하시간": hrs, "COP": cop, "환산계수": pef_f}
        elif eq["output"] == "chp":
            hrs = eq["operating_hours"]["value"]
            eff = eq["electric_efficiency"]["value"]
            hpr = eq["heat_to_power_ratio"]["value"]
            elec = hrs
            heat = hrs * hpr
            fuel_in = hrs / eff
            per_unit = elec * pef_e + heat * pef_f - fuel_in * pef_f
            formula = "발전량×전력계수 + 회수열×연료계수 − 투입연료×연료계수"
            inputs = {"운전시간": hrs, "발전효율": eff, "열전비": hpr, "전력계수": pef_e, "연료계수": pef_f}
        else:  # pragma: no cover - 설정 오류
            raise ValueError(f"unknown output type: {eq['output']}")

        # 물리적 설치 한계
        if eq["limit"] == "roof":
            area = building_area * site["roof_usable_ratio"]["value"]
            max_units = math.floor(area / eq["area_per_unit"]["value"])
            reason = f"옥상 설치 가능 면적 {area:,.0f}㎡"
        elif eq["limit"] == "facade":
            # 정방형 평면 가정: 남측 입면 폭 = √건축면적
            facade = math.sqrt(building_area) * height * site["south_facade_usable_ratio"]["value"]
            max_units = math.floor(facade / eq["area_per_unit"]["value"])
            reason = f"남측 입면 설치 가능 면적 {facade:,.0f}㎡"
        elif eq["limit"] == "open_space":
            open_area = max(0.0, site_area - building_area) * site["open_space_usable_ratio"]["value"]
            max_units = math.floor(open_area / eq["area_per_unit"]["value"])
            reason = f"천공 가능 공지 {open_area:,.0f}㎡"
        elif eq["limit"] == "gfa":
            max_units = math.floor(gfa * eq["max_kw_per_gfa"]["value"])
            reason = f"열수요 기준 상한 (연면적 × {eq['max_kw_per_gfa']['value']} kW/㎡)"
        else:  # pragma: no cover
            raise ValueError(eq["limit"])

        ledger.record(
            f"eq.{key}.per_unit",
            f"{eq['name']} 단위 순생산량",
            _r(per_unit),
            f"kWh/yr·{eq['unit']}",
            formula,
            inputs,
            [eq_src],
        )
        ledger.record(
            f"eq.{key}.max_units",
            f"{eq['name']} 설치 가능 최대량",
            max_units,
            eq["unit"],
            reason,
            sources=[eq_src],
        )
        options.append(EquipmentOption(key, eq["name"], eq["unit"], eq["unit_cost_krw"], per_unit, max_units, reason))
    return options


def plan_for_target(
    options: list[EquipmentOption], demand_kwh: float, target_pct: float
) -> tuple[list[EquipmentPick], float, float]:
    """목표 자립률을 최소 비용으로 맞추는 설비 조합. (picks, 생산량, 부족량)"""
    need = demand_kwh * target_pct / 100
    picks: list[EquipmentPick] = []
    produced = 0.0
    for opt in sorted(options, key=lambda o: o.cost_per_kwh):
        if produced >= need - 1e-6:
            break
        if opt.max_units <= 0 or opt.production_per_unit <= 0:
            continue
        units = min(opt.max_units, math.ceil((need - produced) / opt.production_per_unit - 1e-9))
        if units <= 0:
            continue
        prod = units * opt.production_per_unit
        produced += prod
        picks.append(
            EquipmentPick(
                key=opt.key,
                name=opt.name,
                unit=opt.unit,
                units=units,
                production_kwh=_r(prod),
                cost_krw=units * opt.unit_cost_krw,
                utilization_pct=_r(units / opt.max_units * 100),
            )
        )
    return picks, produced, max(0.0, need - produced)


def build_scenarios(
    options: list[EquipmentOption],
    demand_kwh: float,
    gfa: float,
    grades: list[Grade],
    mandatory_grade: str | None,
) -> list[Scenario]:
    scenarios: list[Scenario] = []
    # 낮은 등급부터 보여준다 (5 → +)
    for g in sorted(grades, key=lambda g: g.min_self_sufficiency):
        picks, produced, shortfall = plan_for_target(options, demand_kwh, g.min_self_sufficiency)
        achieved = produced / demand_kwh * 100 if demand_kwh else 0.0
        ag = grade_for(achieved, grades)
        feasible = shortfall <= 1e-6
        cost = sum(p.cost_krw for p in picks)
        note = None
        if not feasible:
            note = f"대지·건물 조건상 최대 {achieved:.1f}%까지 가능 (부족 {shortfall:,.0f} kWh/yr)"
        scenarios.append(
            Scenario(
                target_grade=g.grade,
                target_label=g.label,
                required_pct=g.min_self_sufficiency,
                feasible=feasible,
                achieved_pct=_r(achieved),
                achieved_grade=ag.grade if ag else None,
                total_cost_krw=cost,
                cost_per_gfa_krw=round(cost / gfa) if gfa else 0,
                picks=picks,
                shortfall_kwh=_r(shortfall),
                mandatory=(g.grade == mandatory_grade),
                note=note,
            )
        )
    return scenarios


def max_potential(options: list[EquipmentOption], demand_kwh: float) -> float:
    total = sum(o.max_units * max(0.0, o.production_per_unit) for o in options)
    return total / demand_kwh * 100 if demand_kwh else 0.0
