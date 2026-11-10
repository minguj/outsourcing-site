"""초기 기획(대지 규모 + ZEB 시나리오) 데모 테스트.

- 골든: 손으로 계산한 결과와 엔진 결과를 대조한다. 손계산 과정은 docstring 에 남긴다.
  규칙 데이터나 가정값을 바꿔 깨지면, 손계산을 다시 해서 기대값을 고친다 (엔진 출력을 복사하지 않는다).
- 불변 조건: 시드를 고정한 무작위 입력으로 "어떤 입력에서도 깨지면 안 되는 조건"을 확인한다.
- 규칙 무결성: 조례값 ≤ 법정 상한, 출처 필드 존재 등.
- API / 브이월드 계약: 네트워크 없이 확인한다.
"""

import asyncio
import json
import os
import random
import subprocess
import unittest
from pathlib import Path
from unittest import mock

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.zeb import router as zeb_router_module
from backend.zeb.adapters.base import ProviderError
from backend.zeb.adapters.vworld import VWorldParcelProvider
from backend.zeb.domain.energy import build_options, grade_for
from backend.zeb.domain.feasibility import PlanOptions, SiteInput, run_feasibility
from backend.zeb.domain.rules import RuleBook
from backend.zeb.domain.trace import Ledger

RB = RuleBook()
SEOUL = "11440"
SEONGNAM = "41135"
MAPO = "1144012000101230004"
FIX = Path(__file__).parent / "fixtures" / "zeb"


def run(area, zone, juris=SEOUL, **opt):
    return run_feasibility(SiteInput(area, zone, juris), PlanOptions(**opt), RB)


def scenario(result, grade):
    return next(s for s in result["scenarios"] if s["target_grade"] == grade)


class GoldenMassingTests(unittest.TestCase):
    def test_g1_seoul_2nd_general_residential(self):
        """서울 제2종일반주거 1,000㎡, 공동주택
        건폐율 min(60, 60) = 60%  → 최대 건축면적 600㎡
        용적률 min(200, 250) = 200% → 최대 연면적 2,000㎡
        층수 = ceil(2000/600) = ceil(3.33) = 4층, 기준층 = 2000/4 = 500㎡, 높이 = 4 × 3.0 = 12m
        """
        m = run(1000, "제2종일반주거지역")["massing"]
        self.assertEqual((m["bcr_pct"], m["far_pct"]), (60, 200))
        self.assertEqual(m["max_building_area_m2"], 600)
        self.assertEqual(m["max_gfa_m2"], 2000)
        self.assertEqual(m["floors"], 4)
        self.assertEqual(m["building_area_m2"], 500)
        self.assertEqual(m["height_m"], 12)
        self.assertEqual(m["binding_constraint"], "용적률")

    def test_g2_semi_industrial_housing_uses_use_specific_far(self):
        """서울 준공업 3,500㎡, 공동주택 → 조례 용도별 기준 250% (일반 400% 아님)
        건축면적 3500×0.6 = 2,100㎡, 연면적 3500×2.5 = 8,750㎡
        층수 ceil(8750/2100) = ceil(4.17) = 5, 기준층 1,750㎡, 높이 15m
        """
        m = run(3500, "준공업지역", "11200")["massing"]
        self.assertEqual(m["far_pct"], 250)
        self.assertEqual(m["max_gfa_m2"], 8750)
        self.assertEqual(m["floors"], 5)
        self.assertEqual(m["building_area_m2"], 1750)
        self.assertEqual(m["height_m"], 15)

    def test_g3_semi_industrial_office_uses_general_far(self):
        """같은 준공업이라도 업무시설은 400%. 연면적 14,000㎡, ceil(14000/2100) = 7층, 층고 4.0 → 28m"""
        m = run(3500, "준공업지역", "11200", building_use="업무시설")["massing"]
        self.assertEqual(m["far_pct"], 400)
        self.assertEqual(m["max_gfa_m2"], 14000)
        self.assertEqual(m["floors"], 7)
        self.assertEqual(m["height_m"], 28)

    def test_g4_unregistered_ordinance_falls_back_with_critical_warning(self):
        """성남(경기)은 조례 미등록 → 법정 상한 60% / 250%. 연면적 1800×2.5 = 4,500㎡. 경고 필수."""
        r = run(1800, "제2종일반주거지역", SEONGNAM)
        self.assertEqual(r["massing"]["far_pct"], 250)
        self.assertEqual(r["massing"]["max_gfa_m2"], 4500)
        self.assertIn(("ORDINANCE_MISSING", "critical"), {(w["code"], w["severity"]) for w in r["warnings"]})

    def test_g5_height_limit_binds(self):
        """서울 2종일반 1,000㎡, 높이 제한 9m, 층고 3m → floor(9/3) = 3층
        연면적 = min(2000, 600×3) = 1,800㎡, 용적률 사용률 90%
        """
        r = run(1000, "제2종일반주거지역", height_limit_m=9)
        m = r["massing"]
        self.assertEqual(m["floors"], 3)
        self.assertEqual(m["gfa_m2"], 1800)
        self.assertEqual(m["binding_constraint"], "높이")
        self.assertEqual(m["far_utilization_pct"], 90.0)
        self.assertTrue(any(w["code"] == "FAR_NOT_EXHAUSTED" for w in r["warnings"]))

    def test_g6_seven_floor_zone_cap_is_recorded(self):
        """서울 2종일반(7층이하) 600㎡, 업무시설
        연면적 600×2.0 = 1,200㎡, 건축면적 360㎡ → 필요 층수 ceil(3.33) = 4층 ≤ 7층.
        제한은 작동하지 않지만, 근거 기록(floors_by_zone)에는 반드시 남아야 한다."""
        r = run(600, "제2종일반주거지역(7층이하)", "11110", building_use="업무시설")
        self.assertIn("floors_by_zone", {s["key"] for s in r["trace"]})
        self.assertEqual(r["massing"]["floors"], 4)

    def test_g7_general_commercial_office_tower(self):
        """서울 일반상업 2,400㎡ 업무: 60% / 800% → 건축면적 1,440, 연면적 19,200
        층수 ceil(19200/1440) = ceil(13.33) = 14, 기준층 1,371.43㎡, 높이 56m"""
        m = run(2400, "일반상업지역", "11680", building_use="업무시설")["massing"]
        self.assertEqual(m["max_gfa_m2"], 19200)
        self.assertEqual(m["floors"], 14)
        self.assertAlmostEqual(m["building_area_m2"], 1371.43, places=2)
        self.assertEqual(m["height_m"], 56)

    def test_g8_zeb_incentive_raises_far(self):
        """3등급 인센티브 13% → 200 × 1.13 = 226%, 연면적 2,260㎡, 층수 ceil(2260/600) = 4"""
        m = run(1000, "제2종일반주거지역", apply_zeb_incentive_grade="3")["massing"]
        self.assertEqual(m["far_effective_pct"], 226)
        self.assertEqual(m["gfa_m2"], 2260)
        self.assertEqual(m["floors"], 4)


class TargetFloorsTests(unittest.TestCase):
    """목표 층수: 같은 연면적을 높게(건축면적 작게) 또는 낮게(연면적 일부 포기) 짓는 경우."""

    AREA = 46640.6  # 가양동 대규모 아파트 단지 규모 (3종일반주거)

    def calc(self, **opt):
        return run_feasibility(SiteInput(self.AREA, "제3종일반주거지역", "11500", **opt.pop("site", {})), PlanOptions(**opt), RB)

    def test_taller_keeps_gfa_and_shrinks_footprint(self):
        """최대 연면적 = 46,640.6 × 2.5 = 116,601.5㎡, 최대 건축면적 = × 0.5 = 23,320.3㎡
        최소 층수 = ceil(116,601.5 / 23,320.3) = 5층
        13층: 건축면적 = 116,601.5 / 13 = 8,969.35㎡, 건폐율 사용 19.2%
        옥상 태양광 최대 = floor(8,969.35 × 0.5 / 10) = 448 kWp (5층이면 floor(23,320.3 × 0.5 / 10) = 1,166)
        """
        r = self.calc(target_floors=13)
        m = r["massing"]
        self.assertEqual((m["floors"], m["gfa_m2"], m["building_area_m2"]), (13, 116601.5, 8969.35))
        self.assertEqual((m["bcr_used_pct"], m["floors_min_full_far"], m["binding_constraint"]), (19.2, 5, "용적률"))
        roof = next(o for o in r["energy"]["options"] if o["key"] == "pv_roof")
        self.assertEqual(roof["max_units"], 448)
        base_roof = next(o for o in self.calc()["energy"]["options"] if o["key"] == "pv_roof")
        self.assertEqual(base_roof["max_units"], 1166)

    def test_taller_building_costs_more_for_same_grade_and_says_so(self):
        low = scenario(self.calc(), "5")["total_cost_krw"]
        high = self.calc(target_floors=13)
        self.assertGreater(scenario(high, "5")["total_cost_krw"], low)
        self.assertTrue(any("옥상이 좁아" in t and "5층" in t for t in high["insights"]))

    def test_lower_than_minimum_gives_up_floor_area(self):
        """3층: 연면적 = 23,320.3 × 3 = 69,960.9㎡ → 용적률 60% 사용, 목표 층수가 결정 조건"""
        r = self.calc(target_floors=3)
        m = r["massing"]
        self.assertEqual((m["gfa_m2"], m["binding_constraint"], m["far_utilization_pct"]), (69960.9, "목표 층수", 60.0))
        self.assertIn("FAR_NOT_EXHAUSTED", {w["code"] for w in r["warnings"]})
        self.assertFalse(any("옥상이 좁아" in t for t in r["insights"]))

    def test_target_is_capped_by_height_limit(self):
        """높이 제한 30m ÷ 층고 3m = 10층. 목표 13층 → 10층으로 계산하고 경고."""
        r = self.calc(target_floors=13, height_limit_m=30)
        m = r["massing"]
        self.assertEqual((m["floors"], m["floors_max"], m["floors_max_reason"]), (10, 10, "높이"))
        codes = {w["code"] for w in r["warnings"]}
        self.assertIn("TARGET_FLOORS_CAPPED", codes)
        # 10층 ≥ 최소 5층이므로 용적률은 다 쓴다 → '용적률 미사용' 경고가 나오면 안 된다 (화면에서 발견한 버그)
        self.assertEqual((m["far_utilization_pct"], m["binding_constraint"]), (100.0, "용적률"))
        self.assertNotIn("FAR_NOT_EXHAUSTED", codes)

    def test_target_is_capped_by_zone_floor_limit(self):
        r = run_feasibility(
            SiteInput(600, "제2종일반주거지역(7층이하)", "11110"), PlanOptions(target_floors=12), RB
        )
        self.assertEqual((r["massing"]["floors"], r["massing"]["floors_max_reason"]), (7, "층수"))

    def test_height_related_plans_are_listed_but_adjacent_ones_are_not(self):
        r = self.calc(site={"land_use_plans": ("최고고도지구",), "adjacent_plans": ("가로구역별 최고높이 제한지역",)})
        self.assertEqual(r["height_plans"], ["최고고도지구"])
        self.assertTrue(any("고도지구" in w["message"] for w in r["warnings"]))

    def test_random_targets_respect_all_limits(self):
        rnd = random.Random(7)
        for _ in range(200):
            area = round(rnd.uniform(200, 30_000), 1)
            zone = rnd.choice(RB.zone_names())
            h = rnd.choice([None, round(rnd.uniform(9, 120), 1)])
            t = rnd.randint(1, 60)
            with self.subTest(area=area, zone=zone, h=h, t=t):
                m = run_feasibility(SiteInput(area, zone, "11440"), PlanOptions(target_floors=t, height_limit_m=h), RB)["massing"]
                self.assertLessEqual(m["building_area_m2"], m["max_building_area_m2"] + 0.01)
                self.assertLessEqual(m["gfa_m2"], m["max_gfa_m2"] + 0.01)
                if m["floors_max"] is not None:
                    self.assertLessEqual(m["floors"], m["floors_max"])
                if m["far_utilization_pct"] < 99.95:
                    self.assertNotEqual(m["binding_constraint"], "용적률")
                else:
                    self.assertEqual(m["binding_constraint"], "용적률")
                if t >= m["floors_min_full_far"] and (m["floors_max"] is None or t <= m["floors_max"]):
                    self.assertEqual(m["floors"], t)
                    self.assertAlmostEqual(m["gfa_m2"], m["max_gfa_m2"], places=1)


class RegionalVariableTests(unittest.TestCase):
    """지역마다 달라지는 값: 조례, 구역(서울도심), 태양광 발전량."""

    def test_solar_yield_differs_by_region(self):
        """서울 1,165 / 제주 1,197 / 전남 1,434 / 그 외(예: 경기) 전국 평균 1,312 kWh/kWp·yr"""
        cases = {"11440": 1165, "50110": 1197, "46110": 1434, "41135": 1312}
        for juris, expected in cases.items():
            with self.subTest(juris=juris):
                e = run(1000, "제2종일반주거지역", juris)["energy"]
                self.assertEqual(e["solar_yield"]["value"], expected)

    def test_sunnier_region_needs_less_pv_for_same_grade(self):
        """전남은 조례 미등록이라 용적률(250%)이 서울(200%)과 달라 연면적이 다르다 → ㎡당 비용으로 비교.
        서울: 12 kWp × 180만 ÷ 2,000㎡ = 10,800원/㎡
        전남: 필요 2,500 × 90 × 20% = 45,000 → ceil(45,000 / (1,434 × 2.75)) = ceil(11.41) = 12 kWp → ÷ 2,500㎡ = 8,640원/㎡"""
        seoul = scenario(run(1000, "제2종일반주거지역", "11440"), "5")
        jeonnam = scenario(run(1000, "제2종일반주거지역", "46110"), "5")
        self.assertEqual((seoul["cost_per_gfa_krw"], jeonnam["cost_per_gfa_krw"]), (10_800, 8_640))

    def test_seoul_downtown_commercial_warns(self):
        """종로구·중구 상업지역: 서울도심이면 일반상업 600% (일반 800%). 경계가 구 단위가 아니므로 경고만."""
        r = run(2000, "일반상업지역", "11110", building_use="업무시설")
        self.assertEqual(r["massing"]["far_pct"], 800)
        w = next(w for w in r["warnings"] if w["code"] == "SUBAREA")
        self.assertIn("600%", w["message"])
        self.assertNotIn("SUBAREA", {w["code"] for w in run(2000, "일반상업지역", "11680", building_use="업무시설")["warnings"]})

    def test_first_class_general_residential_is_capped_at_4_floors(self):
        """1종일반주거 4층 이하. 1,000㎡: 연면적 1,500, 건축면적 600 → 필요 3층(제한 미작동), 목표 6층 → 4층"""
        r = run(1000, "제1종일반주거지역", target_floors=6)
        self.assertEqual((r["massing"]["floors"], r["massing"]["floors_max"]), (4, 4))

    def test_better_energy_performance_lowers_demand(self):
        """1+++ 주거 상한 60 → 2,000㎡ × 60 = 120,000 kWh"""
        r = run(1000, "제2종일반주거지역", performance="1+++")
        self.assertEqual(r["energy"]["demand_kwh"], 120_000)
        self.assertLess(scenario(r, "5")["total_cost_krw"], scenario(run(1000, "제2종일반주거지역"), "5")["total_cost_krw"])


class RealCaseValidationTests(unittest.TestCase):
    def test_yeouido_post_office_roof_only_self_sufficiency(self):
        """실제 사례: 여의도 우체국 — 건폐율 51.6%, 용적률 963.4%, 33층, 1차에너지 118.5 kWh/㎡·yr(1++),
        태양광 설치 가용면적 부족으로 에너지자립률 6% → ZEB 인증 실패 (한국건축친환경설비학회지 보도).

        같은 조건을 이 모델의 옥상 태양광 가정에 넣으면
        자립률 = (건축면적 × 0.5 ÷ 10㎡ × 1,165 × 2.75) ÷ (연면적 × 118.5)
              = 0.05 × 3,203.75 ÷ (963.4/51.6 × 118.5) ≈ 7.2%
        → 실제 6% 와 같은 수준이어야 한다 (모델이 낙관적으로 2배 이상 벗어나면 실패).
        """
        site = 10_000.0
        ba, gfa = site * 0.516, site * 9.634
        opts = build_options(
            RB, Ledger(), building_area=ba, site_area=site, gfa=gfa, height=33 * 4.0,
            assumptions=RB.assumptions, jurisdiction="11560",
        )
        roof = next(o for o in opts if o.key == "pv_roof")
        pct = roof.max_units * roof.production_per_unit / (gfa * 118.5) * 100
        self.assertTrue(4 <= pct <= 10, pct)


class GoldenEnergyTests(unittest.TestCase):
    def test_e1_demand_and_unit_production(self):
        """G1 기준 (서울, 공동주택, 에너지효율 1++ 상한 가정)
        소요량 = 2,000㎡ × 90(주거용 1++ 상한) = 180,000 kWh/yr
        태양광 1kWp = 1,165(서울 발전량) × 2.75 = 3,203.75
        BIPV 1kWp = 923(고시) × 1,165/1,312(지역 보정) × 2.75 = 2,253.9
        지열 1공 = 10.5kW × 864(고시) × 1.1 = 9,979.2
        연료전지 1kW = 7,415×2.75 + 7,415×1.0×1.1 − (7,415/0.4)×1.1 = 20,391.25 + 8,156.5 − 20,391.25 = 8,156.5
        옥상 최대 = floor(500 × 0.5 / 10) = 25 kWp
        """
        e = run(1000, "제2종일반주거지역")["energy"]
        self.assertEqual(e["demand_kwh"], 180_000)
        self.assertEqual(e["solar_yield"], {"value": 1165.0, "label": "서울"})
        opts = {o["key"]: o for o in e["options"]}
        self.assertEqual(opts["pv_roof"]["production_per_unit"], 3203.8)  # 3,203.75 표시 반올림
        self.assertAlmostEqual(opts["pv_bipv"]["production_per_unit"], 2253.9, places=1)
        self.assertEqual(opts["geothermal"]["production_per_unit"], 9979.2)
        self.assertEqual(opts["fuel_cell"]["production_per_unit"], 8156.5)
        self.assertEqual(opts["pv_roof"]["max_units"], 25)

    def test_e2_grade5_scenario_roof_pv_only(self):
        """5등급: 필요 180,000 × 20% = 36,000 → ceil(36,000 / 3,203.75) = ceil(11.24) = 12 kWp
        생산 38,445 → 자립률 21.36% → 21.4%, 비용 12 × 180만 = 2,160만 원"""
        s5 = scenario(run(1000, "제2종일반주거지역"), "5")
        self.assertTrue(s5["feasible"] and s5["mandatory"])
        self.assertEqual([(p["key"], p["units"]) for p in s5["picks"]], [("pv_roof", 12)])
        self.assertEqual(s5["achieved_pct"], 21.4)
        self.assertEqual(s5["total_cost_krw"], 21_600_000)

    def test_e3_tall_office_cannot_meet_high_grades(self):
        """일반상업 14층 업무시설은 옥상이 작아 고등급이 불가능해야 한다 (도메인 직관 검증)."""
        r = run(2400, "일반상업지역", "11680", building_use="업무시설")
        self.assertFalse(scenario(r, "1")["feasible"])
        roof = next(p for p in scenario(r, "5")["picks"] if p["key"] == "pv_roof")
        self.assertEqual(roof["utilization_pct"], 100)

    def test_grade_boundaries(self):
        grades, _ = RB.zeb_grades()
        cases = [(19.99, None), (20, "5"), (39.9, "5"), (40, "4"), (60, "3"), (80, "2"), (99.99, "2"), (100, "1"), (120, "+")]
        for pct, expected in cases:
            with self.subTest(pct=pct):
                g = grade_for(pct, grades)
                self.assertEqual(g.grade if g else None, expected)


class InvariantTests(unittest.TestCase):
    """시드 고정 무작위 입력 300건. 실패하면 subTest 메시지의 입력으로 재현한다."""

    def cases(self, n=300):
        rnd = random.Random(20261109)
        zones, uses = RB.zone_names(), RB.building_uses()
        for _ in range(n):
            site = SiteInput(
                site_area_m2=round(rnd.uniform(100, 50_000), 2),
                zone=rnd.choice(zones),
                jurisdiction=rnd.choice(["11440", "41135", None]),
            )
            opts = PlanOptions(
                building_use=rnd.choice(uses),
                height_limit_m=rnd.choice([None, round(rnd.uniform(6, 200), 1)]),
                is_public=rnd.random() < 0.3,
            )
            yield site, opts

    def test_never_exceeds_legal_limits(self):
        for site, opts in self.cases():
            with self.subTest(site=site, opts=opts):
                m = run_feasibility(site, opts, RB)["massing"]
                a = site.site_area_m2
                self.assertLessEqual(m["gfa_m2"], a * m["far_effective_pct"] / 100 + 0.01)
                self.assertLessEqual(m["building_area_m2"], a * m["bcr_pct"] / 100 + 0.01)
                z = RB.resolve_zone(site.zone, site.jurisdiction, opts.building_use)
                self.assertLessEqual(m["far_pct"], z.national.far)
                self.assertLessEqual(m["bcr_pct"], z.national.bcr)
                self.assertGreaterEqual(m["floors"], 1)
                if opts.height_limit_m:
                    self.assertLessEqual(m["height_m"], max(opts.height_limit_m, m["floor_height_m"]) + 1e-6)

    def test_scenarios_are_consistent(self):
        for site, opts in self.cases(200):
            with self.subTest(site=site, opts=opts):
                r = run_feasibility(site, opts, RB)
                for s in r["scenarios"]:
                    if s["feasible"]:
                        self.assertGreaterEqual(s["achieved_pct"] + 0.05, s["required_pct"])
                    for p in s["picks"]:
                        self.assertGreater(p["units"], 0)
                        self.assertLessEqual(p["utilization_pct"], 100 + 1e-6)
                costs = [s["total_cost_krw"] for s in r["scenarios"] if s["feasible"]]
                self.assertEqual(costs, sorted(costs))
                max_pct = r["energy"]["max_self_sufficiency_pct"]
                for s in r["scenarios"]:
                    if s["required_pct"] < max_pct - 0.5:
                        self.assertTrue(s["feasible"], (s["target_grade"], max_pct))

    def test_same_input_same_calc_id(self):
        for site, opts in self.cases(30):
            a = run_feasibility(site, opts, RB)
            b = run_feasibility(site, opts, RB)
            self.assertEqual(a["calc_id"], b["calc_id"])
            self.assertEqual(a["scenarios"], b["scenarios"])


class PackagingTests(unittest.TestCase):
    """데모가 실행에 필요한 파일이 .gitignore 에 걸려 커밋·이미지에서 빠지지 않는지 확인한다.
    (backend/zeb/data 가 저장소의 data/ 규칙에 걸려 배포 smoke 가 실패한 적이 있다)"""

    def test_no_demo_file_is_git_ignored(self):
        root = Path(__file__).resolve().parents[2]
        files = [
            p.relative_to(root).as_posix()
            for base in (root / "backend" / "zeb", FIX)
            for p in base.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".recorded.json")
        ]
        try:
            r = subprocess.run(
                ["git", "check-ignore", "--no-index", "--stdin"], cwd=root, input="\n".join(files),
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git 을 실행할 수 없음")
        if r.returncode == 128:
            self.skipTest("git 저장소가 아님")
        self.assertEqual(r.stdout.strip(), "", f"gitignore 에 걸린 파일: {r.stdout}")


class RuleIntegrityTests(unittest.TestCase):
    def test_ordinance_values_never_exceed_national_caps(self):
        nat = RB.zoning["national"]
        for o in RB.zoning["ordinances"]:
            for zone, v in o["zones"].items():
                cap = nat["zones"][nat.get("aliases", {}).get(zone, zone)]
                self.assertLessEqual(v["bcr"], cap["bcr"], (o["id"], zone))
                self.assertLessEqual(v["far"], cap["far"], (o["id"], zone))
            for zone, uses in o.get("use_overrides", {}).items():
                for use, v in uses.items():
                    self.assertLessEqual(v["far"], nat["zones"][zone]["far"], (o["id"], zone, use))
                    self.assertIn(use, RB.building_uses())

    def test_every_rule_has_provenance(self):
        self.assertTrue(RB.zoning["national"]["checked_on"])
        for o in RB.zoning["ordinances"]:
            self.assertTrue(o["title"] and o["ref"] and o["checked_on"])
        for g in RB.zeb["grade_sets"]:
            self.assertTrue(g["effective_from"] and g["checked_on"])
        for m in RB.zeb["mandates"]:
            self.assertTrue(m["effective_from"])
            self.assertIn("verified", m)

    def test_zeb_grades_strictly_ordered(self):
        grades, _ = RB.zeb_grades()
        mins = [g.min_self_sufficiency for g in grades]
        self.assertEqual(mins, sorted(mins, reverse=True))
        self.assertEqual(len(set(mins)), len(mins))

    def test_incentive_and_equipment_definitions(self):
        inc, _ = RB.incentive()
        self.assertTrue(all(0 < r <= inc["max_total_rate"] for r in inc["rate_by_grade"].values()))
        keys = [e["key"] for e in RB.equipment["equipment"]]
        self.assertEqual(len(keys), len(set(keys)))
        for e in RB.equipment["equipment"]:
            self.assertLessEqual({"key", "name", "unit", "unit_cost_krw", "output", "limit"}, set(e))
            self.assertGreater(e["unit_cost_krw"], 0)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(zeb_router_module.router)
        cls.env = mock.patch.dict(os.environ, {"VWORLD_API_KEY": ""})
        cls.env.start()
        cls.c = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()

    def test_main_app_mounts_router(self):
        from backend.main import app

        r = TestClient(app).get("/api/demo/zeb/meta")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("cache-control"), "no-store")  # main.py 의 /api/demo/ no-cache 미들웨어

    def test_meta_reports_sample_mode_without_key(self):
        meta = self.c.get("/api/demo/zeb/meta").json()
        self.assertEqual(meta["parcel_source"], "sample")
        self.assertIn("공동주택", meta["building_uses"])

    def test_search_and_get_sample_parcel(self):
        items = self.c.get("/api/demo/zeb/parcels/search", params={"q": "아현동", "source": "sample"}).json()["items"]
        self.assertEqual(items[0]["pnu"], MAPO)
        p = self.c.get(f"/api/demo/zeb/parcels/{MAPO}", params={"source": "sample"}).json()
        self.assertEqual((p["area_m2"], p["jurisdiction"]), (1000, "11440"))
        self.assertEqual(self.c.get("/api/demo/zeb/parcels/123").status_code, 422)

    def test_vworld_source_without_key_is_explicit_error(self):
        r = self.c.get("/api/demo/zeb/parcels/search", params={"q": "아현동", "source": "vworld"})
        self.assertEqual(r.status_code, 503)

    def test_feasibility_by_pnu_and_manual(self):
        r = self.c.post("/api/demo/zeb/feasibility", json={"pnu": MAPO, "source": "sample"}).json()
        self.assertEqual(r["massing"]["gfa_m2"], 2000)
        self.assertEqual(r["site"]["data_source"], "sample")
        self.assertEqual(len(r["scenarios"]), 6)
        ok = self.c.post("/api/demo/zeb/feasibility", json={"manual": {"site_area_m2": 500, "zone": "준주거지역", "jurisdiction": "11"}})
        self.assertEqual(ok.json()["massing"]["far_pct"], 400)

    def test_feasibility_validation(self):
        post = lambda body: self.c.post("/api/demo/zeb/feasibility", json=body).status_code  # noqa: E731
        self.assertEqual(post({"pnu": MAPO, "manual": {"site_area_m2": 1, "zone": "준주거지역"}}), 422)
        self.assertEqual(post({"manual": {"site_area_m2": 500, "zone": "없는지역"}}), 422)
        self.assertEqual(post({"manual": {"site_area_m2": 500, "zone": "준주거지역"}, "unknown": 1}), 422)
        self.assertEqual(post({"pnu": MAPO, "source": "sample", "target_floors": 0}), 422)
        self.assertEqual(post({"pnu": MAPO, "source": "sample", "target_floors": 201}), 422)

    def test_override_plan_warnings(self):
        nowon = self.c.post("/api/demo/zeb/feasibility", json={"pnu": "1135010500106450000", "source": "sample"}).json()
        self.assertTrue(any(w["code"] == "OVERRIDE_PLAN" and "정비구역" in w["message"] for w in nowon["warnings"]))
        jongno = self.c.post("/api/demo/zeb/feasibility", json={"pnu": "1111014800100880002", "source": "sample"}).json()
        self.assertTrue(any("지구단위계획" in w["message"] for w in jongno["warnings"]))

    def test_unverified_rule_is_flagged(self):
        """규칙 값이 verified: false 면 해당 계산 단계가 review_required 에 잡혀야 한다."""
        rb = RuleBook()
        rb.zoning["national"]["zones"]["제1종전용주거지역"]["verified"] = False
        rb.zoning["ordinances"][0]["zones"]["제1종전용주거지역"]["verified"] = False
        r = run_feasibility(SiteInput(800, "제1종전용주거지역", "11"), PlanOptions(), rb)
        self.assertIn("far", r["review_required"])
        self.assertNotIn("far", run(800, "제1종전용주거지역", "11")["review_required"])

    def test_redevelopment_search(self):
        items = self.c.get("/api/demo/zeb/redevelopment/search", params={"q": "상계"}).json()["items"]
        self.assertTrue(items and items[0]["representative_pnu"])


def _load_fixture(name, recorded=False):
    return json.loads((FIX / f"{name}{'.recorded' if recorded else ''}.json").read_text(encoding="utf-8"))


def _provider(handler):
    client = httpx.AsyncClient(base_url="https://api.vworld.kr", transport=httpx.MockTransport(handler))
    return VWorldParcelProvider("TEST", "https://fitagent.co.kr", client=client)


def _router(req, recorded=False):
    assert req.url.params["key"] == "TEST"
    assert req.url.params["domain"] == "https://fitagent.co.kr"
    if req.url.path == "/req/search":
        return httpx.Response(200, json=_load_fixture("vworld_search"))
    if req.url.path.endswith("getLandCharacteristics"):
        return httpx.Response(200, json=_load_fixture("vworld_land_characteristics", recorded))
    if req.url.path.endswith("getLandUseAttr"):
        return httpx.Response(200, json=_load_fixture("vworld_land_use_attr", recorded))
    return httpx.Response(404)


class VWorldContractTests(unittest.TestCase):
    def test_search_maps_pnu_and_point(self):
        hits = asyncio.run(_provider(_router).search("아현동 123-4"))
        self.assertEqual(hits[0].pnu, MAPO)
        self.assertAlmostEqual(hits[0].lat, 37.5551)

    def test_get_uses_latest_year_and_normalizes_zone(self):
        p = asyncio.run(_provider(_router).get(MAPO))
        self.assertEqual(p.area_m2, 1000)  # 2025년 행 (2024년 998.5 아님)
        self.assertEqual(p.zone, "제2종일반주거지역")  # 공백 제거
        self.assertEqual(p.data_source, "vworld")

    def test_land_use_relations_are_separated(self):
        """포함 → 규제 대상, 저촉 → 일부 걸침, 접함 → 인접 필지 것이므로 규제 판단에서 제외."""
        p = asyncio.run(_provider(_router).get(MAPO))
        self.assertEqual(p.land_use_plans, ["제2종일반주거지역", "지구단위계획구역"])
        self.assertEqual(p.partial_plans, ["절대보호구역"])
        self.assertEqual(p.adjacent_plans, ["정비구역", "제3종일반주거지역"])

    def test_error_status_raises_instead_of_falling_back(self):
        def bad(req):
            return httpx.Response(200, json={"response": {"status": "ERROR", "error": {"text": "INCORRECT_KEY"}}})

        with self.assertRaisesRegex(ProviderError, "INCORRECT_KEY"):
            asyncio.run(_provider(bad).search("아현동"))

    def test_http_failure_raises(self):
        with self.assertRaises(ProviderError):
            asyncio.run(_provider(lambda req: httpx.Response(503)).get(MAPO))

    def test_error_messages_never_contain_api_key(self):
        """오류 문구는 화면까지 전달된다. 인증키가 들어가면 공개 페이지에서 키가 노출된다 (실제로 발생했던 문제)."""

        def bad_status(req):
            return httpx.Response(502, request=req)

        def conn_error(req):
            raise httpx.ConnectError("boom " + str(req.url), request=req)

        def key_in_body(req):
            return httpx.Response(200, json={"response": {"status": "ERROR", "error": {"text": f"bad key {req.url}"}}})

        for handler in (bad_status, conn_error, key_in_body):
            with self.subTest(handler=handler.__name__):
                with self.assertRaises(ProviderError) as cm:
                    asyncio.run(_provider(handler).search("아현동"))
                self.assertNotIn("TEST", str(cm.exception))
                self.assertIsNone(cm.exception.__cause__)


@unittest.skipUnless((FIX / "vworld_land_characteristics.recorded.json").exists(), "실응답 녹화 없음")
class VWorldRecordedResponseTests(unittest.TestCase):
    """check_vworld 로 녹화한 실제 응답. 값이 아니라 해석 규칙을 확인한다."""

    def setUp(self):
        self.p = asyncio.run(_provider(lambda req: _router(req, recorded=True)).get("0" * 19))

    def test_parses_core_fields(self):
        self.assertGreater(self.p.area_m2, 0)
        self.assertIsNotNone(RB.canonical_zone(self.p.zone), self.p.zone)
        self.assertTrue(self.p.land_category)
        self.assertNotIn(" ", self.p.zone)

    def test_adjacent_plans_never_trigger_regulation_warnings(self):
        raw = _load_fixture("vworld_land_use_attr", recorded=True)["landUses"]["field"]
        only_adjacent = {r["prposAreaDstrcCodeNm"] for r in raw if r["cnflcAtNm"] == "접함"} - {
            r["prposAreaDstrcCodeNm"] for r in raw if r["cnflcAtNm"] != "접함"
        }
        self.assertFalse(only_adjacent & set(self.p.land_use_plans + self.p.partial_plans))
        site = SiteInput(
            self.p.area_m2, self.p.zone, self.p.jurisdiction, land_use_plans=tuple(self.p.land_use_plans),
            partial_plans=tuple(self.p.partial_plans), adjacent_plans=tuple(self.p.adjacent_plans),
            land_category=self.p.land_category, secondary_zone=self.p.secondary_zone,
        )
        messages = " ".join(w["message"] for w in run_feasibility(site, PlanOptions(), RB)["warnings"])
        for name in only_adjacent:
            for plan in RB.override_plans():
                if plan["keyword"] in name:
                    self.assertNotIn(plan["message"], messages, name)


class BrowserModeTests(unittest.TestCase):
    """브이월드가 해외·클라우드 IP(운영 서버: 시드니)를 차단해, 브라우저가 조회하고 원본을 서버로 보내는 방식."""

    def setUp(self):
        app = FastAPI()
        app.include_router(zeb_router_module.router)
        self.c = TestClient(app)
        self.env = mock.patch.dict(os.environ, {"VWORLD_API_KEY": "KEY-123", "VWORLD_MODE": "", "VWORLD_DOMAIN": "https://fitagent.co.kr"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def raw(self, recorded=False, pnu=MAPO):
        return {
            "pnu": pnu,
            "land_characteristics": _load_fixture("vworld_land_characteristics", recorded),
            "land_use_attr": _load_fixture("vworld_land_use_attr", recorded),
        }

    def post(self, body):
        return self.c.post("/api/demo/zeb/feasibility", json=body)

    def test_meta_hands_domain_bound_key_to_browser_by_default(self):
        meta = self.c.get("/api/demo/zeb/meta").json()
        self.assertEqual((meta["vworld_mode"], meta["vworld_key"]), ("browser", "KEY-123"))
        self.assertEqual(meta["vworld_domain"], "https://fitagent.co.kr")

    def test_server_mode_never_exposes_key(self):
        with mock.patch.dict(os.environ, {"VWORLD_MODE": "server"}):
            meta = self.c.get("/api/demo/zeb/meta").json()
        self.assertEqual(meta["vworld_mode"], "server")
        self.assertIsNone(meta["vworld_key"])

    def test_no_key_means_sample_only(self):
        with mock.patch.dict(os.environ, {"VWORLD_API_KEY": ""}):
            meta = self.c.get("/api/demo/zeb/meta").json()
        self.assertEqual(meta["parcel_source"], "sample")
        self.assertIsNone(meta["vworld_key"])

    def test_server_lookup_is_refused_in_browser_mode(self):
        r = self.c.get("/api/demo/zeb/parcels/search", params={"q": "아현동", "source": "vworld"})
        self.assertEqual(r.status_code, 409)

    def test_feasibility_from_browser_raw_uses_same_parser(self):
        r = self.post({"vworld_raw": self.raw()})
        self.assertEqual(r.status_code, 200, r.text)
        site = r.json()["site"]
        self.assertEqual((site["site_area_m2"], site["data_source"]), (1000, "vworld"))
        self.assertEqual(site["adjacent_plans"], ["정비구역", "제3종일반주거지역"])

    @unittest.skipUnless((FIX / "vworld_land_characteristics.recorded.json").exists(), "실응답 녹화 없음")
    def test_recorded_real_response_through_api(self):
        lc = _load_fixture("vworld_land_characteristics", True)["landCharacteristicss"]["field"][0]
        r = self.post({"vworld_raw": self.raw(recorded=True, pnu=lc["pnu"])})
        self.assertEqual(r.status_code, 200, r.text)
        codes = {w["code"] for w in r.json()["warnings"]}
        if lc.get("lndcgrCodeNm") == "도로":
            self.assertIn("LAND_CATEGORY", codes)

    def test_raw_validation(self):
        self.assertEqual(self.post({"vworld_raw": self.raw(), "pnu": MAPO}).status_code, 422)
        self.assertEqual(self.post({"vworld_raw": {**self.raw(), "pnu": "123"}}).status_code, 422)
        empty = {**self.raw(), "land_characteristics": {"landCharacteristicss": {"field": []}}}
        self.assertEqual(self.post({"vworld_raw": empty}).status_code, 422)
        huge = {**self.raw(), "land_use_attr": {"x": "가" * 300_001}}
        self.assertEqual(self.post({"vworld_raw": huge}).status_code, 422)


class SiteCheckTests(unittest.TestCase):
    def warnings(self, **site_kw):
        site = SiteInput(1000, "제3종일반주거지역", SEOUL, **site_kw)
        return {w["code"]: w for w in run_feasibility(site, PlanOptions(), RB)["warnings"]}

    def test_road_land_category_is_critical(self):
        w = self.warnings(land_category="도로")
        self.assertEqual(w["LAND_CATEGORY"]["severity"], "critical")
        self.assertIn("도로", w["LAND_CATEGORY"]["message"])

    def test_farmland_needs_conversion(self):
        self.assertEqual(self.warnings(land_category="답")["LAND_CATEGORY"]["severity"], "warning")
        self.assertNotIn("LAND_CATEGORY", self.warnings(land_category="대"))

    def test_multi_zone_from_secondary_zone_or_partial_plan(self):
        self.assertIn("MULTI_ZONE", self.warnings(secondary_zone="제2종일반주거지역"))
        self.assertIn("MULTI_ZONE", self.warnings(partial_plans=("제2종 일반주거지역",)))
        self.assertNotIn("MULTI_ZONE", self.warnings(adjacent_plans=("제2종일반주거지역",)))
        self.assertNotIn("MULTI_ZONE", self.warnings(land_use_plans=("제3종일반주거지역",)))

    def test_adjacent_override_plan_is_ignored_but_included_one_warns(self):
        self.assertNotIn("OVERRIDE_PLAN", self.warnings(adjacent_plans=("지구단위계획구역",)))
        self.assertEqual(self.warnings(land_use_plans=("지구단위계획구역",))["OVERRIDE_PLAN"]["severity"], "critical")
        partial = self.warnings(partial_plans=("정비구역",))["OVERRIDE_PLAN"]["message"]
        self.assertIn("일부", partial)

    def test_street_height_limit_zone_is_warning(self):
        w = self.warnings(land_use_plans=("가로구역별 최고높이 제한지역",))
        self.assertEqual(w["OVERRIDE_PLAN"]["severity"], "warning")


if __name__ == "__main__":
    unittest.main()
