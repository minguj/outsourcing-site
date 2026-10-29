"""End-to-end API/XLSX checks. Expected fixture data is imported only here."""
from copy import deepcopy
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fastapi.testclient import TestClient
from backend import demo_api as api
from backend.main import app
from backend import purchase_orders as domain
from backend.order_xlsx import read_sheets

BASE = "/api/demo/purchase-orders"
EXPECTED = Path(__file__).resolve().parents[2] / "dev/purchase_order_samples/expected"


class DemoTests(unittest.TestCase):
    def setUp(self):
        api.SESSIONS.clear()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def start(self, samples=None, client=None):
        response = (client or self.client).post(BASE + "/start", json={"samples": samples or ["A", "B", "C"]}, headers={"X-Demo-Client": "purchase-orders"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def edit(self, state, sample, row, action, client=None, expected_status=200):
        response = (client or self.client).post(f"{BASE}/{sample}/rows/{row}", json={"revision": state["revision"], **action}, headers={"X-Demo-CSRF": state["csrf"]})
        self.assertEqual(response.status_code, expected_status, response.text)
        return response.json()

    def test_initial_parse_matches_new_expected_and_health_survives(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        state = self.start()
        self.assertEqual(state["summary"], {"source_rows": 39, "accepted": 29, "review": 7, "canceled": 3})
        fields = {"price": "unit_price", "amount": "stated_amount", "order_status": "status"}
        for order in state["orders"]:
            expected = json.loads((EXPECTED / f"{order['sample']}.expected.json").read_text(encoding="utf-8"))
            self.assertEqual(order["review"], expected["summary"]["review_rows"])
            self.assertEqual(Decimal(order["totals"]["total"]), Decimal(expected["summary"]["total_amount"]))
            for actual, wanted in zip(order["rows"], expected["rows"]):
                self.assertEqual(actual["id"], wanted["source"]["row"])
                self.assertEqual([i["code"] for i in actual["issues"]], wanted["issue_codes"])
                self.assertEqual(actual["source"]["file"], wanted["source"]["file"])
                for key, address in wanted["source"]["cells"].items():
                    inverse = {value: key for key, value in fields.items()}
                    self.assertEqual(actual["source"]["cells"].get(inverse.get(key, key)), address)
            for actual, wanted in zip(order["lines"], expected["accepted_output_lines"]):
                self.assertEqual(actual["item_code"], wanted["item_code"])
                self.assertEqual(Decimal(actual["quantity"]), Decimal(str(wanted["quantity"])))
                self.assertEqual(Decimal(actual["supply"]), Decimal(wanted["supply_amount"]))
                self.assertEqual([s["row"] for s in actual["sources"]], [s["row"] for s in wanted["sources"]])
                self.assertTrue(all(s["cells"] for s in actual["sources"]))

    def test_unresolved_download_is_blocked_for_each_customer(self):
        state = self.start()
        for sample in "ABC":
            response = self.client.get(f"{BASE}/{sample}/download?revision={state['revision']}")
            self.assertEqual(response.status_code, 409)

    def test_quantity_resolution_amount_confirmation_and_actual_download(self):
        state = self.start(["A"])
        state = self.edit(state, "A", 15, {"action": "resolve", "quantity": "5"})
        self.assertEqual(state["orders"][0]["review"], 1)
        self.edit(state, "A", 19, {"action": "resolve", "confirmed_amount": "13000"}, expected_status=422)
        state = self.edit(state, "A", 19, {"action": "resolve", "confirmed_amount": "13500"})
        self.assertTrue(state["orders"][0]["ready"])
        response = self.client.get(f"{BASE}/A/download?revision={state['revision']}")
        self.assertEqual(response.status_code, 200)
        sheets = read_sheets(BytesIO(response.content))
        self.assertEqual(sheets["거래명세서"]["cells"]["G31"], Decimal("144900"))
        self.assertEqual(sheets["거래명세서"]["cells"]["I31"], Decimal("159390"))
        self.assertEqual(sheets["납기별내역"]["cells"]["J5"], "2026-11-05")
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertIn(b"<", archive.read("xl/worksheets/sheet1.xml"))
            self.assertIn("13500", archive.read("xl/worksheets/sheet2.xml").decode())

    def test_b_explicit_ambiguous_selection_exclusion_and_full_trace(self):
        state = self.start(["B"])
        row = next(r for r in state["orders"][0]["rows"] if r["id"] == 9)
        self.assertEqual(row["candidates"], ["S003", "S004"])
        state = self.edit(state, "B", 9, {"action": "resolve", "item_code": "S004"})
        row = next(r for r in state["orders"][0]["rows"] if r["id"] == 9)
        self.assertEqual(row["supply"], "8500")
        self.assertEqual([i["code"] for i in row["issues"]], ["AMOUNT_MISMATCH"])
        state = self.edit(state, "B", 9, {"action": "resolve", "confirmed_amount": "8500"})
        self.edit(state, "B", 13, {"action": "exclude", "reason": " "}, expected_status=422)
        state = self.edit(state, "B", 13, {"action": "exclude", "reason": "거래처 확인 전 미등록 품목 제외"})
        self.edit(state, "B", 5, {"action": "reset"}, expected_status=422)
        response = self.client.get(f"{BASE}/B/download?revision={state['revision']}")
        self.assertEqual(response.status_code, 200)
        sheets = read_sheets(BytesIO(response.content))
        tracking = sheets["원본추적"]["cells"]
        self.assertEqual([int(tracking[f"D{r}"]) for r in range(5, 23)], list(range(2, 20)))
        self.assertIn("거래처 확인 전", tracking["G16"])
        self.assertEqual(tracking["E8"], "취소 제외")

    def test_customer_ready_is_independent_and_unknown_selection_uses_master(self):
        state = self.start()
        state = self.edit(state, "B", 13, {"action": "resolve", "item_code": "S010"})
        row = next(r for r in state["orders"][1]["rows"] if r["id"] == 13)
        self.assertEqual((row["name"], row["price"], row["supply"]), ("포장테이프 48mm", "1200", "2400"))
        state = self.edit(state, "B", 13, {"action": "resolve", "confirmed_amount": "2400"})
        state = self.edit(state, "B", 9, {"action": "resolve", "item_code": "S003"})
        self.assertEqual(self.client.get(f"{BASE}/B/download?revision={state['revision']}").status_code, 200)
        self.assertEqual(self.client.get(f"{BASE}/A/download?revision={state['revision']}").status_code, 409)

    def test_unknown_item_can_be_registered_for_this_session_only(self):
        state = self.start(["B"])
        register = {"action": "register", "new_code": "p-900", "new_name": "정전기제거패드", "new_unit": "개", "new_price": "6,900"}
        for bad in ({"new_name": "A"}, {"new_unit": ""}, {"new_price": "0"}, {"new_price": "abc"}, {"new_name": "알코올솜 100매"},
                    {"new_code": "S001"}, {"new_code": "코드"}, {"new_code": "A"}, {"new_code": "TOO-LONG-CODE"}):
            self.edit(state, "B", 13, {**register, **bad}, expected_status=422)
        self.edit(state, "B", 2, register, expected_status=422)
        state = self.edit(state, "B", 13, register)
        row = next(r for r in state["orders"][0]["rows"] if r["id"] == 13)
        self.assertEqual((row["item_code"], row["name"], row["unit"], row["price"], row["supply"], row["status"]),
                         ("P-900", "정전기제거패드", "개", "6900", "13800", "accepted"))
        self.assertTrue(row["item_registered"])
        self.assertEqual(row["audit"][-1]["action"], "register")
        self.assertIn("P-900", [m["code"] for m in state["master"] if m["registered"]])
        # Blank code registers as 미정; a different price needs the usual amount confirmation.
        state = self.edit(state, "B", 13, {"action": "reset"})
        state = self.edit(state, "B", 13, {**register, "new_code": " ", "new_name": "정전기제거패드 대형", "new_price": "7000"})
        row = next(r for r in state["orders"][0]["rows"] if r["id"] == 13)
        self.assertEqual((row["item_code"], row["supply"]), ("미정-1", "14000"))
        self.assertTrue(next(m for m in state["master"] if m["code"] == "미정-1")["pending"])
        self.assertEqual([i["code"] for i in row["issues"]], ["AMOUNT_MISMATCH"])
        state = self.edit(state, "B", 13, {"action": "resolve", "confirmed_amount": "14000"})
        state = self.edit(state, "B", 9, {"action": "resolve", "item_code": "S003"})
        response = self.client.get(f"{BASE}/B/download?revision={state['revision']}")
        self.assertEqual(response.status_code, 200)
        sheets = read_sheets(BytesIO(response.content))
        registered = sheets["신규등록품목"]["cells"]
        self.assertEqual((registered["A4"], registered["B4"], registered["D4"], registered["E4"]), ("미정 (코드 부여 필요)", "정전기제거패드 대형", Decimal("7000"), "13"))
        self.assertNotIn("A5", registered)
        codes = [sheets["거래명세서"]["cells"].get(f"B{r}") for r in range(10, 30)]
        self.assertIn("미정", codes)
        self.assertNotIn("미정-1", codes)
        # Another browser session still has only the shared CSV master.
        with TestClient(app) as other:
            fresh = self.start(["B"], other)
            self.assertFalse(any(m["registered"] for m in fresh["master"]))
        self.assertNotIn("P-900", domain.load_master())

    def test_canceled_orders_can_be_restored_and_reviewed_like_other_rows(self):
        state = self.start(["B"])
        rows = lambda st: {r["id"]: r for r in st["orders"][0]["rows"]}
        self.edit(state, "B", 17, {"action": "resolve", "quantity": "3"}, expected_status=422)
        self.edit(state, "B", 2, {"action": "restore"}, expected_status=422)
        # 청소물티슈 is a known S009 alias: it joins the existing 물티슈 line immediately.
        state = self.edit(state, "B", 17, {"action": "restore"})
        row = rows(state)[17]
        self.assertEqual((row["status"], row["item_code"], row["restored"]), ("accepted", "S009", True))
        line = next(l for l in state["orders"][0]["lines"] if l["item_code"] == "S009")
        self.assertEqual((line["quantity"], [s["row"] for s in line["sources"]]), ("22", [2, 4, 8, 17]))
        self.assertEqual(state["orders"][0]["canceled"], 2)
        # 위생장갑 needs the explicit M/L choice; 가상 포장필름 goes through registration.
        state = self.edit(state, "B", 5, {"action": "restore"})
        self.assertEqual([i["code"] for i in rows(state)[5]["issues"]], ["AMBIGUOUS_ITEM"])
        state = self.edit(state, "B", 5, {"action": "resolve", "item_code": "S003"})
        state = self.edit(state, "B", 11, {"action": "restore"})
        self.assertEqual([i["code"] for i in rows(state)[11]["issues"]], ["UNKNOWN_ITEM"])
        state = self.edit(state, "B", 11, {"action": "register", "new_code": "P-100", "new_name": "포장필름", "new_unit": "개", "new_price": "9900"})
        self.assertEqual(rows(state)[11]["status"], "accepted")
        # Excluding a restored row keeps it restored; undoing edits steps back one level at a time.
        state = self.edit(state, "B", 17, {"action": "exclude", "reason": "중복 주문 확인"})
        self.assertEqual((rows(state)[17]["status"], rows(state)[17]["restored"]), ("excluded", True))
        state = self.edit(state, "B", 17, {"action": "reset"})
        self.assertEqual(rows(state)[17]["status"], "accepted")
        state = self.edit(state, "B", 17, {"action": "reset"})
        self.assertEqual(rows(state)[17]["status"], "canceled")
        state = self.edit(state, "B", 17, {"action": "restore"})
        state = self.edit(state, "B", 13, {"action": "exclude", "reason": "거래처 확인 전 제외"})
        state = self.edit(state, "B", 9, {"action": "resolve", "item_code": "S003"})
        self.assertTrue(state["orders"][0]["ready"], state["orders"][0]["review"])
        response = self.client.get(f"{BASE}/B/download?revision={state['revision']}")
        self.assertEqual(response.status_code, 200)
        sheets = read_sheets(BytesIO(response.content))
        tracking = sheets["원본추적"]["cells"]
        status_by_row = {int(tracking[f"D{r}"]): tracking[f"E{r}"] for r in range(5, 23)}
        self.assertEqual((status_by_row[5], status_by_row[11], status_by_row[17]), ("검수 완료 · 취소 철회",) * 3)
        main = sheets["거래명세서"]["cells"]
        self.assertIn(Decimal("22"), [main.get(f"E{r}") for r in range(10, 20)])
        self.assertIn("P-100", [main.get(f"B{r}") for r in range(10, 20)])

    def test_reviewed_statement_can_be_exported_in_each_customer_form(self):
        state = self.start(["A", "B"])
        self.assertEqual(self.client.get(f"{BASE}/A/download?revision={state['revision']}&layout=C").status_code, 409)
        state = self.edit(state, "A", 15, {"action": "resolve", "quantity": "5"})
        state = self.edit(state, "A", 19, {"action": "resolve", "confirmed_amount": "13500"})
        state = self.edit(state, "B", 9, {"action": "resolve", "item_code": "S003"})
        state = self.edit(state, "B", 13, {"action": "register", "new_code": "", "new_name": "정전기제거패드", "new_unit": "개", "new_price": "6900"})
        self.assertEqual(self.client.get(f"{BASE}/A/download?revision={state['revision']}&layout=X").status_code, 422)
        get = lambda sample, layout: read_sheets(BytesIO(self.client.get(f"{BASE}/{sample}/download?revision={state['revision']}&layout={layout}").content))
        # B in its own shop form: B's own item numbers/names, merged order numbers, one total row.
        sheets = get("B", "B")
        cells = sheets["orders_export"]["cells"]
        self.assertEqual([cells[f"D{r}"] for r in range(2, 9)][:2], ["SHOP-S009", "SHOP-S010"])
        self.assertEqual((cells["A2"], cells["E2"], cells["G2"], cells["C2"]), ("DEMO-SHOP-1001 외 2건", "청소물티슈", Decimal("12"), "납품확정"))
        self.assertEqual((cells["D7"], cells["E7"]), ("SHOP-UNLISTED-12", "가상 정전기제거패드"))
        self.assertEqual((cells["A9"], cells["I9"]), ("합계 (검수 완료)", Decimal("132300")))
        self.assertNotIn("A10", cells)
        self.assertEqual(sheets["orders_export"]["filter"], "A1:Q9")
        self.assertIn("DEMO-SHOP-1007", sheets["회신변환기록"]["cells"]["G4"])
        # A in C's manufacturing form: C's own numbers where C has ordered the item, standard name otherwise.
        sheets = get("A", "C")
        cells = sheets["구매발주서"]["cells"]
        self.assertEqual((cells["B14"], cells["C14"], cells["D14"]), ("RM-DEMO-010", "물티슈", "100매"))
        self.assertEqual((cells.get("B11"), cells["C11"], cells["J11"]), (None, "A4 복사용지 80g", "거래처 품번 미등록 · 표준품명 표기"))
        self.assertEqual((cells["A21"], cells["H21"], cells["H23"]), ("소계 (검수 완료 공급가액)", Decimal("144900"), Decimal("144900")))
        self.assertEqual((cells["A1"], cells["G4"], cells["E1"]), ("(가상)누리문구", "—", "납품 회신서"))
        self.assertNotIn("A11:J11", sheets["구매발주서"]["merges"])
        # B in A's print form: our codes (미정 for a code-less registered item), totals below the table.
        cells = get("B", "A")["인쇄발주서"]["cells"]
        self.assertEqual([cells[f"B{r}"] for r in range(12, 19)], ["S009", "S010", "S014", "S003", "S013", "미정", "S011"])
        self.assertEqual((cells.get("A19"), cells["H20"]), (None, Decimal("132300")))
        self.assertEqual(cells["A20"], "공급가액 합계 (검수 완료)")

    def test_sessions_csrf_and_revision_are_isolated(self):
        one = self.start(["A"])
        with TestClient(app) as other:
            two = self.start(["A"], other)
            self.assertNotEqual(one["csrf"], two["csrf"])
            changed = self.edit(one, "A", 15, {"action": "resolve", "quantity": "5"})
            self.assertEqual(other.get(BASE + "/session").json()["orders"][0]["review"], 2)
            self.edit(one, "A", 19, {"action": "exclude", "reason": "보류 처리"}, expected_status=409)
            response = other.post(f"{BASE}/A/rows/15", json={"revision": 0, "action": "reset"}, headers={"X-Demo-CSRF": changed["csrf"]})
            self.assertEqual(response.status_code, 403)

    def test_invalid_quantities_and_unsupported_samples(self):
        state = self.start(["A"])
        for value in ("NaN", "Infinity", "0", "-1", "1.0001", "1000001"):
            self.edit(state, "A", 15, {"action": "resolve", "quantity": value}, expected_status=422)
        self.assertEqual(self.client.post(BASE + "/start", json={"samples": ["../../secret"]}, headers={"X-Demo-Client": "purchase-orders"}).status_code, 422)

    def test_no_aggregation_across_price_unit_or_due(self):
        order = domain.parse_order("B")
        master = domain.load_master()
        self.assertEqual(len(domain.order_view(order, master)["lines"]), 6)
        for field, new in (("due", "2026-12-01"), ("price", Decimal("1900")), ("unit", "다른단위")):
            changed = deepcopy(order)
            row = changed["rows"][0]
            row["raw"][field] = new
            if field == "price":
                row["raw"]["amount"] = row["raw"]["quantity"] * new
            lines = domain.order_view(changed, master)["lines"]
            self.assertEqual(len(lines), 7, field)

    def test_c_layout_spec_dates_and_download(self):
        state = self.start(["C"])
        order = state["orders"][0]
        self.assertEqual([r["id"] for r in order["rows"]], [12,13,15,16,17,19,20,21,23,24,25])
        self.assertEqual({r["item_code"] for r in order["rows"] if r["id"] in (19,20)}, {"S003","S004"})
        self.assertEqual({line["due"] for line in order["lines"]}, {"2026-11-09", "2026-11-12"})
        for row in [15,21,24]:
            state = self.edit(state, "C", row, {"action": "exclude", "reason": "확인 전 발행 보류 품목"})
        response = self.client.get(f"{BASE}/C/download?revision={state['revision']}")
        sheets = read_sheets(BytesIO(response.content))
        self.assertEqual(sheets["거래명세서"]["cells"]["I31"], 138600)
        self.assertIn("비주문행기록", sheets)
        self.assertEqual({sheets["납기별내역"]["cells"][f"J{r}"] for r in range(5,13)}, {"2026-11-09", "2026-11-12"})

    def test_b_fractional_aggregation_preserves_source_rounding_in_excel(self):
        order = domain.parse_order("B")
        master = domain.load_master()
        for row in order["rows"]:
            if row["id"] in (2,4,8):
                domain.apply_review(row, master, {"action": "resolve", "quantity": "0.001", "confirmed_amount": "2"})
            elif row["id"] in (9,13):
                domain.apply_review(row, master, {"action": "exclude", "reason": "거래처 확인 전 제외"})
        view = domain.order_view(order, master)
        self.assertEqual(view["lines"][0]["quantity"], "0.003")
        self.assertEqual(view["lines"][0]["supply"], "6")
        content = domain.export_order(order, master)
        sheets = read_sheets(BytesIO(content))
        self.assertEqual(sheets["거래명세서"]["cells"]["G10"], 6)
        with ZipFile(BytesIO(content)) as archive:
            root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            formula = root.find("s:sheetData/s:row/s:c[@r='G10']/s:f", ns).text
            self.assertEqual(formula, "SUM(ROUND(0.001*1800,0),ROUND(0.001*1800,0),ROUND(0.001*1800,0))")

    def test_changed_quantity_invalidates_old_amount_confirmation(self):
        state = self.start(["A"])
        state = self.edit(state, "A", 19, {"action": "resolve", "confirmed_amount": "13500"})
        state = self.edit(state, "A", 19, {"action": "resolve", "quantity": "4"})
        row = next(r for r in state["orders"][0]["rows"] if r["id"] == 19)
        self.assertEqual([i["code"] for i in row["issues"]], ["AMOUNT_MISMATCH"])
        self.assertEqual(row["supply"], "18000")

    def test_c_unknown_spec_is_not_ignored_even_when_name_is_unique(self):
        order = domain.parse_order("C")
        order["rows"][0]["raw"]["spec"] = "마스터에 없는 규격"
        row = domain.order_view(order, domain.load_master())["rows"][0]
        self.assertIsNone(row["item_code"])
        self.assertEqual([i["code"] for i in row["issues"]], ["UNKNOWN_ITEM"])

    def test_amounts_are_read_from_actual_xlsx_not_filename_or_expected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            shutil.copytree(domain.DATA, folder, dirs_exist_ok=True)
            path = folder / "purchase_order_A.xlsx"
            buffer = BytesIO()
            with ZipFile(path) as source, ZipFile(buffer, "w") as target:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename == "xl/worksheets/sheet1.xml":
                        root = ET.fromstring(data)
                        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                        root.find("s:sheetData/s:row/s:c[@r='F12']/s:v", ns).text = "3"
                        root.find("s:sheetData/s:row/s:c[@r='H12']/s:v", ns).text = "75000"
                        data = ET.tostring(root)
                    target.writestr(info, data)
            path.write_bytes(buffer.getvalue())
            view = domain.order_view(domain.parse_order("A", folder), domain.load_master(folder))
            self.assertEqual(view["totals"]["supply"], "147400")
            self.assertEqual(view["lines"][0]["quantity"], "3")


if __name__ == "__main__":
    unittest.main()
