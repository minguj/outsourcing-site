"""구독·고정지출 찾기 데모 테스트. 기대값은 seed.py 의 금액으로 손으로 계산했다."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from fastapi.testclient import TestClient

from backend import main
from backend.spend import detect, enrich_ai, merchants, router as spend_router

AS_OF = date(2026, 11, 15)


def tx(i, day, amount, merchant="TEST", *, kind="approval", usd=None, approval_id=None):
    t = {"id": f"t{i}", "date": day, "merchant_raw": merchant, "amount": amount, "type": kind,
         "orig_amount": usd, "orig_currency": "USD" if usd is not None else None}
    if approval_id:
        t["approval_id"] = approval_id
    return t


class MerchantTests(unittest.TestCase):
    def test_normalize_and_lookup(self):
        self.assertEqual(merchants.normalize("KCP*쿠팡와우 월회비"), "쿠팡와우월회비")
        self.assertEqual(merchants.normalize("NETFLIX.COM"), "NETFLIX")
        self.assertEqual(merchants.normalize("GOOGLE*YouTubePremium"), "YOUTUBEPREMIUM")
        self.assertEqual(merchants.normalize("(주)우아한형제들"), "우아한형제들")
        self.assertEqual(merchants.lookup("쿠팡와우월회비")["service"], "쿠팡 와우 멤버십")
        self.assertEqual(merchants.lookup("YOUTUBEPREMIUM")["category"], "ott")
        self.assertIsNone(merchants.lookup("쿠팡"))  # 일반 쿠팡 주문은 멤버십이 아니다


class DetectTests(unittest.TestCase):
    def test_cancelled_approval_is_removed(self):
        items = [tx(1, "2026-10-02", 45900), tx(2, "2026-10-03", 45900, kind="cancel", approval_id="t1"),
                 tx(3, "2026-10-04", 1000)]
        self.assertEqual([t["id"] for t in detect.effective(items)], ["t3"])

    def test_monthly_weekly_and_irregular(self):
        monthly = [tx(i, d, 9900) for i, d in enumerate(["2026-06-10", "2026-07-10", "2026-08-10"])]
        result = detect.analyze(monthly, None, AS_OF)
        self.assertEqual((result["cadence"], result["next_date"]), ("monthly", "2026-09-10"))
        self.assertEqual(result["status"], "cancelled")  # 9/10 + 유예 10일이 지났다
        weekly = [tx(i, f"2026-11-{d:02d}", 19900) for i, d in enumerate([1, 8, 15])]
        result = detect.analyze(weekly, None, AS_OF)
        self.assertEqual((result["cadence"], result["monthly_equivalent"]), ("weekly", 19900 * 52 // 12))
        irregular = [tx(i, d, 9900) for i, d in enumerate(["2026-06-01", "2026-06-12", "2026-07-30"])]
        self.assertIsNone(detect.analyze(irregular, None, AS_OF))

    def test_one_skipped_month_lowers_confidence(self):
        dates = ["2026-07-05", "2026-08-05", "2026-10-05", "2026-11-05"]
        result = detect.analyze([tx(i, d, 5000) for i, d in enumerate(dates)], None, AS_OF)
        self.assertEqual((result["cadence"], result["confidence"]), ("monthly", 82 - 15))

    def test_trial_price_increase_fx_and_variable(self):
        trial = [tx(1, "2026-09-20", 100), tx(2, "2026-10-20", 13900)]
        result = detect.analyze(trial, merchants.lookup("TVING"), AS_OF)
        self.assertEqual([s["type"] for s in result["signals"]], ["trial_conversion"])
        self.assertEqual(result["expected_amount"], 13900)

        up = [tx(i, f"2026-{m:02d}-05", a) for i, (m, a) in enumerate([(8, 13500), (9, 13500), (10, 17000), (11, 17000)])]
        signal = detect.analyze(up, merchants.lookup("NETFLIX"), AS_OF)["signals"][0]
        self.assertEqual((signal["type"], signal["date"], signal["from"], signal["to"]),
                         ("price_increase", "2026-10-05", 13500, 17000))

        fx = [tx(i, f"2026-{m:02d}-18", a, usd=20.0) for i, (m, a) in enumerate([(8, 27310), (9, 28450), (10, 28190)])]
        result = detect.analyze(fx, merchants.lookup("OPENAI"), AS_OF)
        self.assertEqual((result["amount_type"], result["expected_amount"]), ("fx", round((27310 + 28450 + 28190) / 3)))
        self.assertNotIn("price_increase", [s["type"] for s in result["signals"]])

        phone = [tx(i, f"2026-{m:02d}-25", a) for i, (m, a) in enumerate([(8, 59900), (9, 62400), (10, 60100)])]
        result = detect.analyze(phone, merchants.lookup("KT통신"), AS_OF)
        self.assertEqual((result["amount_type"], result["expected_amount"], result["signals"]), ("variable", 60100, []))

    def test_split_two_lines_and_month_end(self):
        lines = [tx(i, f"2026-{m:02d}-{d}", a) for i, (m, d, a) in
                 enumerate([(9, 21, 45100), (9, 26, 69800), (10, 21, 45300), (10, 26, 69800)])]
        self.assertEqual([[t["amount"] for t in c] for c in detect.split_by_amount(lines)],
                         [[45100, 45300], [69800, 69800]])
        self.assertEqual(detect.add_months(date(2026, 1, 31), 1), date(2026, 2, 28))


class SpendApiTests(unittest.TestCase):
    def setUp(self):
        spend_router.SANDBOXES.clear()
        spend_router.AI_CACHE.clear()
        spend_router.AI_CALLS.clear()
        spend_router.REPORTS.clear()
        self.client = TestClient(main.app)
        self.token = self.client.post("/api/demo/spend/sandbox").json()["token"]

    def get(self, persona, token=None):
        return self.client.get(f"/api/demo/spend/personas/{persona}/analysis",
                               headers={"X-Spend-Sandbox": token or self.token})

    def post(self, path, json=None):
        return self.client.post(f"/api/demo/spend{path}", json=json, headers={"X-Spend-Sandbox": self.token})

    def by_service(self, view):
        return {r["service"]: r for r in view["series"]}

    def test_totals_by_persona(self):
        jisoo = self.get("jisoo").json()["summary"]
        # 구독: 넷플릭스 17,000 + 유튜브 14,900 + 노션(최근 3번 평균) 13,993 + 티빙 13,900 + 스포티파이 11,990
        #       + 멜론 10,900 + 쿠팡와우 7,890 + iCloud 4,400 + 배민클럽 3,990 + ChatGPT(최근 3번 평균) 27,983
        self.assertEqual(jisoo["subscription_monthly"], 126946)
        self.assertEqual(jisoo["fixed_monthly"], 60100)  # 휴대폰: 최근 3번 59,900·62,400·60,100의 중앙값
        self.assertEqual((jisoo["monthly_total"], jisoo["yearly_total"]), (187046, 187046 * 12))
        junghoon = self.get("junghoon").json()["summary"]
        # 관리비 230,800 + 생명 152,000 + 화재 87,400 + 휴대폰 69,800 + 전기 58,400 + 휴대폰 45,200 + 인터넷 33,000 + 가스 16,700
        self.assertEqual(junghoon["fixed_monthly"], 693300)
        # 학원 380,000 + MS365 119,000/12 = 9,916 + 디즈니+ 9,900 + 웨이브 7,900 + 네이버플러스 4,900
        self.assertEqual(junghoon["subscription_monthly"], 412616)
        haneul = self.get("haneul").json()["summary"]
        # 밀키트 19,900×52/12 = 86,233 + 헬로모바일 16,900 + 스포티파이 11,990 + 밀리의서재 9,900 + 리디 4,900
        self.assertEqual(haneul["monthly_total"], 129923)

    def test_haneul_weekly_trial_and_content_duplicate(self):
        with mock.patch.object(enrich_ai, "enabled", return_value=True), \
                mock.patch.object(enrich_ai, "classify", return_value=[
                    {"key": "밀리의서재", "service": "밀리의서재", "category": "content", "kind": "subscription",
                     "recurring": True, "reason": ""},
                    {"key": "RIDI리디셀렉트", "service": "리디셀렉트", "category": "content", "kind": "subscription",
                     "recurring": True, "reason": ""}]):
            view = self.post("/personas/haneul/enrich").json()
        savings = {s["title"]: s["monthly"] for s in view["savings"]}
        self.assertEqual(savings["도서·콘텐츠 구독 2개 정리"], 4900)  # 밀리의서재 9,900을 남길 때
        self.assertEqual(savings["스포티파이 체험 후 유료 전환"], 11990)  # 2026-09-03 전환, 기준일까지 73일(90일 이내)
        self.assertEqual(view["savings_total"], 4900 + 11990)
        weekly = self.by_service(view)["프레시위클리 밀키트구독"]
        self.assertEqual((weekly["cadence"], weekly["count"], weekly["next_date"]), ("weekly", 10, "2026-11-16"))

    def test_jisoo_signals_duplicates_and_savings(self):
        view = self.get("jisoo").json()
        rows = self.by_service(view)
        netflix = next(s for s in rows["넷플릭스"]["signals"] if s["type"] == "price_increase")
        self.assertEqual((netflix["date"], netflix["from"], netflix["to"]), ("2026-08-05", 13500, 17000))
        self.assertEqual(next(s for s in rows["티빙"]["signals"] if s["type"] == "trial_conversion")["date"], "2026-10-20")
        watcha = rows["WATCHA 왓챠"]
        self.assertEqual((watcha["status"], watcha["next_date"]), ("cancelled", "2026-09-08"))
        self.assertNotIn("duplicate", [s["type"] for s in watcha["signals"]])  # 해지된 구독은 중복에서 뺀다
        self.assertIn("duplicate", [s["type"] for s in rows["멜론"]["signals"]])
        savings = {s["title"]: s["monthly"] for s in view["savings"]}
        self.assertEqual(savings["영상(OTT) 구독 3개 정리"], 14900 + 13900)  # 넷플릭스(가장 비쌈)만 남길 때
        self.assertEqual(savings["음악 구독 2개 정리"], 10900)
        self.assertEqual(savings["티빙 체험 후 유료 전환"], 13900)
        self.assertEqual(savings["넷플릭스 요금 인상"], 3500)
        # 해지 후보: 유튜브 14,900 + 티빙 13,900 (중복·체험 양쪽에 있어도 한 번) + 멜론 10,900. 인상분은 해지 금액이 아니라 뺀다
        self.assertEqual(view["savings_total"], 14900 + 13900 + 10900)
        cancelled = [t for t in view["transactions"] if t["merchant_raw"] == "쿠팡(주)" and t["amount"] == 45900]
        self.assertEqual(sorted(t["type"] for t in cancelled), ["approval", "cancel"])
        self.assertEqual(view["ai_pending"], 2)  # WATCHA, NOTION

    def test_junghoon_lines_yearly_and_upcoming(self):
        view = self.get("junghoon").json()
        rows = self.by_service(view)
        self.assertIn("휴대폰 요금 (69,800원)", rows)
        self.assertIn("휴대폰 요금 (45,200원)", rows)
        self.assertEqual(len([r for r in view["series"] if r["service"] == "전기요금"]), 1)  # 여름에 올라도 한 묶음
        ms = rows["Microsoft 365"]
        self.assertEqual((ms["cadence"], ms["next_date"], ms["monthly_equivalent"]), ("yearly", "2027-06-11", 9916))
        self.assertEqual(rows["피트니스"]["status"], "cancelled")
        self.assertEqual(len(view["upcoming"]), 12)
        self.assertEqual((view["upcoming"][0]["date"], view["upcoming"][0]["service"]), ("2026-11-18", "전기요금"))
        self.assertIn("한결생명보험", rows)

    def test_ai_enrich_validates_caches_and_drops_non_recurring(self):
        answer = [
            {"key": "WATCHA왓챠", "service": "왓챠", "category": "ott", "kind": "subscription", "recurring": True,
             "reason": "OTT"},
            {"key": "NOTIONLABS", "service": "Notion", "category": "spaceship", "kind": "subscription",
             "recurring": True, "reason": "x"},
            {"key": "다른가맹점", "service": "x", "category": "other", "kind": "fixed", "recurring": True, "reason": ""},
        ]
        with mock.patch.object(enrich_ai, "enabled", return_value=True), \
                mock.patch.object(enrich_ai, "classify", return_value=answer) as called:
            view = self.post("/personas/jisoo/enrich").json()
        self.assertEqual(view["enrich"], {"asked": 2, "saved": 1, "status": "partial"})
        self.assertEqual(sorted(i["key"] for i in called.call_args.args[0]), ["NOTIONLABS", "WATCHA왓챠"])
        watcha = self.by_service(view)["왓챠"]
        self.assertEqual((watcha["source"], watcha["category"]), ("ai", "ott"))
        self.assertEqual(view["ai_pending"], 1)

        other = self.client.post("/api/demo/spend/sandbox").json()["token"]
        self.assertEqual(self.by_service(self.get("jisoo", other).json())["왓챠"]["source"], "ai")  # 다른 방문자도 재사용

        not_recurring = [{"key": "프레시위클리밀키트구독", "service": "x", "category": "other", "kind": "subscription",
                          "recurring": False, "reason": ""}]
        with mock.patch.object(enrich_ai, "enabled", return_value=True), \
                mock.patch.object(enrich_ai, "classify", return_value=not_recurring):
            view = self.post("/personas/haneul/enrich").json()
        self.assertNotIn("프레시위클리 밀키트구독", self.by_service(view))

    def test_ai_fallbacks(self):
        with mock.patch.object(enrich_ai, "enabled", return_value=False):
            self.assertEqual(self.post("/personas/jisoo/enrich").json()["enrich"]["status"], "no_ai")
        with mock.patch.object(enrich_ai, "enabled", return_value=True), \
                mock.patch.object(enrich_ai, "classify", side_effect=enrich_ai.EnrichError("500")):
            self.assertEqual(self.post("/personas/jisoo/enrich").json()["enrich"]["status"], "failed")
        spend_router.SANDBOXES[self.token]["data"]["ai_runs"] = spend_router.AI_PER_SANDBOX
        with mock.patch.object(enrich_ai, "enabled", return_value=True), \
                mock.patch.object(enrich_ai, "classify", side_effect=AssertionError("호출하면 안 됨")):
            self.assertEqual(self.post("/personas/jisoo/enrich").json()["enrich"]["status"], "limit")

    def test_review_reject_confirm_reset(self):
        netflix = self.by_service(self.get("jisoo").json())["넷플릭스"]
        path = f"/personas/jisoo/series/{netflix['id']}/review"
        rejected = self.post(path, {"decision": "reject"}).json()
        self.assertEqual(rejected["summary"]["subscription_monthly"], 126946 - 17000)
        self.assertEqual({s["title"]: s["monthly"] for s in rejected["savings"]}["영상(OTT) 구독 2개 정리"], 13900)
        self.assertEqual(rejected["series"][-1]["service"], "넷플릭스")  # 제외한 항목은 맨 아래
        confirmed = self.post(path, {"decision": "confirm"}).json()
        self.assertEqual(self.by_service(confirmed)["넷플릭스"]["confidence"], 99)
        reset = self.post(path, {"decision": "reset"}).json()
        self.assertIsNone(self.by_service(reset)["넷플릭스"]["review"])
        self.assertEqual(self.post("/personas/jisoo/series/sr-0000000000/review", {"decision": "confirm"}).status_code, 409)
        self.assertEqual(self.post("/personas/jisoo/series/netflix/review", {"decision": "confirm"}).status_code, 422)

    def test_aliases_are_one_series(self):
        netflix = self.by_service(self.get("jisoo").json())["넷플릭스"]
        self.assertEqual(netflix["aliases"], ["NETFLIX.COM", "넷플릭스(NETFLIX)"])  # 9월부터 표기가 바뀌어도 한 묶음
        self.assertEqual((netflix["count"], netflix["first_date"]), (7, "2026-05-05"))

    def test_payment_alerts_within_three_days(self):
        alerts = self.get("jisoo").json()["alerts"]
        self.assertEqual([(a["service"], a["date"], a["d_day"]) for a in alerts], [("ChatGPT Plus", "2026-11-18", 3)])
        alerts = self.get("haneul").json()["alerts"]
        self.assertEqual([(a["date"], a["d_day"]) for a in alerts], [("2026-11-16", 1), ("2026-11-17", 2)])

    def test_easy_cancel_completes_and_leaves_totals(self):
        clock = datetime(2026, 11, 16, 13, 0, 0, tzinfo=spend_router.KST)
        rows = self.by_service(self.get("jisoo").json())
        path = f"/personas/jisoo/series/{rows['넷플릭스']['id']}/cancel"
        with mock.patch.object(spend_router, "_now", return_value=clock):
            started = self.by_service(self.post(path, {"action": "request"}).json())["넷플릭스"]["cancel"]
            self.assertEqual((started["status"], started["method"]), ("processing", "easy"))
            self.assertEqual(self.post(path, {"action": "request"}).status_code, 409)  # 두 번 요청 불가
        with mock.patch.object(spend_router, "_now", return_value=clock + timedelta(seconds=5)):
            view = self.get("jisoo").json()
        self.assertEqual(self.by_service(view)["넷플릭스"]["cancel"]["status"], "done")
        self.assertEqual(view["summary"]["subscription_monthly"], 126946 - 17000)
        self.assertEqual(view["summary"]["saved_monthly"], 17000)
        self.assertNotIn("넷플릭스", [u["service"] for u in view["upcoming"]])
        # 남은 OTT는 유튜브·티빙 → 비싼 유튜브를 남기면 티빙 13,900 절감
        self.assertEqual({s["title"]: s["monthly"] for s in view["savings"]}["영상(OTT) 구독 2개 정리"], 13900)
        self.assertEqual(view["series"][-1]["service"], "넷플릭스")  # 해지 완료는 맨 아래
        with mock.patch.object(spend_router, "_now", return_value=clock + timedelta(seconds=6)):
            undone = self.post(path, {"action": "undo"}).json()
        self.assertEqual(undone["summary"]["subscription_monthly"], 126946)

    def test_guide_cancel_and_not_cancellable(self):
        rows = self.by_service(self.get("jisoo").json())
        notion = rows["NOTION LABS INC"]  # 사전에 없는 구독 → 안내 후 직접 해지
        path = f"/personas/jisoo/series/{notion['id']}/cancel"
        guide = self.by_service(self.post(path, {"action": "request"}).json())["NOTION LABS INC"]["cancel"]
        self.assertEqual((guide["status"], len(guide["steps"])), ("guide", 4))
        self.assertIn("2026-11-09", guide["steps"][2])
        done = self.post(path, {"action": "confirm"}).json()
        self.assertEqual(done["summary"]["saved_monthly"], notion["monthly_equivalent"])
        phone = f"/personas/jisoo/series/{rows['휴대폰 요금']['id']}/cancel"
        self.assertIn("고정지출", self.post(phone, {"action": "request"}).json()["detail"])
        watcha = f"/personas/jisoo/series/{rows['WATCHA 왓챠']['id']}/cancel"
        self.assertEqual(self.post(watcha, {"action": "request"}).status_code, 409)  # 이미 해지 추정
        self.assertEqual(self.post(f"/personas/jisoo/series/{rows['멜론']['id']}/cancel", {"action": "confirm"}).status_code, 409)

    def test_merchant_registry_and_reports(self):
        registry = self.client.get("/api/demo/spend/merchants", headers={"X-Spend-Sandbox": self.token}).json()
        self.assertEqual(registry["stats"]["recurring_merchants"], 28)
        self.assertEqual((registry["stats"]["dictionary"], registry["stats"]["rule"]), (21, 7))
        self.assertEqual(registry["stats"]["coverage_pct"], 75)
        rows = {r["service"]: r for r in registry["merchants"]}
        self.assertEqual(rows["휴대폰 요금"]["personas"], ["김지수", "박정훈"])
        self.assertIn("한결생명보험", rows)
        self.assertEqual(len(rows["넷플릭스"]["aliases"]), 2)

        melon = self.by_service(self.get("jisoo").json())["멜론"]
        path = f"/personas/jisoo/series/{melon['id']}/review"
        tokens = [self.token] + [self.client.post("/api/demo/spend/sandbox").json()["token"] for _ in range(2)]
        for token in tokens[:2]:
            self.client.post(f"/api/demo/spend{path}", json={"decision": "reject"}, headers={"X-Spend-Sandbox": token})
        self.client.post(f"/api/demo/spend{path}", json={"decision": "confirm"}, headers={"X-Spend-Sandbox": tokens[2]})
        row = {r["service"]: r for r in self.client.get(
            "/api/demo/spend/merchants", headers={"X-Spend-Sandbox": self.token}).json()["merchants"]}["멜론"]
        self.assertEqual((row["reports"], row["needs_review"]), ({"confirm": 1, "reject": 2}, True))
        self.client.post(f"/api/demo/spend{path}", json={"decision": "reset"}, headers={"X-Spend-Sandbox": self.token})
        row = {r["service"]: r for r in self.client.get(
            "/api/demo/spend/merchants", headers={"X-Spend-Sandbox": self.token}).json()["merchants"]}["멜론"]
        self.assertEqual((row["reports"], row["needs_review"]), ({"confirm": 1, "reject": 1}, False))

    def test_sandbox_required(self):
        self.assertEqual(self.get("jisoo", token="x" * 32).status_code, 404)
        self.assertEqual(self.get("nobody").status_code, 422)


if __name__ == "__main__":
    unittest.main()
