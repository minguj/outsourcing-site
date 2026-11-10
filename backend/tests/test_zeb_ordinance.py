"""조례 개정 감지(backend/zeb/ordinance) 테스트.

법제처 API 는 등록한 서버 IP 에서만 응답하므로 테스트는 fixture 응답으로 돈다.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from backend.zeb.domain import rules as rules_module
from backend.zeb.domain.feasibility import PlanOptions, SiteInput, run_feasibility
from backend.zeb.domain.rules import RuleBook
from backend.zeb.ordinance import watch
from backend.zeb.ordinance.extract import extract
from backend.zeb.ordinance.lawapi import Article, LawApiError, LawClient
from backend.zeb.ordinance.update import apply, compare, report

FIX = Path(__file__).resolve().parent / "fixtures" / "zeb"
RULES = Path(rules_module.__file__).resolve().parent.parent / "rules"
SEOUL = "서울특별시 도시계획 조례"
# 규칙 파일 사본. 실제 규칙이 조례 개정으로 바뀌어도 이 테스트는 고정된 기준으로 돈다.
SNAPSHOT = FIX / "zoning_snapshot.yaml"


def _fixture(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeApi:
    """lawSearch / lawService 요청에 fixture 를 돌려준다. body 를 바꿔 개정 상황을 만든다."""

    def __init__(self, body: dict | None = None, search: dict | None = None):
        self.body = body or _fixture("law_ordin_body.json")
        self.search = search or _fixture("law_ordin_search.json")
        self.urls: list[str] = []

    def __call__(self, url: str) -> str:
        self.urls.append(url)
        if "lawSearch.do" in url:
            return json.dumps(self.search, ensure_ascii=False)
        if "lawService.do" in url:
            return json.dumps(self.body, ensure_ascii=False)
        raise AssertionError(url)


def _body_with(old: str, new: str) -> dict:
    """조문 문구 일부를 바꾼 본문 (조례 개정 흉내)."""
    text = json.dumps(_fixture("law_ordin_body.json"), ensure_ascii=False)
    assert old in text, old
    return json.loads(text.replace(old, new))


def _seoul(data: dict) -> dict:
    return next(o for o in data["ordinances"] if o["id"] == "seoul-urban-planning-ordinance")


class LawApiTests(unittest.TestCase):
    def test_latest_picks_exact_name_not_similar_ordinances(self):
        v = LawClient("OC1", FakeApi()).latest(SEOUL, "6110000")
        self.assertEqual((v.serial, v.promulgated_on, v.effective_on), ("2149501", "2026-07-13", "2026-07-13"))

    def test_request_carries_oc_org_and_json(self):
        api = FakeApi()
        LawClient("OC1", api).latest(SEOUL, "6110000")
        self.assertIn("OC=OC1", api.urls[0])
        self.assertIn("target=ordin", api.urls[0])
        self.assertIn("org=6110000", api.urls[0])
        self.assertIn("type=JSON", api.urls[0])

    def test_unregistered_ip_error_is_explicit_and_hides_oc(self):
        """실제로 받은 거부 응답 형식: 서버 IP·도메인을 등록하지 않으면 이렇게 온다."""
        msg = {"result": "사용자 정보 검증에 실패하였습니다.", "msg": "OPEN API 호출 시 사용자 검증을 위하여 정확한 서버장비의 IP주소 및 도메인주소를 등록해 주세요. (OC1)"}
        with self.assertRaises(LawApiError) as cm:
            LawClient("OC1", lambda url: json.dumps(msg, ensure_ascii=False)).latest(SEOUL)
        self.assertIn("IP주소", str(cm.exception))
        self.assertNotIn("OC1", str(cm.exception))

    def test_network_error_does_not_leak_url(self):
        def boom(url):
            raise OSError(f"failed {url}")

        with self.assertRaises(LawApiError) as cm:
            LawClient("SECRET", boom).latest(SEOUL)
        self.assertNotIn("SECRET", str(cm.exception))

    def test_missing_oc_is_error(self):
        with self.assertRaises(LawApiError):
            LawClient("")

    def test_articles_skip_chapter_headings(self):
        api = FakeApi()
        c = LawClient("OC1", api)
        arts = c.articles(c.latest(SEOUL))
        # 실제 응답처럼 조문번호가 ["004400", "004400"] 목록으로 오고, '제3절' 같은 머리는 조문여부 N
        self.assertEqual([a.number for a in arts], ["44", "45", "46", "47", "48", "49", "50", "51"])
        self.assertEqual(arts[0].title, "용도지역 안에서의 건폐율")
        self.assertIn("MST=2149501", api.urls[-1])


class ExtractTests(unittest.TestCase):
    def setUp(self):
        c = LawClient("OC1", FakeApi())
        self.ext = extract(c.articles(c.latest(SEOUL)))

    def test_only_the_zoning_articles_are_read(self):
        """제목에 '용도지역'이 있는 조만 본다. '그 밖의', '강화', '완화' 조는 제외."""
        self.assertEqual(self.ext.articles["bcr"], ["제44조(용도지역 안에서의 건폐율)"])
        self.assertEqual(self.ext.articles["far"], ["제48조(용도지역 안에서의 용적률)"])
        self.assertEqual(len(self.ext.values["bcr"]), 16)
        self.assertEqual(len(self.ext.values["far"]), 16)

    def test_values(self):
        self.assertEqual(self.ext.values["far"]["제3종일반주거지역"], [250])
        self.assertEqual(self.ext.values["bcr"]["제2종전용주거지역"], [40])
        self.assertEqual(self.ext.values["far"]["중심상업지역"], [1000])  # '1천퍼센트'

    def test_school_site_values_in_other_article_are_not_mixed_in(self):
        """실제 제49조 학교이적지 값('제3종일반주거지역: 200퍼센트')이 기본값에 섞이면 안 된다."""
        self.assertEqual(self.ext.values["far"]["제3종일반주거지역"], [250])
        self.assertEqual(self.ext.values["far"]["준주거지역"], [400])

    def test_seoul_downtown_values_in_parentheses(self):
        self.assertEqual(
            self.ext.subareas["far"]["서울도심"],
            {"중심상업지역": 800, "일반상업지역": 600, "근린상업지역": 500, "유통상업지역": 500},
        )

    def test_without_zoning_article_nothing_is_extracted(self):
        e = extract([Article("49", "그 밖의 용적률", "바. 제3종일반주거지역: 200퍼센트")])
        self.assertEqual(e.values["far"], {})

    def test_spacing_variants(self):
        e = extract([Article("44", "용도지역 안에서의 건폐율", "1. 제3종 일반주거지역 : 50 퍼센트 2. 준주거지역: 60%")])
        self.assertEqual(e.values["bcr"], {"제3종일반주거지역": [50], "준주거지역": [60]})


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.text = SNAPSHOT.read_text(encoding="utf-8")
        self.data = yaml.safe_load(self.text)

    def proposal(self, api: FakeApi):
        c = LawClient("OC1", api)
        v = c.latest(SEOUL)
        return compare(_seoul(self.data), v, extract(c.articles(v)))

    def test_current_rules_match_ordinance_text(self):
        """기준선: 지금 규칙 파일 값이 조문과 모두 같다 (서울도심·공동주택 별도 기준 포함)."""
        p = self.proposal(FakeApi())
        self.assertEqual((p.changed, p.manual), ([], []))
        self.assertEqual(len(p.results), 32)

    def test_baseline_apply_only_records_version(self):
        p = self.proposal(FakeApi())
        out = apply(self.text, p, "2026-11-17")
        diff = [(a, b) for a, b in zip(self.text.splitlines(), out.splitlines()) if a != b]
        self.assertEqual(len(diff), 2, diff)
        self.assertIn('promulgated_on: "2026-07-13"', out)
        self.assertIn('checked_on: "2026-11-17"', out)
        self.assertIn('checked_on: "2026-11-10"', out)  # 국가 법령 확인일은 그대로

    def test_single_changed_value_is_proposed_as_unverified(self):
        p = self.proposal(FakeApi(_body_with("제3종일반주거지역: 250퍼센트", "제3종일반주거지역: 300퍼센트")))
        self.assertEqual([(r.zone, r.kind, r.new) for r in p.changed], [("제3종일반주거지역", "far", 300)])
        out = apply(self.text, p, "2026-11-17")
        # 다른 용도지역·주석은 그대로
        self.assertEqual(out.count("verified: false") - self.text.count("verified: false"), 1)
        self.assertIn("# 2024년 전부개정으로 조문 번호가 바뀌었다", out)
        new = _seoul(yaml.safe_load(out))
        self.assertEqual(new["zones"]["제3종일반주거지역"], {"bcr": 50, "far": 300, "verified": False})
        self.assertEqual(new["zones"]["제2종일반주거지역"]["far"], 200)

    def test_ambiguous_value_keeps_number_but_marks_unverified(self):
        p = self.proposal(FakeApi(_body_with("근린상업지역: 600퍼센트(단", "근린상업지역: 600퍼센트, 근린상업지역: 550퍼센트(단")))
        self.assertEqual([(r.zone, r.found) for r in p.manual], [("근린상업지역", [600, 550])])
        out = apply(self.text, p, "2026-11-17")
        z = _seoul(yaml.safe_load(out))["zones"]["근린상업지역"]
        self.assertEqual((z["far"], z["verified"]), (600, False))

    def test_missing_article_marks_zones_for_manual_check(self):
        """용적률 조(제48조)가 사라지면(조 제목 변경 등) 다른 조로 대신 읽지 않고 전부 수동 확인으로 넘긴다."""
        body = _fixture("law_ordin_body.json")
        body["LawService"]["조문"]["조"] = [a for a in body["LawService"]["조문"]["조"] if a.get("조제목") != "용도지역 안에서의 용적률"]
        p = self.proposal(FakeApi(body))
        self.assertEqual(p.changed, [])
        self.assertEqual(len(p.manual), 16)
        self.assertTrue(all(r.kind == "far" for r in p.manual))
        self.assertEqual([n for n, _ in p.subarea_issues], ["서울도심"])

    def test_seoul_downtown_change_flags_subarea(self):
        p = self.proposal(FakeApi(_body_with("(단, 서울도심: 600퍼센트)", "(단, 서울도심: 650퍼센트)")))
        self.assertEqual((p.changed, p.manual), ([], []))
        self.assertEqual(p.subarea_issues, [("서울도심", "일반상업지역 600% → 650%")])
        out = apply(self.text, p, "2026-11-17")
        sa = _seoul(yaml.safe_load(out))["subareas"][0]
        self.assertEqual((sa["verified"], sa["far"]["일반상업지역"]), (False, 600))
        self.assertIn("서울도심", report([p], []))

    def test_note_with_comma_survives_edit(self):
        """1종일반 줄의 note 에는 쉼표·괄호가 있다. 줄 단위 수정이 note 를 깨지 않아야 한다."""
        p = self.proposal(FakeApi(_body_with("3. 제1종일반주거지역: 150퍼센트", "3. 제1종일반주거지역: 160퍼센트")))
        out = apply(self.text, p, "2026-11-17")
        z = _seoul(yaml.safe_load(out))["zones"]["제1종일반주거지역"]
        self.assertEqual((z["far"], z["max_floors"], z["verified"]), (160, 4, False))
        self.assertIn("별표 4, 서울시", z["note"])

    def test_report_lists_changes_and_source_link(self):
        p = self.proposal(FakeApi(_body_with("제3종일반주거지역: 250퍼센트", "제3종일반주거지역: 300퍼센트")))
        md = report([p], [])
        self.assertIn("| 제3종일반주거지역 | 용적률 | 250% | 300% | 300%로 변경 (미검증) |", md)
        self.assertIn("law.go.kr/자치법규/서울특별시도시계획조례", md)
        self.assertIn("변경 1건", md)


class WatchRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rules = self.tmp / "zoning.yaml"
        shutil.copy(SNAPSHOT, self.rules)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_same_promulgation_skips_body_and_does_not_write(self):
        text = self.rules.read_text(encoding="utf-8").replace("promulgated_on: null", 'promulgated_on: "2026-07-13"')
        self.rules.write_text(text, encoding="utf-8")
        api = FakeApi()
        props, errors = watch.run(self.rules, LawClient("OC1", api), "2026-11-17")
        self.assertEqual((props, errors), ([], []))
        self.assertFalse(any("lawService.do" in u for u in api.urls))
        self.assertEqual(self.rules.read_text(encoding="utf-8"), text)

    def test_new_promulgation_writes_rules_and_keeps_line_endings(self):
        before = self.rules.read_bytes()
        props, _ = watch.run(self.rules, LawClient("OC1", FakeApi(_body_with("6. 준주거지역: 400퍼센트", "6. 준주거지역: 450퍼센트"))), "2026-11-17")
        after = self.rules.read_bytes()
        self.assertEqual(len(props), 1)
        self.assertEqual(before.count(b"\r\n"), after.count(b"\r\n"))  # yaml 은 LF 유지
        self.assertIn(b"far: 450", after)

    def test_api_failure_is_reported_without_touching_rules(self):
        before = self.rules.read_bytes()
        client = LawClient("OC1", lambda url: json.dumps({"result": "실패", "msg": "IP 등록 필요"}, ensure_ascii=False))
        props, errors = watch.run(self.rules, client, "2026-11-17")
        self.assertEqual(props, [])
        self.assertIn("IP 등록 필요", errors[0])
        self.assertEqual(self.rules.read_bytes(), before)

    def test_main_writes_report_and_github_output(self):
        out = self.tmp / "gh_output"
        rep = self.tmp / "report.md"
        with mock.patch.dict(os.environ, {"LAW_OC": "OC1", "GITHUB_OUTPUT": str(out)}), mock.patch.object(
            watch, "LawClient", lambda oc: LawClient(oc, FakeApi(_body_with("6. 준주거지역: 400퍼센트", "6. 준주거지역: 450퍼센트")))
        ):
            code = watch.main(["--rules", str(self.rules), "--report", str(rep)])
        self.assertEqual(code, 0)
        self.assertIn("changed=true", out.read_text())
        self.assertIn("needs_review=true", out.read_text())
        self.assertIn("준주거지역", rep.read_text(encoding="utf-8"))

    def test_main_without_oc_fails(self):
        with mock.patch.dict(os.environ, {"LAW_OC": ""}):
            self.assertEqual(watch.main(["--rules", str(self.rules), "--report", str(self.tmp / "r.md")]), 2)


class RuleFileTests(unittest.TestCase):
    def test_no_note_was_split_by_a_comma(self):
        """{ …, note: A, B } 처럼 따옴표 없는 쉼표가 있으면 YAML 이 note 를 잘라 'B' 라는 빈 키를 만든다 (실제로 있었던 문제)."""
        allowed_null = {"effective_from", "promulgated_on", "url", "ref", "note"}

        def walk(o, path):
            if isinstance(o, dict):
                for k, v in o.items():
                    if v is None and k not in allowed_null:
                        self.fail(f"{path}/{k} 가 비어 있습니다 (쉼표 잘림?)")
                    walk(v, f"{path}/{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")

        for f in sorted(RULES.glob("*.yaml")):
            walk(yaml.safe_load(f.read_text(encoding="utf-8")), f.name)

    def test_every_watched_ordinance_has_name_and_org(self):
        """기관 구분: 법제처 지자체코드(org) 또는 [시도코드, 시도명, 지자체명](agency, 일괄 수집과 같은 방식)."""
        data = yaml.safe_load((RULES / "zoning.yaml").read_text(encoding="utf-8"))
        for o in data["ordinances"]:
            if "watch" in o:
                w = o["watch"]
                self.assertTrue(w["law_name"])
                if "agency" in w:
                    self.assertEqual(len(w["agency"]), 3, o["id"])
                    self.assertRegex(str(w["agency"][0]), r"^\d{2}$")
                else:
                    self.assertRegex(str(w["org"]), r"^\d{7}$")


class RuleBookIntegrationTests(unittest.TestCase):
    def test_auto_changed_value_shows_as_unverified_in_results(self):
        """PR 이 그대로 병합돼도, 사람이 verified 를 고치기 전까지 결과에 '미검증'으로 보인다."""
        text = SNAPSHOT.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        c = LawClient("OC1", FakeApi(_body_with("제3종일반주거지역: 250퍼센트", "제3종일반주거지역: 300퍼센트")))
        v = c.latest(SEOUL)
        changed = yaml.safe_load(apply(text, compare(_seoul(data), v, extract(c.articles(v))), "2026-11-17"))
        rb = RuleBook()
        rb.zoning = changed
        r = run_feasibility(SiteInput(1000, "제3종일반주거지역", "11440"), PlanOptions(), rb)
        self.assertEqual(r["massing"]["far_pct"], 300)
        self.assertTrue(r["review_required"])

    def test_ordinance_source_shows_checked_version(self):
        rb = RuleBook()
        rb.zoning = json.loads(json.dumps(rb.zoning))
        _seoul(rb.zoning)["watch"]["promulgated_on"] = "2025-05-15"
        z = rb.resolve_zone("제3종일반주거지역", "11440", "공동주택")
        self.assertIn("2025-05-15 공포판", z.ordinance.source.ref)
        self.assertIn("확인", z.ordinance.source.ref)


if __name__ == "__main__":
    unittest.main()
