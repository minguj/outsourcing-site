"""초기 기획 타당성 검토 오케스트레이터.

대지 → 규모 → 에너지 소요량 → 설비 잠재량 → ZEB 등급별 시나리오 → 인사이트
순서로 계산하고, 결과 전체를 하나의 재현 가능한 스냅샷(calc_id)으로 묶는다.
이 모듈은 I/O 를 하지 않는다 (필지 조회는 adapters 계층의 책임).
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime

from .energy import build_options, build_scenarios, grade_for, max_potential
from .massing import MassingInput, compute_massing
from .rules import RuleBook
from .trace import INPUT, Ledger

ENGINE_VERSION = "0.1.0"


def format_krw(v: float) -> str:
    if v >= 1e8:
        return f"{v / 1e8:,.1f}억 원"
    return f"{round(v / 1e4):,}만 원"


@dataclass(frozen=True)
class SiteInput:
    site_area_m2: float
    zone: str
    jurisdiction: str | None = None
    address: str | None = None
    pnu: str | None = None
    land_use_plans: tuple[str, ...] = ()  # 필지에 포함되는 지역·지구
    partial_plans: tuple[str, ...] = ()  # 일부만 걸치는(저촉) 지역·지구
    adjacent_plans: tuple[str, ...] = ()  # 경계에 접하는 지역·지구 (규제 판단에 쓰지 않음, 표시만)
    land_category: str | None = None  # 지목
    secondary_zone: str | None = None  # 토지특성 용도지역2
    data_source: str = "manual"


@dataclass(frozen=True)
class PlanOptions:
    building_use: str = "공동주택"
    height_limit_m: float | None = None
    floor_height_m: float | None = None
    target_floors: int | None = None
    is_public: bool = False
    apply_zeb_incentive_grade: str | None = None  # 예: "3" → 3등급 취득 가정 시 용적률 완화 반영
    assumptions_override: dict = field(default_factory=dict)
    as_of: date | None = None


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _calc_id(payload: dict) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def run_feasibility(site: SiteInput, opts: PlanOptions, rules: RuleBook | None = None) -> dict:
    rules = rules or RuleBook(opts.as_of)
    ledger = Ledger()

    if opts.building_use not in rules.building_uses():
        raise ValueError(f"지원하지 않는 건축물 용도: {opts.building_use}")

    assumptions = _deep_merge(rules.assumptions, opts.assumptions_override or {})
    use_a = assumptions["building_uses"][opts.building_use]

    _site_checks(site, rules, ledger)

    # 인센티브 -----------------------------------------------------------
    incentive_rate = 0.0
    incentive_src = None
    if opts.apply_zeb_incentive_grade:
        inc, incentive_src = rules.incentive()
        incentive_rate = float(inc["rate_by_grade"][opts.apply_zeb_incentive_grade])
        ledger.record(
            "incentive_rate",
            f"ZEB {opts.apply_zeb_incentive_grade}등급 용적률 완화비율",
            incentive_rate,
            "%",
            "등급별 완화비율 표",
            {"가정 등급": opts.apply_zeb_incentive_grade},
            [incentive_src],
        )

    # 1) 규모 -------------------------------------------------------------
    massing = compute_massing(
        MassingInput(
            site_area_m2=site.site_area_m2,
            zone=site.zone,
            jurisdiction=site.jurisdiction,
            building_use=opts.building_use,
            height_limit_m=opts.height_limit_m,
            floor_height_m=opts.floor_height_m,
            far_incentive_rate=incentive_rate,
            incentive_source=incentive_src,
            target_floors=opts.target_floors,
        ),
        rules,
        ledger,
        floor_height_default=use_a["floor_height"]["value"],
    )

    # 2) 에너지 소요량 ------------------------------------------------------
    intensity = use_a["demand_intensity"]["value"]
    overridden = "demand_intensity" in (opts.assumptions_override.get("building_uses", {}).get(opts.building_use, {}))
    demand = massing.gfa_m2 * intensity
    ledger.record(
        "demand_intensity",
        "단위면적당 1차에너지 소요량",
        intensity,
        "kWh/㎡·yr",
        "입력값" if overridden else "용도별 가정값",
        sources=[
            INPUT
            if overridden
            else rules.assumption_source(
                f"building_uses.{opts.building_use}.demand_intensity", use_a["demand_intensity"].get("note")
            )
        ],
    )
    ledger.record(
        "demand",
        "연간 1차에너지 소요량",
        round(demand),
        "kWh/yr",
        "계획 연면적 × 단위면적당 소요량",
        {"계획 연면적": massing.gfa_m2, "단위 소요량": intensity},
    )

    # 3) 설비 잠재량 --------------------------------------------------------
    options = build_options(
        rules,
        ledger,
        building_area=massing.building_area_m2,
        site_area=site.site_area_m2,
        gfa=massing.gfa_m2,
        height=massing.height_m,
        assumptions=assumptions,
    )
    potential = max_potential(options, demand)
    ledger.record(
        "max_self_sufficiency",
        "설치 가능 최대 자립률",
        round(potential, 1),
        "%",
        "Σ(설비별 최대 설치량 × 단위 순생산량) ÷ 소요량",
    )

    # 4) ZEB 등급·의무 -----------------------------------------------------
    grades, grade_src = rules.zeb_grades()
    mandatory_grade, mandate_src = rules.mandate(opts.is_public, massing.gfa_m2)
    if mandatory_grade:
        ledger.record(
            "mandatory_grade",
            "ZEB 의무 등급",
            f"{mandatory_grade}등급 이상",
            "",
            "공공/민간 구분 × 연면적 기준",
            {"연면적": massing.gfa_m2, "공공 여부": "공공" if opts.is_public else "민간"},
            [mandate_src],
        )
    max_grade = grade_for(potential, grades)
    scenarios = build_scenarios(options, demand, massing.gfa_m2, grades, mandatory_grade)

    # 5) 인사이트 ----------------------------------------------------------
    insights = _insights(scenarios, options, mandatory_grade, max_grade, massing, opts)
    floor_comparison = _compare_with_min_floors(site, opts, rules, massing, scenarios, mandatory_grade)
    if floor_comparison:
        insights.insert(1, floor_comparison)
    if mandatory_grade:
        mand = next(s for s in scenarios if s.target_grade == mandatory_grade)
        if not mand.feasible:
            ledger.warn(
                "MANDATE_INFEASIBLE",
                f"현재 규모로는 의무 등급({mandatory_grade}등급)을 신재생 설비만으로 충족하기 어렵습니다. "
                "외피 성능 강화로 소요량을 줄이거나 대지 외 생산(보정계수 적용)을 검토해야 합니다.",
                "critical",
            )

    snapshot_inputs = {
        "site": site.__dict__,
        "options": {**opts.__dict__, "as_of": (opts.as_of or rules.as_of).isoformat()},
        "rules": rules.versions(),
        "engine": ENGINE_VERSION,
    }
    return {
        "calc_id": _calc_id(snapshot_inputs),
        "engine_version": ENGINE_VERSION,
        "computed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule_versions": rules.versions(),
        "height_plans": [
            name
            for name in (*site.land_use_plans, *site.partial_plans)
            if any(k in name for k in rules.height_plan_keywords())
        ],
        "site": {
            **site.__dict__,
            "land_use_plans": list(site.land_use_plans),
            "partial_plans": list(site.partial_plans),
            "adjacent_plans": list(site.adjacent_plans),
        },
        "options": {
            "building_use": opts.building_use,
            "height_limit_m": opts.height_limit_m,
            "floor_height_m": opts.floor_height_m,
            "target_floors": opts.target_floors,
            "is_public": opts.is_public,
            "apply_zeb_incentive_grade": opts.apply_zeb_incentive_grade,
        },
        "massing": massing.to_dict(),
        "energy": {
            "demand_intensity": intensity,
            "demand_kwh": round(demand),
            "max_self_sufficiency_pct": round(potential, 1),
            "max_grade": max_grade.grade if max_grade else None,
            "mandatory_grade": mandatory_grade,
            "options": [
                {
                    "key": o.key,
                    "name": o.name,
                    "unit": o.unit,
                    "max_units": o.max_units,
                    "production_per_unit": round(o.production_per_unit, 1),
                    "unit_cost_krw": o.unit_cost_krw,
                    "cost_per_kwh": round(o.cost_per_kwh, 1) if o.production_per_unit > 0 else None,
                    "limit_reason": o.limit_reason,
                }
                for o in options
            ],
        },
        "grade_source": grade_src.to_dict(),
        "scenarios": [s.to_dict() for s in scenarios],
        "insights": insights,
        "warnings": ledger.warnings,
        "trace": ledger.to_list(),
        "review_required": [s.key for s in ledger.steps() if s.needs_review],
    }


def _site_checks(site: SiteInput, rules: RuleBook, ledger: Ledger) -> None:
    """대지 자체의 전제 조건 점검. 계산은 계속하되, 결과를 확정값처럼 쓰면 안 되는 경우를 알린다."""
    # 1) 지목
    rule = rules.land_category_check(site.land_category)
    if rule:
        ledger.warn("LAND_CATEGORY", rule["message"].format(category=site.land_category), rule.get("severity", "warning"))

    # 2) 두 개 이상 용도지역에 걸친 필지 (포함·저촉만, 접함 제외)
    zones = {rules.canonical_zone(site.zone) or site.zone}
    for name in (site.secondary_zone, *site.land_use_plans, *site.partial_plans):
        z = rules.canonical_zone(name) if name else None
        if z:
            zones.add(z)
    if len(zones) > 1:
        ledger.warn(
            "MULTI_ZONE",
            f"대지가 둘 이상의 용도지역({', '.join(sorted(zones))})에 걸칩니다. 건폐율·용적률은 면적 비율에 따른 "
            f"별도 산정(국토계획법 제84조)이 필요하며, 이 계산은 대표 용도지역({site.zone}) 기준입니다.",
            "critical",
        )

    # 3) 개별 계획 우선 구역 / 높이 제한 지역 (포함 → 해당, 저촉 → 일부 해당, 접함 → 무시)
    for plan in rules.override_plans():
        severity = plan.get("severity", "critical")
        if any(plan["keyword"] in p for p in site.land_use_plans):
            ledger.warn("OVERRIDE_PLAN", plan["message"], severity)
        elif any(plan["keyword"] in p for p in site.partial_plans):
            ledger.warn("OVERRIDE_PLAN", f"(대지 일부가 걸침) {plan['message']}", severity)


def _compare_with_min_floors(site, opts, rules, massing, scenarios, mandatory_grade) -> str | None:
    """목표 층수를 정했을 때, 같은 대지를 가장 낮게(건폐율 최대) 지은 경우와 의무 등급 설비비를 비교한다."""
    # 더 높게(건축면적은 작게) 지을 때만 비교한다. 더 낮게 지으면 연면적이 줄어드는 것이라 비교 의미가 다르다.
    if not opts.target_floors or not mandatory_grade or massing.floors <= massing.floors_min_full_far:
        return None
    base = run_feasibility(site, replace(opts, target_floors=None), rules)
    if base["massing"]["floors"] >= massing.floors:
        return None
    here = next(s for s in scenarios if s.target_grade == mandatory_grade)
    there = next(s for s in base["scenarios"] if s["target_grade"] == mandatory_grade)
    lo = f"{base['massing']['floors']}층(건폐율 {base['massing']['bcr_used_pct']}%)"
    if not here.feasible:
        return f"{massing.floors}층으로는 의무 등급({here.target_label})을 맞추기 어렵습니다. {lo}으로 지으면 " + (
            f"{format_krw(there['total_cost_krw'])}으로 가능합니다." if there["feasible"] else "역시 어렵습니다."
        )
    if not there["feasible"] or there["total_cost_krw"] == 0:
        return None
    ratio = here.total_cost_krw / there["total_cost_krw"]
    return (
        f"{massing.floors}층(건폐율 {massing.bcr_used_pct}%)은 옥상이 좁아 의무 등급 설비비가 "
        f"{format_krw(here.total_cost_krw)}입니다. 같은 연면적을 {lo}으로 지으면 "
        f"{format_krw(there['total_cost_krw'])}이므로 {ratio:.1f}배입니다."
    )


def _insights(scenarios, options, mandatory_grade, max_grade, massing, opts) -> list[str]:
    out: list[str] = []
    feasible = [s for s in scenarios if s.feasible]
    if max_grade:
        out.append(f"이 대지·규모에서 신재생 설비로 도달 가능한 최고 등급은 ZEB {max_grade.label}입니다.")
    else:
        out.append("설치 가능한 신재생 설비만으로는 ZEB 5등급(자립률 20%)에도 도달하지 못합니다.")

    if mandatory_grade:
        m = next(s for s in scenarios if s.target_grade == mandatory_grade)
        if m.feasible:
            out.append(
                f"의무 등급({m.target_label}) 충족 설비비는 약 {format_krw(m.total_cost_krw)} "
                f"(연면적 ㎡당 {m.cost_per_gfa_krw:,.0f}원)입니다."
            )

    # 등급 간 비용 점프
    for a, b in zip(feasible, feasible[1:], strict=False):
        if a.total_cost_krw > 0 and b.total_cost_krw / a.total_cost_krw >= 2.5:
            new_keys = {p.key for p in b.picks} - {p.key for p in a.picks}
            names = ", ".join(o.name for o in options if o.key in new_keys)
            reason = f" — {names} 추가가 필요하기 때문" if names else ""
            out.append(
                f"{a.target_label} → {b.target_label}에서 비용이 {b.total_cost_krw / a.total_cost_krw:.1f}배로 뛰어요{reason}."
            )
            break

    roof = next((o for o in options if o.key == "pv_roof"), None)
    if roof and scenarios:
        first = scenarios[0]
        roof_pick = next((p for p in first.picks if p.key == "pv_roof"), None)
        if roof_pick and roof_pick.utilization_pct >= 100 and len(first.picks) > 1:
            out.append(
                f"{massing.floors}층 규모에서는 옥상 태양광만으로 5등급을 채우지 못합니다. "
                "층수가 높을수록 지붕 대비 소요량이 커지는 구조적 한계입니다."
            )
    if opts.apply_zeb_incentive_grade:
        out.append(
            f"ZEB {opts.apply_zeb_incentive_grade}등급 인센티브를 반영해 용적률 {massing.far_effective_pct}%로 계산했습니다. "
            "인센티브를 받으려면 해당 등급 시나리오의 설비비를 함께 부담해야 합니다."
        )
    return out
