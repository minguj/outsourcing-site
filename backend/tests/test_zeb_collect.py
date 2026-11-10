"""전국 조례 일괄 수집(backend/zeb/ordinance/collect.py) 테스트.

법제처 API 는 등록 IP 에서만 응답하므로 가짜 응답으로 돈다. 조문 문구는 실제 서울 조례 응답의 형식을 따른다.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from backend.zeb.domain import rules as rules_module
from backend.zeb.domain.feasibility import PlanOptions, SiteInput, run_feasibility
from backend.zeb.domain.rules import RuleBook
from backend.zeb.ordinance import collect, watch
from backend.zeb.ordinance.lawapi import LawClient

RULES = Path(rules_module.__file__).resolve().parent.parent / "rules"
NATIONAL = yaml.safe_load((RULES / "zoning.yaml").read_text(encoding="utf-8"))["national"]["zones"]
ZONES = list(NATIONAL)


def body(serial: str, name: str, bcr: dict, far: dict, extra_far_text: str = "") -> dict:
    """서울 조례 실제 응답과 같은 구조의 본문. bcr/far 는 용도지역 → 값."""
    def items(d):
        return "".join(f"{i}. {z}: {v}퍼센트" for i, (z, v) in enumerate(d.items(), 1))

    n44, n48 = ["004400", "004400"], ["004800", "004800"]
    arts = [
        {"조문번호": n44, "조제목": "", "조내용": "제3절 건폐율 및 용적률", "조문여부": "N"},
        {"조문번호": n44, "조제목": "용도지역 안에서의 건폐율", "조내용": f"제44조(용도지역 안에서의 건폐율) 용도지역별 건폐율은 다음 각 호의 비율 이하로 한다.{items(bcr)}", "조문여부": "Y"},
        {"조문번호": n48, "조제목": "용도지역 안에서의 용적률", "조내용": f"제48조(용도지역 안에서의 용적률) 용도지역별 용적률은 다음 각 호의 비율 이하로 한다.{items(far)}{extra_far_text}", "조문여부": "Y"},
    ]
    return {"LawService": {"자치법규기본정보": {"자치법규일련번호": serial, "자치법규명": name}, "조문": {"조": arts}}}


def standard(scale: float = 0.8) -> tuple[dict, dict]:
    return ({z: int(v["bcr"] * scale) for z, v in NATIONAL.items()}, {z: int(v["far"] * scale) for z, v in NATIONAL.items()})


class FakeLaw:
    """이름별 검색 결과(지자체기관명 포함)와 MST 별 본문."""

    def __init__(self):
        self.rows: list[dict] = []
        self.bodies: dict[str, dict] = {}
        self.queries: list[str] = []

    def add(self, name: str, agency: str, serial: str, date: str, b: dict | None):
        self.rows.append({"자치법규명": name, "지자체기관명": agency, "자치법규ID": "9" + serial, "자치법규일련번호": serial, "공포일자": date, "시행일자": date})
        if b is not None:
            self.bodies[serial] = b

    def __call__(self, url: str) -> str:
        from urllib.parse import parse_qs, urlparse

        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        if "lawSearch.do" in url:
            self.queries.append(q["query"])
            hits = [r for r in self.rows if q["query"].replace(" ", "") in r["자치법규명"].replace(" ", "")]
            return json.dumps({"OrdinSearch": {"law": hits}}, ensure_ascii=False)
        return json.dumps(self.bodies[q["MST"]], ensure_ascii=False)


def auth(prefix, sido, sido_name, name, kind):
    return {"prefix": prefix, "sido": sido, "sido_name": sido_name, "name": name, "kind": kind}


SUWON = auth("4111", "41", "경기도", "수원시", "city")
YEONCHEON = auth("4180", "41", "경기도", "연천군", "county")
GOSEONG_GN = auth("4882", "48", "경상남도", "고성군", "county")
GOSEONG_GW = auth("5182", "51", "강원특별자치도", "고성군", "county")


class AuthorityTableTests(unittest.TestCase):
    def setUp(self):
        self.auth = yaml.safe_load((RULES / "authorities.yaml").read_text(encoding="utf-8"))["authorities"]

    def test_covers_metros_and_cities(self):
        self.assertGreaterEqual(len(self.auth), 150)
        by = {(a["sido"], a["name"]): a["prefix"] for a in self.auth}
        self.assertEqual(by[("41", "수원시")], "4111")  # 장안·권선·팔달·영통구
        self.assertEqual(by[("41", "화성시")], "4159")  # 나중에 생긴 구(4159x)도 잡힌다
        self.assertEqual((by[("43", "영동군")], by[("43", "증평군")]), ("43740", "43745"))  # 4자리가 겹쳐 5자리
        self.assertEqual(by[("50", "제주특별자치도")], "50")
        self.assertIn(("51", "고성군"), by)
        self.assertIn(("48", "고성군"), by)

    def test_no_prefix_shadows_another(self):
        prefixes = [a["prefix"] for a in self.auth]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for p in prefixes:
            self.assertEqual([q for q in prefixes if q != p and q.startswith(p)], [], p)


class CollectOneTests(unittest.TestCase):
    def test_city_values(self):
        api = FakeLaw()
        bcr, far = standard()
        api.add("수원시 도시계획 조례", "경기도 수원시", "101", "20250301", body("101", "수원시 도시계획 조례", bcr, far))
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertIsNone(r.error)
        self.assertEqual(r.counts, (16, 16))
        self.assertEqual(r.zones["일반상업지역"], {"bcr": 64, "far": 1040})
        self.assertEqual(r.version.promulgated_on, "2025-03-01")

    def test_county_uses_gun_planning_ordinance(self):
        api = FakeLaw()
        bcr, far = standard()
        api.add("연천군 군계획 조례", "경기도 연천군", "102", "20240101", body("102", "연천군 군계획 조례", bcr, far))
        r = collect.collect_one(YEONCHEON, LawClient("x", api), NATIONAL)
        self.assertEqual(r.version.name, "연천군 군계획 조례")
        self.assertEqual(api.queries[0], "연천군 군계획 조례")

    def test_same_county_name_in_two_provinces(self):
        api = FakeLaw()
        bcr, far = standard()
        api.add("고성군 군계획 조례", "강원특별자치도 고성군", "201", "20260101", body("201", "고성군 군계획 조례", bcr, {**far, "준주거지역": 300}))
        api.add("고성군 군계획 조례", "경상남도 고성군", "202", "20250101", body("202", "고성군 군계획 조례", bcr, {**far, "준주거지역": 350}))
        gw = collect.collect_one(GOSEONG_GW, LawClient("x", api), NATIONAL)
        gn = collect.collect_one(GOSEONG_GN, LawClient("x", api), NATIONAL)
        self.assertEqual((gw.version.serial, gw.zones["준주거지역"]["far"]), ("201", 300))
        self.assertEqual((gn.version.serial, gn.zones["준주거지역"]["far"]), ("202", 350))

    def test_old_province_name_still_matches(self):
        api = FakeLaw()
        bcr, far = standard()
        api.add("고성군 군계획 조례", "강원도 고성군", "203", "20200101", body("203", "고성군 군계획 조례", bcr, far))
        self.assertIsNone(collect.collect_one(GOSEONG_GW, LawClient("x", api), NATIONAL).error)

    def test_value_above_cap_is_left_out(self):
        api = FakeLaw()
        bcr, far = standard()
        api.add("수원시 도시계획 조례", "경기도 수원시", "103", "20250301",
                body("103", "수원시 도시계획 조례", {**bcr, "자연녹지지역": 30}, far))
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertNotIn("bcr", r.zones["자연녹지지역"])  # 30% > 법정 상한 20%
        self.assertEqual(r.counts, (15, 16))
        self.assertTrue(any("법정 상한" in i for i in r.issues))

    def test_exception_clause_values_do_not_replace_base_value(self):
        """실제 경기 수집에서 나온 형식: 제1항 기본값 뒤 ②항에 주상복합 주거비율별 값(부천), '다만' 뒤 완화값(이천)."""
        api = FakeLaw()
        bcr, far = standard()
        extra = ("② 상업지역에서 주상복합건축물의 용적률은 다음과 같다. 1. 일반상업지역: 600퍼센트 2. 일반상업지역: 650퍼센트"
                 " 다만, 취락지구 안의 제2종일반주거지역: 70퍼센트")
        api.add("수원시 도시계획 조례", "경기도 수원시", "106", "20250301", body("106", "수원시 도시계획 조례", bcr, far, extra))
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual(r.zones["일반상업지역"]["far"], 1040)
        self.assertIn("600·650", r.zones["일반상업지역"]["note"])
        self.assertEqual(r.counts, (16, 16))
        self.assertTrue(any("다른 값" in i for i in r.issues))

    def test_thousands_separator(self):
        """실제 경기 수집에서 상업지역 용적률이 대거 빠진 원인: '1,300퍼센트' 표기."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("107", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][2]
        art["조내용"] = art["조내용"].replace("중심상업지역: 1200퍼센트", "중심상업지역: 1,200퍼센트")
        api.add("수원시 도시계획 조례", "경기도 수원시", "107", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual(r.zones["중심상업지역"]["far"], 1200)

    def test_korean_thousand_with_digits(self):
        """법령식 표기 '1천300퍼센트'(= 1300). 쉼표 보강 뒤에도 상업지역이 빠진 지자체의 다음 원인 후보."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("109", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][2]
        art["조내용"] = art["조내용"].replace("중심상업지역: 1200퍼센트", "중심상업지역: 1천200퍼센트").replace("일반상업지역: 1040퍼센트", "일반상업지역: 1천40퍼센트")
        api.add("수원시 도시계획 조례", "경기도 수원시", "109", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual((r.zones["중심상업지역"]["far"], r.zones["일반상업지역"]["far"]), (1200, 1040))

    def test_not_found_zones_are_reported(self):
        api = FakeLaw()
        bcr, far = standard()
        far.pop("유통상업지역")
        api.add("수원시 도시계획 조례", "경기도 수원시", "108", "20250301", body("108", "수원시 도시계획 조례", bcr, far))
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        # 조문에 이름이 아예 없으면 지정 안 된 용도지역으로 보고 전체 추출로 센다 (안양·과천·시흥 등)
        self.assertEqual(r.absent["far"], ["유통상업지역"])
        self.assertTrue(r.complete)
        self.assertIn("용적률 조문에 없음(지정 안 된 듯): 유통상업지역", r.issues)
        self.assertIn("전체 추출 1곳", collect.report([r], []))

    def test_label_between_zone_and_number(self):
        """수원 형식: '제2종일반주거지역: 일반건축은 250퍼센트 이하(다만, 공동주택… 230퍼센트)'."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("111", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][2]
        art["조내용"] = art["조내용"].replace(
            "제2종일반주거지역: 200퍼센트", "제2종일반주거지역: 일반건축은 200퍼센트 이하(다만, 공동주택은 230퍼센트 이하)"
        ).replace("중심상업지역: 1200퍼센트", "중심상업지역: 일반건축물은 1,200퍼센트 이하")
        api.add("수원시 도시계획 조례", "경기도 수원시", "111", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual((r.zones["제2종일반주거지역"]["far"], r.zones["중심상업지역"]["far"]), (200, 1200))
        self.assertTrue(r.complete)

    def test_hundredths_format_from_gunpo(self):
        """군포 실제 문구: '제1종 전용주거지역 : 100분의 40 이하', '100분 의 280', '100분의 1,000', '자연녹지지 역'."""
        api = FakeLaw()
        bcr_text = ("제49조(용도지역안에서의 건폐율)① 영 제84조제1항에 따라 용도지역 안에서의 건폐율은 다음 각 호와 같다."
                    + "".join(f"{i}. {z[:-4]} {z[-4:]} : 100분의 {v} 이하" if "전용" in z or "일반주거" in z else f"{i}. {z} : 100분의 {v} 이하"
                              for i, (z, v) in enumerate(standard()[0].items(), 1))
                    + "② 제1항에도 불구하고 시장정비사업구역 주거지역에 위치한 시장의 건폐율은 65퍼센트 이하로 한다.")
        far = standard()[1]
        far_text = ("제53조(용도지역 안에서의 용적률)① 각 용도지역의 용적률은 다음 각 호와 같다. 다만, 지구단위계획구역에서는 강화 또는 완화할 수 있다."
                    + "".join(f"{i}. {z} : 100분 의 {v:,} 이하" for i, (z, v) in enumerate(far.items(), 1)).replace("자연녹지지역", "자연녹지지 역"))
        b = {"LawService": {"조문": {"조": [
            {"조문번호": ["004900"] * 2, "조제목": "용도지역안에서의 건폐율", "조내용": bcr_text, "조문여부": "Y"},
            {"조문번호": ["005300"] * 2, "조제목": "용도지역 안에서의 용적률", "조내용": far_text, "조문여부": "Y"}]}}}
        api.add("수원시 도시계획 조례", "경기도 수원시", "113", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertIsNone(r.error)
        self.assertTrue(r.complete, r.issues)
        self.assertEqual(r.zones["제1종전용주거지역"]["bcr"], 40)
        self.assertEqual(r.zones["중심상업지역"]["far"], 1200)
        self.assertEqual(r.zones["자연녹지지역"]["far"], 80)

    def test_item_number_not_glued_to_hundredths(self):
        """전주 실제 결과: '100분의 40 2. 제2종…' 이 공백 제거 뒤 '100분의402' 로 읽혀 402% 가 됐다."""
        api = FakeLaw()
        bcr, far = standard()
        # 단위 없이 '100분의 40' 다음에 바로 다음 호 번호 '2.' 가 오는 형식
        text = "제44조(용도지역 안에서의 건폐율) 용도지역별 건폐율은 다음 각 호와 같다." + "".join(
            f"{i}. {z} : 100분의 {v} " for i, (z, v) in enumerate(bcr.items(), 1))
        b = body("114", "수원시 도시계획 조례", bcr, far)
        b["LawService"]["조문"]["조"][1]["조내용"] = text
        api.add("수원시 도시계획 조례", "경기도 수원시", "114", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual((r.zones["제1종전용주거지역"]["bcr"], r.zones["제2종전용주거지역"]["bcr"]), (40, 40))
        self.assertTrue(r.complete, r.issues)

    def test_unit_typos(self):
        """옥천 '200센트', 아산 '70퍼센터' (실제 조문 오타)."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("115", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][2]
        art["조내용"] = art["조내용"].replace("제1종일반주거지역: 160퍼센트", "제1종일반주거지역: 160센트").replace("보전녹지지역: 64퍼센트", "보전녹지지역: 64퍼센터")
        api.add("수원시 도시계획 조례", "경기도 수원시", "115", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual((r.zones["제1종일반주거지역"]["far"], r.zones["보전녹지지역"]["far"]), (160, 64))

    def test_not_found_explains_agency_mismatch(self):
        """전남 전체·광주가 '찾지 못함'이었다. 같은 이름이 다른 기관명으로 있으면 그 이름을 보여 준다."""
        api = FakeLaw()
        bcr, far = standard()
        api.add("수원시 도시계획 조례", "새이름특별시 수원시", "116", "20250301", body("116", "수원시 도시계획 조례", bcr, far))
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertIn("다른 기관명으로 있음: 새이름특별시 수원시", r.error)

    def test_gwangju_jeonnam_integration_agency_names(self):
        """2026 광주·전남 통합: '전남광주통합특별시 목포시', '(구)광주광역시'."""
        api = FakeLaw()
        bcr, far = standard()
        api.add("목포시 도시계획 조례", "전남광주통합특별시 목포시", "118", "20260801", body("118", "목포시 도시계획 조례", bcr, far))
        api.add("광주광역시 도시계획 조례", "(구)광주광역시", "119", "20260101", body("119", "광주광역시 도시계획 조례", bcr, far))
        mokpo = collect.collect_one(auth("4611", "46", "전라남도", "목포시", "city"), LawClient("x", api), NATIONAL)
        gwangju = collect.collect_one(auth("29", "29", "광주광역시", "광주광역시", "metro"), LawClient("x", api), NATIONAL)
        self.assertIsNone(mokpo.error)
        self.assertIsNone(gwangju.error)
        self.assertTrue(any("통합 전 기관" in i for i in gwangju.issues))

    def test_county_name_variants_and_title_suffix(self):
        api = FakeLaw()
        bcr, far = standard()
        api.add("가평군 계획조례", "경기도 가평군", "120", "20250101", body("120", "가평군 계획조례", bcr, far))
        api.add("연천군 군계획 조례 [제명개정 2020. 10. 5.]", "경기도 연천군", "121", "20250101", body("121", "연천군 군계획 조례", bcr, far))
        gp = collect.collect_one(auth("4182", "41", "경기도", "가평군", "county"), LawClient("x", api), NATIONAL)
        yc = collect.collect_one(YEONCHEON, LawClient("x", api), NATIONAL)
        self.assertEqual((gp.error, gp.version.serial), (None, "120"))
        self.assertEqual((yc.error, yc.version.serial), (None, "121"))

    def test_appendix_table_is_reported_as_manual(self):
        """울산·창원: '건폐율은 별표 27과 같다'."""
        api = FakeLaw()
        api.add("수원시 도시계획 조례", "경기도 수원시", "122", "20250301", {"LawService": {"조문": {"조": [
            {"조문번호": "005800", "조제목": "용도지역에서의 건폐율", "조내용": "제58조(용도지역에서의 건폐율) 각 용도지역별 건축물의 건폐율은 별표 27과 같다.", "조문여부": "Y"}]}}})
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertIn("별표로 정함", r.error)
        self.assertIn("수동 입력", r.error)

    def test_over_cap_value_gets_diagnostic(self):
        api = FakeLaw()
        bcr, far = standard()
        api.add("수원시 도시계획 조례", "경기도 수원시", "123", "20250301", body("123", "수원시 도시계획 조례", {**bcr, "자연녹지지역": 30}, far))
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertTrue(any("자연녹지지역" in d and "30퍼센트" in d for d in r.diagnostics))

    def test_item_number_glued_before_unit_jeonju(self):
        """전주 실제 결과 형식: '제1종전용주거지역：402퍼센트.제2종전용주거지역：403퍼센트 … 근린상업지역：6010퍼센트'."""
        api = FakeLaw()
        bcr, far = standard()
        real = {z: int(v["bcr"]) for z, v in NATIONAL.items()}  # 실제 조례값처럼 10 단위
        text = "제44조(용도지역 안에서의 건폐율) 건폐율은 다음과 같다." + "".join(
            f"{z}：{v}{i + 1}퍼센트." for i, (z, v) in enumerate(real.items(), 1))
        b = body("124", "수원시 도시계획 조례", bcr, far)
        b["LawService"]["조문"]["조"][1]["조내용"] = text
        api.add("수원시 도시계획 조례", "경기도 수원시", "124", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual((r.zones["제1종전용주거지역"]["bcr"], r.zones["근린상업지역"]["bcr"]), (50, 70))
        self.assertTrue(r.complete, r.issues)
        self.assertTrue(any("호 번호로 보고 뗌" in i for i in r.issues))

    def test_strip_item_number_only_when_over_cap(self):
        self.assertEqual(collect._strip_item_number(402, 50), 40)
        self.assertEqual(collect._strip_item_number(6010, 70), 60)
        self.assertIsNone(collect._strip_item_number(45, 50))  # 상한 이하는 그대로
        self.assertIsNone(collect._strip_item_number(999, 50))  # 99·9 는 상한 초과 → 못 고침

    def test_kind_with_no_values_is_diagnosed(self):
        """여수 건폐율 0/16: 조문은 있는데 값을 하나도 못 읽으면 조문 앞부분을 보여 준다."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("125", "수원시 도시계획 조례", bcr, far)
        b["LawService"]["조문"]["조"][1]["조내용"] = "제44조(용도지역 안에서의 건폐율) 제1종전용주거지역 등 용도지역별 건폐율은 아래 표와 같이 한다."
        api.add("수원시 도시계획 조례", "경기도 수원시", "125", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertIn("건폐율 조문에서 값을 하나도 못 읽음", r.issues)
        self.assertTrue(any(d.startswith("건폐율 조문 앞부분") for d in r.diagnostics))

    def test_failure_lists_related_articles(self):
        api = FakeLaw()
        api.add("수원시 도시계획 조례", "경기도 수원시", "112", "20250301", {"LawService": {"조문": {"조": [
            {"조문번호": "005000", "조제목": "건폐율", "조내용": "제50조(건폐율) 영 제84조에 따른 건폐율은 별표 20과 같다.", "조문여부": "Y"}]}}})
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertIn("관련 조: 제50조(건폐율)", r.error)

    def test_failure_shows_article_head(self):
        api = FakeLaw()
        api.add("수원시 도시계획 조례", "경기도 수원시", "117", "20250301", {"LawService": {"조문": {"조": [
            {"조문번호": "004600", "조제목": "용도지역 안에서의 건폐율‧용적률", "조내용": "제46조(용도지역 안에서의 건폐율‧용적률) 용도지역 안에서의 건폐율 및 용적률은 별표 22와 같다.", "조문여부": "Y"}]}}})
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertIn("별표로 정함", r.error)

    def test_diagnostics_show_unreadable_wording(self):
        api = FakeLaw()
        bcr, far = standard()
        b = body("110", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][2]
        art["조내용"] = art["조내용"].replace("준주거지역: 400퍼센트", "준주거지역은 400퍼센트 이상 500퍼센트 이하")
        api.add("수원시 도시계획 조례", "경기도 수원시", "110", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertTrue(any("준주거지역은400퍼센트" in d for d in r.diagnostics))
        self.assertIn("못 찾은 용도지역 진단", collect.report([r], []))

    def test_issue_lists_titles_when_no_zoning_article(self):
        """여수: 건폐율 조 제목에 '용도지역'이 없어 0/16 인데 이유가 안 보이던 경우. 비슷한 제목을 보여 준다."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("118", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][1]
        art["조제목"] = "건폐율의 최대한도"
        art["조내용"] = art["조내용"].replace("(용도지역 안에서의 건폐율)", "(건폐율의 최대한도)")
        api.add("수원시 도시계획 조례", "경기도 수원시", "118", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual(r.counts, (0, 16))
        self.assertFalse(r.complete)
        self.assertTrue(any("제44조(건폐율의 최대한도)" in i for i in r.issues), r.issues)

    def test_zoning_title_with_split_words(self):
        """여수 제33조 '용도구역·지역·지구안에서의 건폐율' 도 용도지역 조로 읽는다. '용도지구'·'그 밖의' 조는 아니다."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("119", "수원시 도시계획 조례", bcr, far)
        arts = b["LawService"]["조문"]["조"]
        arts[1]["조제목"] = "용도구역·지역·지구안에서의 건폐율"
        arts.append({"조문번호": "004500", "조제목": "그 밖의 용도지구ㆍ구역 등의 건폐율",
                     "조내용": "제45조(그 밖의 용도지구ㆍ구역 등의 건폐율) 1. 준주거지역: 10퍼센트", "조문여부": "Y"})
        api.add("수원시 도시계획 조례", "경기도 수원시", "119", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual(r.counts, (16, 16))
        self.assertEqual(r.articles["bcr"], ["제44조(용도구역·지역·지구안에서의 건폐율)"])

    def test_zone_only_in_exception_sentence_counts_as_absent(self):
        """울릉: 근린상업지역이 목록엔 없고 '근린상업지역 중 방화지구의 건축물…'에만 나오면 지정 안 된 것으로 본다.
        다른 쪽(용적률)에 값이 있는 용도지역은 그대로 '못 찾음'으로 둔다 (태백 준주거 용적률)."""
        api = FakeLaw()
        bcr, far = standard()
        del bcr["근린상업지역"], far["근린상업지역"], far["준주거지역"]
        tail = "② 근린상업지역 중 방화지구의 건축물은 90퍼센트 이하. 준주거지역에 위치한 시장의 용적률은 500퍼센트 이하"
        b = body("120", "수원시 도시계획 조례", bcr, far, extra_far_text=tail)
        b["LawService"]["조문"]["조"][1]["조내용"] += tail
        api.add("수원시 도시계획 조례", "경기도 수원시", "120", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual(r.absent, {"bcr": ["근린상업지역"], "far": ["근린상업지역"]})
        self.assertFalse(r.complete)  # 준주거 용적률은 못 찾음
        self.assertTrue(any(d.startswith("용적률 준주거지역:") and "준주거지역에위치한시장" in d for d in r.diagnostics), r.diagnostics)

    def test_diagnose_shows_up_to_three_places(self):
        d = collect._diagnose("far", "준주거지역", "준주거지역에A준주거지역에B준주거지역에C준주거지역에D")
        self.assertEqual(d.count("`") // 2, 3)
        self.assertTrue(d.endswith("외 1곳"))

    def test_zone_name_typo_missing_last_char(self):
        """태백 제56조: '6. 준주거지 : 500 퍼센트 이하' ('역' 빠짐). 실제 조문 형식 그대로."""
        api = FakeLaw()
        bcr, far = standard()
        b = body("121", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][2]
        art["조내용"] = art["조내용"].replace(f"준주거지역: {far['준주거지역']}퍼센트", f"준주거지 : {far['준주거지역']} 퍼센트 이하")
        self.assertIn("준주거지 :", art["조내용"])
        api.add("수원시 도시계획 조례", "경기도 수원시", "121", "20250301", b)
        r = collect.collect_one(SUWON, LawClient("x", api), NATIONAL)
        self.assertEqual(r.counts, (16, 16))
        self.assertEqual(r.zones["준주거지역"]["far"], far["준주거지역"])

    def test_not_found_and_no_article(self):
        api = FakeLaw()
        self.assertIn("찾지 못함", collect.collect_one(SUWON, LawClient("x", api), NATIONAL).error)
        api.add("수원시 도시계획 조례", "경기도 수원시", "104", "20250301",
                {"LawService": {"조문": {"조": [{"조문번호": "000100", "조제목": "목적", "조내용": "제1조(목적) …", "조문여부": "Y"}]}}})
        self.assertIn("별표", collect.collect_one(SUWON, LawClient("x", api), NATIONAL).error)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        shutil.copy(RULES / "zoning.yaml", self.dir / "zoning.yaml")
        authorities = [auth("11", "11", "서울특별시", "서울특별시", "metro"), SUWON, YEONCHEON]
        (self.dir / "authorities.yaml").write_text(yaml.safe_dump({"authorities": authorities}, allow_unicode=True), encoding="utf-8")
        self.api = FakeLaw()
        bcr, far = standard()
        self.api.add("수원시 도시계획 조례", "경기도 수원시", "101", "20250301", body("101", "수원시 도시계획 조례", bcr, far))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_collect(self, only=None):
        return collect.run(self.dir, LawClient("x", self.api), "2026-11-10", only, sleep=lambda s: None)

    def test_writes_collected_file_and_skips_verified_jurisdictions(self):
        results, skipped, changed = self.run_collect()
        self.assertTrue(changed)
        self.assertEqual([a["name"] for a in skipped], ["서울특별시"])  # zoning.yaml 에 있음
        data = yaml.safe_load((self.dir / collect.COLLECTED_FILE).read_text(encoding="utf-8"))
        o = data["ordinances"][0]
        self.assertEqual((o["id"], o["jurisdiction"], o["collected"]), ("auto-4111", "4111", True))
        self.assertEqual(o["zones"]["제3종일반주거지역"], {"bcr": 40, "far": 240, "verified": False})
        self.assertEqual(o["watch"]["promulgated_on"], "2025-03-01")
        self.assertEqual(data["missing"][0]["name"], "경기도 연천군")
        md = collect.report(results, skipped)
        self.assertIn("전체 추출 1곳", md)
        self.assertIn("실패 1곳", md)

    def test_human_verified_value_survives_recollection(self):
        self.run_collect()
        path = self.dir / collect.COLLECTED_FILE
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("제3종일반주거지역: { bcr: 40, far: 240, verified: false }",
                                     "제3종일반주거지역: { bcr: 40, far: 240, verified: true }"), encoding="utf-8")
        _, _, changed = self.run_collect()
        self.assertFalse(changed)
        self.assertIn("제3종일반주거지역: { bcr: 40, far: 240, verified: true }", path.read_text(encoding="utf-8"))

    def test_partial_run_keeps_other_results(self):
        self.run_collect()
        bcr, far = standard(0.7)
        self.api.add("연천군 군계획 조례", "경기도 연천군", "102", "20240101", body("102", "연천군 군계획 조례", bcr, far))
        self.run_collect(only="4180")
        data = yaml.safe_load((self.dir / collect.COLLECTED_FILE).read_text(encoding="utf-8"))
        self.assertEqual([o["id"] for o in data["ordinances"]], ["auto-4111", "auto-4180"])
        self.assertEqual(data["missing"], [])

    def test_retry_reruns_only_failed_and_partial(self):
        """--only retry: 지난번에 실패했거나 일부만 뽑은 곳만 다시 받고, 나머지는 이전 결과를 둔다."""
        self.run_collect()  # 수원 전체 추출, 연천 실패
        bcr, far = standard(0.7)
        self.api.add("연천군 군계획 조례", "경기도 연천군", "102", "20240101", body("102", "연천군 군계획 조례", bcr, far))
        self.api.queries.clear()
        results, _, changed = self.run_collect(only="retry")
        self.assertTrue(changed)
        self.assertEqual([r.authority["name"] for r in results], ["연천군"])
        self.assertFalse(any("수원" in q for q in self.api.queries))
        data = yaml.safe_load((self.dir / collect.COLLECTED_FILE).read_text(encoding="utf-8"))
        self.assertEqual([(o["id"], o["complete"]) for o in data["ordinances"]], [("auto-4111", True), ("auto-4180", True)])
        self.assertEqual(data["missing"], [])
        # 다 채워졌으면 다음 retry 는 할 일이 없다
        results, _, changed = self.run_collect(only="retry")
        self.assertEqual((results, changed), ([], False))

    def test_retry_includes_partial_and_accepts_codes(self):
        bcr, far = standard()
        b = body("106", "수원시 도시계획 조례", bcr, far)
        art = b["LawService"]["조문"]["조"][2]
        art["조내용"] = art["조내용"].replace("준주거지역: 400퍼센트", "준주거지역은 400퍼센트 이상 500퍼센트 이하")
        self.api.add("수원시 도시계획 조례", "경기도 수원시", "106", "20250401", b)
        self.run_collect()
        data = yaml.safe_load((self.dir / collect.COLLECTED_FILE).read_text(encoding="utf-8"))
        self.assertFalse(data["ordinances"][0]["complete"])
        self.assertEqual(collect.retry_prefixes(data), {"4111", "4180"})
        picked = collect.selector("11, retry", data)
        self.assertEqual([p for p in ("11", "4111", "4180", "4113") if picked(p)], ["11", "4111", "4180"])

    def test_retry_on_legacy_file_without_complete_flag(self):
        """complete 가 없던 예전 파일: 두 값이 16개씩 다 있지 않은 곳만 다시 수집 대상."""
        full = {z: {"bcr": 10, "far": 10} for z in ZONES}
        half = {z: {"bcr": 10, "far": 10} for z in ZONES[:10]}
        prev = {"ordinances": [{"jurisdiction": "4111", "zones": full}, {"jurisdiction": "4113", "zones": half}],
                "missing": [{"prefix": "4180"}]}
        self.assertEqual(collect.retry_prefixes(prev), {"4113", "4180"})

    def test_retry_without_previous_file_is_an_error(self):
        with self.assertRaises(ValueError):
            self.run_collect(only="retry")

    def test_daily_watch_covers_collected_file(self):
        """일괄 수집분도 개정 감지 대상. 같은 이름 조례가 다른 도에 있어도 지자체기관명으로 구분한다."""
        self.run_collect()
        bcr, far = standard()
        self.api.add("수원시 도시계획 조례", "경기도 수원시", "105", "20261101", body("105", "수원시 도시계획 조례", bcr, {**far, "준주거지역": 380}))
        props, errors = watch.run(self.dir / collect.COLLECTED_FILE, LawClient("x", self.api), "2026-11-11", sleep=lambda s: None)
        self.assertEqual(errors, [])
        self.assertEqual([(r.zone, r.new) for r in props[0].changed], [("준주거지역", 380)])
        o = yaml.safe_load((self.dir / collect.COLLECTED_FILE).read_text(encoding="utf-8"))["ordinances"][0]
        self.assertEqual(o["zones"]["준주거지역"], {"bcr": 56, "far": 380, "verified": False})
        self.assertEqual(o["watch"]["promulgated_on"], "2026-11-01")


class RuleBookCollectedTests(unittest.TestCase):
    def rulebook(self, zones: dict, jurisdiction="4111", collected_seoul=False) -> RuleBook:
        rb = RuleBook()
        ords = [{"id": f"auto-{jurisdiction}", "jurisdiction": jurisdiction, "title": "수원시 도시계획 조례", "ref": "제44조, 제48조",
                 "checked_on": "2026-11-10", "collected": True, "zones": zones}]
        if collected_seoul:
            ords.append({"id": "auto-11", "jurisdiction": "11", "title": "서울특별시 도시계획 조례", "ref": "-", "checked_on": "2026-11-10",
                         "collected": True, "zones": {"제3종일반주거지역": {"bcr": 10, "far": 10, "verified": False}}})
        rb.collected = {"ordinances": ords}
        return rb

    def test_collected_values_are_used_but_flagged(self):
        rb = self.rulebook({"일반상업지역": {"bcr": 60, "far": 1000, "verified": False}})
        r = run_feasibility(SiteInput(337.2, "일반상업지역", "41111"), PlanOptions(), rb)
        self.assertEqual((r["massing"]["bcr_pct"], r["massing"]["far_pct"]), (60, 1000))
        codes = {w["code"] for w in r["warnings"]}
        self.assertIn("ORDINANCE_COLLECTED", codes)
        self.assertNotIn("ORDINANCE_MISSING", codes)
        self.assertTrue(r["review_required"])
        z = rb.resolve_zone("일반상업지역", "41111", "공동주택")
        self.assertEqual((z.ordinance.source.title, z.ordinance.source.verified, z.collected), ("수원시 도시계획 조례 (자동 수집)", False, True))

    def test_missing_half_falls_back_to_national(self):
        rb = self.rulebook({"일반상업지역": {"far": 1000, "verified": False}})
        z = rb.resolve_zone("일반상업지역", "41117", "공동주택")
        self.assertEqual((z.ordinance.bcr, z.ordinance.far), (80, 1000))
        self.assertIn("건폐율은 조문에서 찾지 못해 법정 상한", z.ordinance.source.note)

    def test_zone_not_collected_keeps_missing_warning(self):
        rb = self.rulebook({"일반상업지역": {"bcr": 60, "far": 1000, "verified": False}})
        r = run_feasibility(SiteInput(1000, "제3종일반주거지역", "41111"), PlanOptions(), rb)
        self.assertIn("ORDINANCE_MISSING", {w["code"] for w in r["warnings"]})

    def test_verified_manual_rule_wins_over_collected_for_same_jurisdiction(self):
        rb = self.rulebook({}, collected_seoul=True)
        z = rb.resolve_zone("제3종일반주거지역", "11440", "공동주택")
        self.assertEqual((z.ordinance.far, z.collected), (250, False))

    def test_collected_file_values_never_exceed_caps(self):
        path = RULES / collect.COLLECTED_FILE
        if not path.exists():
            self.skipTest("아직 일괄 수집 전")
        for o in yaml.safe_load(path.read_text(encoding="utf-8"))["ordinances"] or []:
            for zone, v in o["zones"].items():
                for k in ("bcr", "far"):
                    if k in v:
                        self.assertLessEqual(v[k], NATIONAL[zone][k], (o["id"], zone, k))


if __name__ == "__main__":
    unittest.main()
