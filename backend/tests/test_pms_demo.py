"""운영 플랫폼(PMS) 데모: 청구 계산, 역할 × 사업장 권한, 계약 상태, 샌드박스 격리."""
import unittest
from datetime import date

from fastapi.testclient import TestClient

from backend import site_api
from backend.main import app
from backend.pms import billing, router as pms_router


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


if __name__ == "__main__":
    unittest.main()
