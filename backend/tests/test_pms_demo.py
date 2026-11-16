"""운영 플랫폼(PMS) 데모: 청구 계산, 역할 × 사업장 권한, 계약 상태, 샌드박스 격리."""
import unittest
from datetime import date, datetime

from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import site_api
from backend.main import app
from backend.pms import billing, integration, ledger, router as pms_router, voc, voc_ai


class BillingMathTests(unittest.TestCase):
    """기대값은 손으로 계산했다 (엔진 출력을 복사하지 않음)."""

    def test_full_month_is_not_prorated(self):
        self.assertEqual(billing.prorated_fee(3_200_000, date(2026, 3, 1), None, "2026-11"), 3_200_000)

    def test_move_in_mid_month_counts_move_in_day(self):
        # 11/15 ~ 11/30 = 16일, 3,900,000 x 16/30 = 2,080,000
        self.assertEqual(billing.prorated_fee(3_900_000, date(2026, 11, 15), None, "2026-11"), 2_080_000)

    def test_move_out_mid_month_counts_move_out_day(self):
        # 11/1 ~ 11/20 = 20일, 3,900,000 x 20/30 = 2,600,000
        self.assertEqual(billing.prorated_fee(3_900_000, date(2026, 1, 1), date(2026, 11, 20), "2026-11"), 2_600_000)

    def test_prorated_amount_drops_below_ten_won(self):
        # 11/24 ~ 11/30 = 7일, 3,200,000 x 7/30 = 746,666.6 -> 746,660
        self.assertEqual(billing.prorated_fee(3_200_000, date(2026, 11, 24), None, "2026-11"), 746_660)

    def test_no_days_in_month_means_no_invoice(self):
        contract = {"start_date": "2026-12-01", "end_date": None, "monthly_fee": 3_200_000}
        self.assertIsNone(billing.build_invoice(contract, "2026-11", [], {}))

    def test_due_date_rolls_to_next_month_and_clamps_day(self):
        self.assertEqual(billing.due_date("2026-11", 10), date(2026, 12, 10))
        self.assertEqual(billing.due_date("2026-12", 10), date(2027, 1, 10))
        self.assertEqual(billing.due_date("2027-01", 31), date(2027, 2, 28))

    def test_late_fee_is_simple_daily_interest_on_remaining_principal(self):
        # 1,000,000 x 12% x 30/365 = 9,863.0 -> 9,860
        self.assertEqual(billing.late_fee(1_000_000, date(2026, 12, 10), date(2027, 1, 9), 12.0), 9_860)
        self.assertEqual(billing.late_fee(1_000_000, date(2026, 12, 10), date(2026, 12, 10), 12.0), 0)
        self.assertEqual(billing.late_fee(0, date(2026, 12, 10), date(2027, 1, 9), 12.0), 0)

    def test_invoice_status(self):
        due = date(2026, 12, 10)
        self.assertEqual(billing.invoice_status(100, [], due, date(2026, 12, 1)), "issued")
        self.assertEqual(billing.invoice_status(100, [{"amount": 40}], due, date(2026, 12, 1)), "partial")
        self.assertEqual(billing.invoice_status(100, [{"amount": 40}], due, date(2026, 12, 11)), "overdue")
        self.assertEqual(billing.invoice_status(100, [{"amount": 100}], due, date(2026, 12, 11)), "paid")


class PmsApiTests(unittest.TestCase):
    def setUp(self):
        site_api.HITS.clear()
        pms_router.SANDBOXES.clear()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        response = self.client.post("/api/demo/pms/sandbox")
        self.assertEqual(response.status_code, 200, response.text)
        self.box = response.json()
        self.token = self.box["token"]

    def call(self, method, path, user, **kwargs):
        headers = {"X-Pms-Sandbox": self.token, "X-Pms-User": user}
        return self.client.request(method, f"/api/demo/pms{path}", headers=headers, **kwargs)

    def run_november(self, user="u-mgr-garam"):
        return self.call("POST", "/sites/site-garam/billing-runs", user, json={"month": "2026-11"})

    # ---------- 샌드박스 ----------

    def test_sandbox_lists_demo_users_and_is_not_cached(self):
        roles = {u["id"]: u["role"] for u in self.box["users"]}
        self.assertEqual(roles["u-hq"], "hq_admin")
        self.assertEqual(roles["u-guardian"], "guardian")
        response = self.call("GET", "/me", "u-care-garam")
        self.assertEqual(response.json()["sites"], ["가람 시니어 레지던스"])
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_sandboxes_are_isolated(self):
        self.run_november()
        other = self.client.post("/api/demo/pms/sandbox").json()["token"]
        headers = {"X-Pms-Sandbox": other, "X-Pms-User": "u-mgr-garam"}
        self.assertEqual(self.client.get("/api/demo/pms/sites/site-garam/invoices", headers=headers).json(), [])

    def test_unknown_or_malformed_sandbox(self):
        headers = {"X-Pms-Sandbox": "x" * 32, "X-Pms-User": "u-hq"}
        self.assertEqual(self.client.get("/api/demo/pms/sites", headers=headers).status_code, 404)
        headers = {"X-Pms-Sandbox": "bad token!", "X-Pms-User": "u-hq"}
        self.assertEqual(self.client.get("/api/demo/pms/sites", headers=headers).status_code, 422)
        self.assertEqual(self.call("GET", "/sites", "u-nobody").status_code, 404)

    # ---------- 사업장 범위 ----------

    def test_hq_sees_all_sites_and_site_staff_only_their_own(self):
        self.assertEqual({s["id"] for s in self.call("GET", "/sites", "u-hq").json()}, {"site-garam", "site-nuri"})
        self.assertEqual([s["id"] for s in self.call("GET", "/sites", "u-mgr-garam").json()], ["site-garam"])
        self.assertEqual({s["id"] for s in self.call("GET", "/sites", "u-acct").json()}, {"site-garam", "site-nuri"})

    def test_other_site_data_is_not_found_not_forbidden(self):
        for path in ("/sites/site-nuri/units", "/sites/site-nuri/contracts", "/sites/site-nuri/invoices",
                     "/residents/r-n101"):
            self.assertEqual(self.call("GET", path, "u-mgr-garam").status_code, 404, path)
        response = self.call("POST", "/contracts/c-n101/transition", "u-mgr-garam", json={"to": "terminated"})
        self.assertEqual(response.status_code, 404)

    def test_unit_board_status(self):
        units = {u["id"]: u for u in self.call("GET", "/sites/site-garam/units", "u-care-garam").json()}
        self.assertEqual(len(units), 12)
        self.assertEqual(units["site-garam-A101"]["status"], "occupied")
        self.assertEqual(units["site-garam-A304"]["status"], "maintenance")
        self.assertEqual(units["site-garam-A303"]["status"], "vacant")

    # ---------- 역할 권한과 개인정보 ----------

    def test_role_permissions(self):
        self.assertEqual(self.run_november("u-care-garam").status_code, 403)
        self.assertEqual(self.run_november("u-hq").status_code, 403)  # 본사는 조회만, 청구 실행은 사업장
        self.assertEqual(self.call("GET", "/sites/site-garam/contracts", "u-care-garam").status_code, 403)
        self.assertEqual(self.call("GET", "/audit", "u-acct").status_code, 403)
        self.assertEqual(self.run_november("u-acct").status_code, 200)

    def test_resident_list_has_names_only_and_respects_scope(self):
        rows = self.call("GET", "/sites/site-garam/residents", "u-care-garam").json()
        self.assertEqual(len(rows), 5)
        self.assertEqual(set(rows[0]), {"id", "name", "unit_id", "unit_number", "status", "status_label"})
        own = self.call("GET", "/sites/site-garam/residents", "u-guardian").json()
        self.assertEqual([r["id"] for r in own], ["r-101"])
        self.assertEqual(self.call("GET", "/sites/site-nuri/residents", "u-care-garam").status_code, 404)
        self.assertEqual(self.call("GET", "/audit", "u-hq").json(), [])  # 목록 조회는 감사 기록 대상 아님

    def test_care_staff_sees_care_notes_but_masked_phones(self):
        body = self.call("GET", "/residents/r-101", "u-care-garam").json()
        self.assertEqual(body["phone"], "010-****-7731")
        self.assertEqual(body["guardian"]["phone"], "010-****-4402")
        self.assertIn("고혈압", body["care"]["notes"])

    def test_accountant_sees_phone_but_not_care_notes(self):
        body = self.call("GET", "/residents/r-101", "u-acct").json()
        self.assertEqual(body["phone"], "010-2481-7731")
        self.assertIsNone(body["care"])

    def test_revealing_sensitive_fields_is_audited(self):
        self.call("GET", "/residents/r-101", "u-care-garam")
        self.call("GET", "/residents/r-n101", "u-acct")
        garam = self.call("GET", "/audit", "u-mgr-garam").json()
        self.assertEqual([(e["user_id"], e["target"], e["fields"]) for e in garam], [("u-care-garam", "r-101", ["care"])])
        everything = self.call("GET", "/audit", "u-hq").json()
        self.assertEqual(len(everything), 2)

    def test_guardian_sees_only_own_family(self):
        self.run_november()
        self.assertEqual(self.call("GET", "/residents/r-102", "u-guardian").status_code, 404)
        own = self.call("GET", "/residents/r-101", "u-guardian").json()
        self.assertIsNone(own["care"])
        invoices = self.call("GET", "/sites/site-garam/invoices", "u-guardian", params={"month": "2026-11"}).json()
        self.assertEqual([i["resident_id"] for i in invoices], ["r-101"])

    # ---------- 청구·수납 ----------

    def test_monthly_billing_with_proration_and_services_runs_once(self):
        result = self.run_november().json()
        self.assertEqual(sorted(result["created"]), ["inv-c-101-2026-11", "inv-c-102-2026-11", "inv-c-201-2026-11", "inv-c-202-2026-11"])
        again = self.run_november().json()
        self.assertEqual(again["created"], [])
        self.assertEqual(len(again["skipped"]), 4)
        invoices = {i["contract_id"]: i for i in self.call("GET", "/sites/site-garam/invoices", "u-acct",
                                                           params={"month": "2026-11", "as_of": "2026-12-01"}).json()}
        self.assertEqual(invoices["c-101"]["total"], 3_200_000 + 20 * 9_000 + 2 * 30_000)
        self.assertEqual(invoices["c-201"]["total"], 2_080_000 + 6 * 9_000)
        self.assertEqual(invoices["c-202"]["total"], 2_600_000)
        self.assertEqual(invoices["c-101"]["due_date"], "2026-12-10")
        self.assertNotIn("c-301", invoices)  # 작성 중 계약은 청구하지 않음

    def test_partial_payment_overdue_and_late_fee(self):
        self.run_november()
        invoice_id = "inv-c-102-2026-11"
        total = 3_200_000 + 4 * 15_000 + 12 * 9_000  # 3,368,000
        response = self.call("POST", f"/invoices/{invoice_id}/payments", "u-acct",
                             json={"amount": 2_368_000, "paid_on": "2026-12-05", "as_of": "2026-12-05"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "partial")
        self.assertEqual(response.json()["outstanding"], total - 2_368_000)
        late = self.call("GET", "/sites/site-garam/invoices", "u-acct", params={"month": "2026-11", "as_of": "2027-01-09"}).json()
        row = next(i for i in late if i["id"] == invoice_id)
        self.assertEqual(row["status"], "overdue")
        self.assertEqual(row["late_fee"], 9_860)  # 1,000,000 x 12% x 30/365
        over = self.call("POST", f"/invoices/{invoice_id}/payments", "u-acct",
                         json={"amount": 1_000_010, "paid_on": "2027-01-09", "as_of": "2027-01-09"})
        self.assertEqual(over.status_code, 409)

    def test_service_usage_is_billed_next_run(self):
        self.assertEqual(self.call("POST", "/residents/r-101/usages", "u-acct",
                                   json={"service": "meal", "quantity": 1, "date": "2026-11-20"}).status_code, 403)
        response = self.call("POST", "/residents/r-101/usages", "u-care-garam",
                             json={"service": "meal", "quantity": 3, "date": "2026-11-20"})
        self.assertEqual(response.status_code, 200, response.text)
        wrong_site_service = self.call("POST", "/residents/r-101/usages", "u-care-garam",
                                       json={"service": "parking", "quantity": 1, "date": "2026-11-20"})
        self.assertEqual(wrong_site_service.status_code, 409)
        self.run_november()
        invoice = next(i for i in self.call("GET", "/sites/site-garam/invoices", "u-acct").json() if i["contract_id"] == "c-101")
        self.assertEqual(next(l for l in invoice["lines"] if l["code"] == "meal")["quantity"], 23)

    # ---------- 계약 상태 ----------

    def test_contract_flow_and_rules(self):
        bad = self.call("POST", "/contracts/c-301/transition", "u-mgr-garam", json={"to": "active"})
        self.assertEqual(bad.status_code, 409)
        self.assertEqual(self.call("POST", "/contracts/c-301/transition", "u-care-garam", json={"to": "signed"}).status_code, 403)
        signed = self.call("POST", "/contracts/c-301/transition", "u-mgr-garam", json={"to": "signed"})
        self.assertEqual(signed.json()["status_label"], "체결")
        self.assertEqual(signed.json()["next"], ["active", "cancelled"])
        self.assertEqual(signed.json()["resident_name"], "한정희")
        units = {u["id"]: u for u in self.call("GET", "/sites/site-garam/units", "u-mgr-garam").json()}
        self.assertEqual(units["site-garam-A301"]["status"], "reserved")
        active = self.call("POST", "/contracts/c-301/transition", "u-mgr-garam", json={"to": "active", "date": "2026-12-01"})
        self.assertEqual(active.status_code, 200)
        early = self.call("POST", "/contracts/c-301/transition", "u-mgr-garam", json={"to": "terminated", "date": "2026-11-01"})
        self.assertEqual(early.status_code, 409)

    def test_double_booking_and_maintenance_are_blocked(self):
        data = pms_router.SANDBOXES[self.token]["data"]
        data["contracts"].append({"id": "c-dup", "site_id": "site-garam", "unit_id": "site-garam-A101", "resident_id": "r-301",
                                  "status": "draft", "start_date": "2026-12-01", "end_date": None,
                                  "deposit": 1, "monthly_fee": 1})
        data["contracts"].append({"id": "c-fix", "site_id": "site-garam", "unit_id": "site-garam-A304", "resident_id": "r-301",
                                  "status": "draft", "start_date": "2026-12-01", "end_date": None,
                                  "deposit": 1, "monthly_fee": 1})
        dup = self.call("POST", "/contracts/c-dup/transition", "u-mgr-garam", json={"to": "signed"})
        self.assertIn("다른 계약", dup.json()["detail"])
        fix = self.call("POST", "/contracts/c-fix/transition", "u-mgr-garam", json={"to": "signed"})
        self.assertIn("정비", fix.json()["detail"])


class VocRuleTests(unittest.TestCase):
    def test_redact_hides_phone_email_and_known_names(self):
        text = "김순자 어머니 연락은 010-2481-7731 이나 son@example.com 으로 주세요. 박지훈 드림"
        out = voc.redact(text, ["김순자", "박지훈", "김"])
        self.assertNotIn("2481", out)
        self.assertNotIn("example.com", out)
        self.assertNotIn("김순자", out)
        self.assertNotIn("박지훈", out)
        self.assertIn("[전화번호]", out)
        self.assertIn("[이메일]", out)

    def test_rule_classify(self):
        leak = voc.rule_classify("화장실 천장에서 물이 떨어져요")
        self.assertEqual((leak["category"], leak["urgency"]), ("facility", "high"))
        self.assertEqual(voc.rule_classify("보일러가 고장 났어요")["urgency"], "normal")
        self.assertEqual(voc.rule_classify("반찬에 견과류가 있었는데 알레르기가 있어요")["category"], "care")
        billing_q = voc.rule_classify("청구 금액이 어떻게 계산되는지 궁금합니다")
        self.assertEqual((billing_q["category"], billing_q["urgency"]), ("billing", "low"))
        self.assertEqual(voc.rule_classify("안녕하세요")["category"], "other")

    def test_normalize_ai_accepts_only_known_values(self):
        good = {"category": "noise", "urgency": "normal", "summary": " 야간 소음 ", "reason": "윗집 소음"}
        self.assertEqual(voc.normalize_ai(good)["summary"], "야간 소음")
        self.assertIsNone(voc.normalize_ai({**good, "category": "elevator"}))
        self.assertIsNone(voc.normalize_ai({**good, "urgency": "urgent"}))
        self.assertIsNone(voc.normalize_ai({**good, "summary": ""}))
        self.assertIsNone(voc.normalize_ai("facility"))


class IntegrationRuleTests(unittest.TestCase):
    def setUp(self):
        self.state = {"secret": "s3cret", "fail_next": 0, "seen_keys": [], "credentials": {}, "log": []}
        contract = {"id": "c-1", "site_id": "site-x"}
        self.event = integration.new_event(1, "access.grant", contract, {"id": "r-1"}, "A101", date(2026, 11, 16))
        self.at = datetime(2026, 11, 16, 9, tzinfo=site_api.KST)

    def test_signature_is_checked(self):
        code, _ = integration.send(self.event, self.state, self.at, secret="wrong")
        self.assertEqual(code, 401)
        self.assertEqual(self.state["credentials"], {})
        body = integration.canonical(self.event["payload"])
        self.assertTrue(integration.verify("s3cret", "1", body, integration.sign("s3cret", "1", body)))
        self.assertFalse(integration.verify("s3cret", "2", body, integration.sign("s3cret", "1", body)))

    def test_retry_then_dead_letter(self):
        self.state["fail_next"] = 4
        for expected in ("retrying", "retrying", "retrying", "dead"):
            integration.deliver(self.event, self.state, self.at)
            self.assertEqual(self.event["status"], expected)
        self.assertEqual(len(self.event["attempts"]), integration.MAX_ATTEMPTS)
        self.assertEqual(self.state["credentials"], {})

    def test_retry_succeeds_and_duplicate_is_ignored(self):
        self.state["fail_next"] = 1
        integration.deliver(self.event, self.state, self.at)
        self.assertEqual(self.event["next_attempt_at"], "2026-11-16T09:01:00+09:00")
        integration.deliver(self.event, self.state, self.at)
        self.assertEqual(self.event["status"], "delivered")
        self.assertEqual(self.state["credentials"]["r-1"]["status"], "active")
        self.state["credentials"]["r-1"]["status"] = "probe"
        code, message = integration.send(self.event, self.state, self.at)
        self.assertEqual(code, 200)
        self.assertIn("중복", message)
        self.assertEqual(self.state["credentials"]["r-1"]["status"], "probe")


class LedgerRuleTests(unittest.TestCase):
    def test_journal_balances_and_skips_other_months(self):
        invoices = [
            {"id": "inv-1", "resident_id": "r-1", "month": "2026-11", "total": 3_440_000,
             "lines": [{"code": "monthly_fee", "amount": 3_200_000}, {"code": "meal", "amount": 240_000}]},
            {"id": "inv-0", "resident_id": "r-1", "month": "2026-10", "total": 100,
             "lines": [{"code": "monthly_fee", "amount": 100}]},
        ]
        payments = [{"id": "p-1", "invoice_id": "inv-1", "amount": 1_000_000, "paid_on": "2026-11-20"},
                    {"id": "p-2", "invoice_id": "inv-1", "amount": 5, "paid_on": "2026-12-02"}]
        rows = ledger.journal("2026-11", invoices, payments, {"r-1": "김순자"})
        self.assertEqual(len(rows), 5)
        self.assertEqual(ledger.totals(rows), {"debit": 4_440_000, "credit": 4_440_000, "balanced": True})
        self.assertEqual(rows[0]["date"], "2026-11-30")
        self.assertEqual({r["account"] for r in rows[:3]}, {"매출채권", "이용료수익", "서비스수익"})
        text = ledger.to_csv(rows)
        self.assertTrue(text.startswith("\ufeff전표일자,"))
        self.assertIn("김순자", text)


class PmsStage3ApiTests(PmsApiTests):
    """민원·연동·회계 마감. 날짜는 2026-11-16 로 고정한다."""

    def setUp(self):
        today = mock.patch.object(pms_router, "_today", return_value=date(2026, 11, 16))
        now = mock.patch.object(pms_router, "_now", return_value=datetime(2026, 11, 16, 13, 0, tzinfo=site_api.KST))
        today.start(), now.start()
        self.addCleanup(mock.patch.stopall)
        env = mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
        env.start()
        super().setUp()

    def vocs(self, user, site="site-garam"):
        return self.call("GET", f"/sites/{site}/vocs", user)

    # ---------- 민원 ----------

    def test_voc_scope_by_role(self):
        mgr = self.vocs("u-mgr-garam").json()
        self.assertEqual([v["category"] for v in mgr], ["facility", "care", "billing"])  # 긴급 먼저, 같은 긴급도는 최신 먼저
        self.assertEqual([v["category"] for v in self.vocs("u-care-garam").json()], ["care"])
        self.assertEqual([v["category"] for v in self.vocs("u-acct").json()], ["billing"])
        self.assertEqual([v["resident_id"] for v in self.vocs("u-guardian").json()], ["r-101"])
        self.assertEqual(self.vocs("u-mgr-nuri").status_code, 404)
        self.assertEqual([v["category"] for v in self.vocs("u-mgr-nuri", "site-nuri").json()], ["noise"])
        self.assertEqual([v["category"] for v in self.vocs("u-hq").json()], ["facility", "care", "billing"])

    def test_voc_rule_fallback_routes_and_masks(self):
        created = self.call("POST", "/residents/r-101/vocs", "u-mgr-garam",
                            json={"text": "어머니 방에 약 복용 확인이 빠졌어요. 연락은 010-9123-4402 로 주세요."})
        self.assertEqual(created.status_code, 200, created.text)
        item = created.json()
        self.assertEqual((item["source"], item["category"], item["assignee_role"]), ("rule", "care", "care_staff"))
        self.assertIn("010-9123-4402", item["text"])  # 매니저는 연락처 원문 권한이 있다
        care = next(v for v in self.vocs("u-care-garam").json() if v["id"] == item["id"])
        self.assertNotIn("4402", care["text"])  # 케어 직원은 가린 문장
        self.assertTrue(care["masked"])

    def test_voc_ai_gets_redacted_text_and_bad_answer_falls_back(self):
        seen = []

        def fake(text):
            seen.append(text)
            return {"category": "facility", "urgency": "high", "summary": "A101 보일러 고장", "reason": "난방 불가"}

        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), mock.patch.object(voc_ai, "classify", fake):
            item = self.call("POST", "/residents/r-101/vocs", "u-guardian",
                             json={"text": "김순자 어머니 방 보일러가 안 돼요. 박지훈 010-9123-4402"}).json()
        self.assertEqual((item["source"], item["summary"], item["assignee_role"]), ("ai", "A101 보일러 고장", "site_manager"))
        self.assertNotIn("김순자", seen[0])
        self.assertNotIn("4402", seen[0])
        self.assertIn("김순자", item["text"])  # 보호자는 자기 민원 원문을 본다
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
                mock.patch.object(voc_ai, "classify", return_value={"category": "x"}):
            bad = self.call("POST", "/residents/r-101/vocs", "u-guardian", json={"text": "보일러가 안 돼요"}).json()
        self.assertEqual(bad["source"], "rule")

    def test_voc_ai_cap_per_sandbox(self):
        data = pms_router.SANDBOXES[self.token]["data"]
        data["voc_ai_calls"] = pms_router.AI_PER_SANDBOX
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
                mock.patch.object(voc_ai, "classify", side_effect=AssertionError("호출하면 안 됨")):
            item = self.call("POST", "/residents/r-101/vocs", "u-guardian", json={"text": "보일러가 안 돼요"}).json()
        self.assertEqual(item["source"], "rule")

    def test_voc_write_scope_and_status_flow(self):
        self.assertEqual(self.call("POST", "/residents/r-102/vocs", "u-guardian", json={"text": "소음"}).status_code, 404)
        self.assertEqual(self.call("POST", "/residents/r-101/vocs", "u-acct", json={"text": "소음"}).status_code, 403)
        self.assertEqual(self.call("POST", "/residents/r-301/vocs", "u-mgr-garam", json={"text": "소음"}).status_code, 409)
        self.assertEqual(self.call("POST", "/vocs/voc-1/status", "u-guardian", json={"to": "in_progress"}).status_code, 403)
        self.assertEqual(self.call("POST", "/vocs/voc-1/status", "u-care-garam", json={"to": "in_progress"}).status_code, 404)
        self.assertEqual(self.call("POST", "/vocs/voc-1/status", "u-mgr-garam", json={"to": "done"}).status_code, 409)
        moved = self.call("POST", "/vocs/voc-1/status", "u-mgr-garam", json={"to": "in_progress"}).json()
        self.assertEqual(moved["status_label"], "처리 중")
        self.assertEqual([(n["to"], n["reason"]) for n in moved["next"]], [("done", False), ("received", True)])
        self.assertEqual(self.vocs("u-guardian").json()[0]["next"], [])

    def test_voc_reopen_needs_reason_and_keeps_history(self):
        path = "/vocs/voc-1/status"
        self.call("POST", path, "u-mgr-garam", json={"to": "in_progress"})
        done = self.call("POST", path, "u-mgr-garam", json={"to": "done"}).json()
        self.assertEqual([(n["to"], n["label"]) for n in done["next"]], [("in_progress", "다시 열기")])
        no_reason = self.call("POST", path, "u-mgr-garam", json={"to": "in_progress", "reason": "  "})
        self.assertEqual(no_reason.status_code, 409)
        self.assertIn("사유", no_reason.json()["detail"])
        reopened = self.call("POST", path, "u-mgr-garam", json={"to": "in_progress", "reason": "같은 곳 재누수"}).json()
        self.assertEqual((reopened["status"], reopened["reopened"]), ("in_progress", 1))
        self.assertEqual([h["action"] for h in reopened["history"]], ["접수", "처리 시작", "완료", "다시 열기"])
        last = reopened["history"][-1]
        self.assertEqual((last["by"], last["reason"], last["from_label"], last["to_label"]), ("윤매니저", "같은 곳 재누수", "완료", "처리 중"))
        self.assertEqual(last["at"], "2026-11-16T13:00:00+09:00")
        back = self.call("POST", path, "u-mgr-garam", json={"to": "received", "reason": "담당 잘못 지정"}).json()
        self.assertEqual((back["status"], back["reopened"]), ("received", 1))
        self.assertEqual(self.call("POST", path, "u-mgr-garam", json={"to": "in_progress", "reason": "x" * 201}).status_code, 422)

    # ---------- 출입 연동 ----------

    def integration(self, user="u-mgr-garam"):
        return self.call("GET", "/sites/site-garam/integration", user)

    def test_contract_changes_send_access_events(self):
        self.assertEqual(self.integration("u-care-garam").status_code, 403)
        terminated = self.call("POST", "/contracts/c-101/transition", "u-mgr-garam", json={"to": "terminated", "date": "2026-11-16"})
        self.assertEqual(terminated.status_code, 200)
        view = self.integration().json()
        revoke = view["events"][0]
        self.assertEqual((revoke["kind"], revoke["status"], revoke["idempotency_key"]),
                         ("access.revoke", "delivered", "access.revoke:c-101"))
        cards = {c["resident_id"]: c["status"] for c in view["credentials"]}
        self.assertEqual(cards["r-101"], "revoked")
        self.assertEqual(cards["r-102"], "active")
        self.call("POST", "/contracts/c-301/transition", "u-mgr-garam", json={"to": "signed"})
        self.call("POST", "/contracts/c-301/transition", "u-mgr-garam", json={"to": "active"})
        grant = self.integration().json()["events"][0]
        self.assertEqual((grant["kind"], grant["status"], grant["scheduled_for"]), ("access.grant", "scheduled", "2026-12-01"))

    def test_failure_retry_and_scheduled_revoke(self):
        self.call("POST", "/integration/fail-next", "u-mgr-garam", json={"count": 1})
        self.call("POST", "/contracts/c-102/transition", "u-mgr-garam", json={"to": "terminated", "date": "2026-11-16"})
        event = self.integration().json()["events"][0]
        self.assertEqual((event["status"], event["attempts"][0]["code"]), ("retrying", 503))
        sent = self.call("POST", "/sites/site-garam/integration/process", "u-mgr-garam", json={}).json()["sent"]
        self.assertEqual(sent, [{"id": event["id"], "status": "delivered"}])
        # 최봉길(c-202) 회수는 퇴거일(11-20)에 예약돼 있다
        early = self.call("POST", "/sites/site-garam/integration/process", "u-mgr-garam", json={"as_of": "2026-11-19"}).json()
        self.assertEqual(early["sent"], [])
        on_day = self.call("POST", "/sites/site-garam/integration/process", "u-mgr-garam", json={"as_of": "2026-11-20"}).json()
        self.assertEqual(len(on_day["sent"]), 1)
        cards = {c["resident_id"]: c["status"] for c in self.integration().json()["credentials"]}
        self.assertEqual(cards["r-202"], "revoked")
        self.assertEqual(self.call("POST", "/integration/fail-next", "u-hq", json={"count": 1}).status_code, 403)

    def test_resend_is_ignored_as_duplicate(self):
        event = self.integration().json()["events"][-1]
        result = self.call("POST", f"/integration/events/{event['id']}/resend", "u-mgr-garam").json()
        self.assertEqual(result["code"], 200)
        self.assertIn("중복", result["message"])
        self.assertEqual(self.call("POST", "/integration/events/evt-0001/resend", "u-mgr-nuri").status_code, 404)

    # ---------- 회계 마감 ----------

    def test_ledger_export_and_close_locks_month(self):
        self.run_november()
        self.call("POST", "/invoices/inv-c-101-2026-11/payments", "u-acct",
                  json={"amount": 1_000_000, "paid_on": "2026-11-16", "as_of": "2026-11-16"})
        self.assertEqual(self.call("GET", "/sites/site-garam/ledger?month=2026-11", "u-mgr-garam").status_code, 403)
        view = self.call("GET", "/sites/site-garam/ledger?month=2026-11", "u-hq").json()
        self.assertTrue(view["totals"]["balanced"])
        self.assertEqual(view["totals"]["debit"], 11_542_000 + 1_000_000)
        csv_res = self.call("GET", "/sites/site-garam/ledger.csv?month=2026-11", "u-acct")
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res.headers["content-type"])
        self.assertTrue(csv_res.content.startswith("\ufeff".encode()))
        self.assertEqual(self.call("POST", "/sites/site-garam/ledger/close", "u-acct", json={"month": "2026-10"}).status_code, 409)
        closed = self.call("POST", "/sites/site-garam/ledger/close", "u-acct", json={"month": "2026-11"})
        self.assertEqual(closed.json()["closed"]["by"], "문회계")
        self.assertEqual(self.call("POST", "/sites/site-garam/ledger/close", "u-acct", json={"month": "2026-11"}).status_code, 409)
        self.assertEqual(self.run_november().status_code, 409)
        late_pay = self.call("POST", "/invoices/inv-c-102-2026-11/payments", "u-acct",
                             json={"amount": 10, "paid_on": "2026-11-30", "as_of": "2026-11-30"})
        self.assertEqual(late_pay.status_code, 409)
        ok_pay = self.call("POST", "/invoices/inv-c-102-2026-11/payments", "u-acct",
                           json={"amount": 10, "paid_on": "2026-12-01", "as_of": "2026-12-01"})
        self.assertEqual(ok_pay.status_code, 200)
        usage = self.call("POST", "/residents/r-101/usages", "u-care-garam", json={"service": "meal", "quantity": 1, "date": "2026-11-20"})
        self.assertEqual(usage.status_code, 409)


class DeployPackagingTests(unittest.TestCase):
    def test_dockerfile_copies_every_backend_package(self):
        backend = Path(__file__).resolve().parents[1]
        dockerfile = (backend / "Dockerfile").read_text(encoding="utf-8")
        for package in sorted(p.parent.name for p in backend.glob("*/__init__.py")):
            if package == "tests":
                continue
            self.assertIn(f"backend/{package}/", dockerfile, f"Dockerfile 에 backend/{package}/ 복사가 없습니다")


if __name__ == "__main__":
    unittest.main()
