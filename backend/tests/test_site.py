"""AI 상담 / 문의 접수 / 견적·결제 / 관리자 API checks. External services are mocked."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pathlib import Path

from backend import consult, notify, site_api, site_store, uploads
from backend.main import app

ADMIN = {"X-Admin-Client": "1"}
ENV = {"ADMIN_PASSWORD": "test-admin-pass", "TOSS_CLIENT_KEY": "test_ck_x", "TOSS_SECRET_KEY": "test_sk_x",
       "ANTHROPIC_API_KEY": "sk-test", "SMTP_HOST": "", "NOTIFY_EMAIL": "", "PUBLIC_BASE_URL": "https://site.example",
       "PAYMENT_MOCK": "", "DATA_DIR": ""}


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        site_store.connect(os.path.join(self.folder.name, "site.db"))
        site_api.HITS.clear()
        site_api.ADMIN_SESSIONS.clear()
        site_api.DAILY.update(day="", count=0)
        env = patch.dict(os.environ, {**ENV, "DATA_DIR": self.folder.name})
        env.start()
        self.addCleanup(env.stop)
        self.sent = []
        mail = patch.object(notify, "send", side_effect=lambda subject, body, reply_to=None: self.sent.append((subject, body, reply_to)) or True)
        mail.start()
        self.addCleanup(mail.stop)
        self.customer = []
        customer = patch.object(notify, "send_customer", side_effect=lambda to, subject, body: self.customer.append((to, subject, body)) or True)
        customer.start()
        self.addCleanup(customer.stop)
        site_api.DEMO_QUOTES.clear()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def login(self):
        response = self.client.post("/api/admin/login", json={"password": "test-admin-pass"}, headers=ADMIN)
        self.assertEqual(response.status_code, 200, response.text)

    def inquiry(self, **extra):
        body = {"name": "홍길동", "company": "(가상)테스트상사", "email": "buyer@example.com", "consent": True,
                "brief": {"project_type": "문서 변환·자동화", "title": "발주서 변환", "summary": "거래처 발주서를 표준 양식으로",
                          "budget": "1천만원 내외", "timeline": "12월 오픈", "goals": ["수작업 절감"], "evil": "drop"},
                "transcript": [{"role": "user", "content": "발주서 변환이 필요해요"}]}
        body.update(extra)
        return self.client.post("/api/inquiries", json=body)

    def test_chat_returns_reply_and_brief_and_validates(self):
        fake = {"content": [{"type": "text", "text": "정리했어요."},
                            {"type": "tool_use", "name": "save_brief", "input": {"title": "상담봇", "budget": "미정"}}]}
        with patch.object(consult, "call_claude", return_value=fake) as call:
            response = self.client.post("/api/consult/chat", json={"messages": [
                {"role": "assistant", "content": "안녕하세요"}, {"role": "user", "content": "상담봇 만들고 싶어요"}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"reply": "정리했어요.", "brief": {"title": "상담봇", "budget": "미정"}})
        self.assertEqual(call.call_args.args[0], [{"role": "user", "content": "상담봇 만들고 싶어요"}])
        self.assertEqual(self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "x" * 1600}]}).status_code, 422)
        self.assertEqual(self.client.post("/api/consult/chat", json={"messages": [{"role": "system", "content": "hi"}]}).status_code, 422)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            response = self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(response.status_code, 503)

    def test_chat_is_rate_limited_per_ip(self):
        fake = {"content": [{"type": "text", "text": "네"}]}
        with patch.object(consult, "call_claude", return_value=fake):
            statuses = [self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "hi"}]},
                                         headers={"X-Forwarded-For": "203.0.113.9"}).status_code for _ in range(41)]
        self.assertEqual(statuses[:40], [200] * 40)
        self.assertEqual(statuses[40], 429)

    def test_inquiry_is_stored_cleaned_and_notified(self):
        self.assertEqual(self.inquiry(consent=False).status_code, 422)
        self.assertEqual(self.inquiry(email="not-an-email").status_code, 422)
        self.assertEqual(self.inquiry(brief=None, message="").status_code, 422)
        response = self.inquiry()
        self.assertEqual(response.status_code, 200, response.text)
        stored = site_store.get_inquiry(response.json()["id"])
        self.assertNotIn("evil", stored["brief"])
        self.assertEqual(stored["brief"]["goals"], ["수작업 절감"])
        self.assertEqual(len(self.sent), 1)
        self.assertIn("발주서 변환", self.sent[0][0])
        self.assertIn("1천만원 내외", self.sent[0][1])
        # Honeypot submissions look accepted but are never stored.
        self.assertEqual(self.inquiry(website="http://spam").json(), {"ok": True})
        self.assertEqual(len(site_store.list_inquiries()), 1)

    def test_admin_requires_login_and_creates_quote(self):
        inquiry_id = self.inquiry().json()["id"]
        self.assertEqual(self.client.get("/api/admin/inquiries").status_code, 401)
        self.assertEqual(self.client.post("/api/admin/login", json={"password": "wrong"}, headers=ADMIN).status_code, 401)
        self.assertEqual(self.client.post("/api/admin/login", json={"password": "test-admin-pass"}).status_code, 401)
        self.login()
        listing = self.client.get("/api/admin/inquiries").json()
        self.assertEqual(listing["inquiries"][0]["id"], inquiry_id)
        quote = {"title": "발주서 변환 툴", "items": [{"name": "변환 엔진", "amount": 6000000}, {"name": "검수 화면", "amount": 3000000}],
                 "deposit": 3000000, "schedule": "6주", "note": "VAT 별도"}
        self.assertEqual(self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", json=quote).status_code, 403)
        self.assertEqual(self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", json={**quote, "deposit": 99000000}, headers=ADMIN).status_code, 422)
        created = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", json=quote, headers=ADMIN).json()
        self.assertTrue(created["path"].startswith("/quote?t="))
        self.assertEqual(created["inquiry"]["status"], "quoted")
        public = self.client.get(f"/api/quotes/{created['token']}").json()
        self.assertEqual((public["total"], public["deposit"], public["payment_ready"]), (9000000, 3000000, True))
        self.assertNotIn("email", public["customer"])
        self.assertEqual(self.client.get("/api/quotes/not-a-real-token").status_code, 404)

    def test_deposit_payment_confirms_only_the_issued_order(self):
        inquiry_id = self.inquiry().json()["id"]
        self.login()
        token = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json={
            "title": "상담 에이전트", "items": [{"name": "개발", "amount": 5000000}], "deposit": 1500000}).json()["token"]
        order = self.client.post(f"/api/quotes/{token}/checkout").json()
        self.assertEqual((order["amount"], order["client_key"]), (1500000, "test_ck_x"))
        with patch.object(site_api, "toss_confirm", return_value={"method": "카드"}) as toss:
            self.assertEqual(self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": "pk", "order_id": order["order_id"], "amount": 1}).status_code, 400)
            self.assertEqual(self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": "pk", "order_id": "Q1-forged0", "amount": 1500000}).status_code, 400)
            paid = self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": "pk", "order_id": order["order_id"], "amount": 1500000})
            self.assertEqual(paid.status_code, 200, paid.text)
            self.assertEqual(paid.json()["status"], "paid")
            # Reloading the success page is idempotent; a different payment is refused.
            self.assertEqual(self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": "pk", "order_id": order["order_id"], "amount": 1500000}).status_code, 200)
            self.assertEqual(self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": "other", "order_id": order["order_id"], "amount": 1500000}).status_code, 409)
        toss.assert_called_once_with("pk", order["order_id"], 1500000)
        self.assertEqual(self.client.post(f"/api/quotes/{token}/checkout").status_code, 409)
        self.assertEqual(site_store.get_inquiry(inquiry_id)["status"], "deposit_paid")
        self.assertTrue(any("착수금 결제 완료" in sent[0] for sent in self.sent))

    def test_mock_payment_only_without_real_keys(self):
        inquiry_id = self.inquiry().json()["id"]
        self.login()
        token = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json={
            "title": "모의", "items": [{"name": "개발", "amount": 1000000}], "deposit": 300000}).json()["token"]
        with patch.dict(os.environ, {"TOSS_CLIENT_KEY": "", "TOSS_SECRET_KEY": "", "PAYMENT_MOCK": "1"}):
            self.assertEqual(self.client.get(f"/api/quotes/{token}").json()["payment_mode"], "mock")
            order = self.client.post(f"/api/quotes/{token}/checkout").json()
            self.assertTrue(order["mock"])
            self.assertEqual(self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": "mock_other", "order_id": order["order_id"], "amount": 300000}).status_code, 400)
            paid = self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": f"mock_{order['order_id']}", "order_id": order["order_id"], "amount": 300000})
            self.assertEqual(paid.json()["status"], "paid")
        self.assertEqual(site_store.get_quote(token)["payment_method"], "모의 결제")
        # With real keys present the mock switch is ignored.
        with patch.dict(os.environ, {"PAYMENT_MOCK": "1"}):
            self.assertEqual(self.client.get(f"/api/quotes/{token}").json()["payment_mode"], "toss")

    def test_customer_mails_receipt_quote_and_kickoff(self):
        inquiry_id = self.inquiry().json()["id"]
        self.assertEqual(self.customer[0][0], "buyer@example.com")
        self.assertIn("상담이 접수되었습니다", self.customer[0][1])
        self.assertIn("발주서 변환", self.customer[0][2])
        self.login()
        created = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json={
            "title": "변환 툴", "items": [{"name": "개발", "amount": 5000000}], "deposit": 1500000, "schedule": "6주"}).json()
        self.assertTrue(created["emailed"])
        to, subject, body = self.customer[-1]
        self.assertEqual(to, "buyer@example.com")
        self.assertIn(f"https://site.example/quote?t={created['token']}", body)
        self.assertIn("착수금 1,500,000원", body)
        order = self.client.post(f"/api/quotes/{created['token']}/checkout").json()
        with patch.object(site_api, "toss_confirm", return_value={"method": "카드"}):
            self.client.post(f"/api/quotes/{created['token']}/confirm", json={"payment_key": "pk", "order_id": order["order_id"], "amount": 1500000})
        to, subject, body = self.customer[-1]
        self.assertIn("착수금 결제 완료", subject)
        self.assertIn("착수 미팅 일정 조율", body)
        # The owner's payment notice carries the customer's contact details and replies go to the customer.
        subject, body, reply_to = self.sent[-1]
        self.assertIn(f"착수금 결제 완료 #{inquiry_id}", subject)
        for expected in ("이메일: buyer@example.com", "회사: (가상)테스트상사", "전화: -", "착수금: 1,500,000원", f"/admin?inquiry={inquiry_id}"):
            self.assertIn(expected, body)
        self.assertEqual(reply_to, "buyer@example.com")
        self.assertEqual(self.sent[0][2], "buyer@example.com")
        # Without a public site address the quote can still be created as a link only.
        with patch.dict(os.environ, {"PUBLIC_BASE_URL": ""}):
            quote = {"title": "링크만", "items": [{"name": "개발", "amount": 1000000}], "deposit": 300000}
            self.assertEqual(self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json=quote).status_code, 422)
            created = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json={**quote, "send_email": False}).json()
            self.assertFalse(created["emailed"])

    def multipart(self, files, **extra):
        payload = {"name": "홍길동", "email": "buyer@example.com", "consent": True, "message": "기획서 첨부합니다", **extra}
        return self.client.post("/api/inquiries", data={"payload": json.dumps(payload, ensure_ascii=False)}, files=files)

    def test_inquiry_attachments_are_stored_and_admin_only(self):
        files = [("files", ("회사 기획서 v2.pdf", b"%PDF-1.4 plan", "application/pdf")),
                 ("files", ("../../화면.png", b"\x89PNG data", "image/png"))]
        response = self.multipart(files)
        self.assertEqual(response.status_code, 200, response.text)
        inquiry_id = response.json()["id"]
        self.assertIn("회사 기획서 v2.pdf", self.sent[-1][1])
        self.assertIn("회사 기획서 v2.pdf", self.customer[-1][2])
        stored = site_store.get_inquiry(inquiry_id)["files"]
        self.assertEqual([f["original_name"] for f in stored], ["회사 기획서 v2.pdf", "화면.png"])
        # Stored inside DATA_DIR/uploads with server-generated names, never the client's path.
        on_disk = list(Path(self.folder.name, "uploads", str(inquiry_id)).iterdir())
        self.assertEqual(len(on_disk), 2)
        self.assertTrue(all(".." not in f.name and "기획서" not in f.name for f in on_disk))
        file_id = stored[0]["id"]
        self.assertEqual(self.client.get(f"/api/admin/files/{file_id}").status_code, 401)
        self.login()
        download = self.client.get(f"/api/admin/files/{file_id}")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"%PDF-1.4 plan")
        self.assertEqual(download.headers["content-type"], "application/octet-stream")
        self.assertTrue(download.headers["content-disposition"].startswith("attachment"))
        self.assertEqual(self.client.get("/api/admin/files/999").status_code, 404)
        self.assertEqual(self.client.get("/api/admin/inquiries").json()["inquiries"][0]["file_count"], 2)

    def test_inquiry_attachment_limits_roll_back(self):
        bad_type = self.multipart([("files", ("run.exe", b"MZ", "application/octet-stream"))])
        self.assertEqual(bad_type.status_code, 422)
        self.assertIn("올릴 수 없는 형식", bad_type.json()["detail"])
        too_many = self.multipart([("files", (f"{i}.pdf", b"x", "application/pdf")) for i in range(4)])
        self.assertEqual(too_many.status_code, 422)
        with patch.object(uploads, "MAX_FILE_BYTES", 10):
            too_big = self.multipart([("files", ("ok.pdf", b"x", "application/pdf")), ("files", ("big.pdf", b"x" * 11, "application/pdf"))])
        self.assertEqual(too_big.status_code, 422)
        self.assertIn("10MB", too_big.json()["detail"])
        # A failed upload leaves no inquiry and no files behind.
        self.assertEqual(site_store.list_inquiries(), [])
        self.assertEqual([f for f in Path(self.folder.name, "uploads").rglob("*") if f.is_file()], [])
        # Plain JSON submissions still work without attachments.
        self.assertEqual(self.inquiry().status_code, 200)

    def test_demo_quote_is_self_serve_and_never_charged(self):
        created = self.client.post("/api/quotes/demo", json={"title": "쇼핑몰 상담봇"})
        self.assertEqual(created.status_code, 200, created.text)
        token = created.json()["token"]
        quote = self.client.get(f"/api/quotes/{token}").json()
        self.assertTrue(quote["is_demo"] and quote["payment_test"])
        self.assertIn("쇼핑몰 상담봇 (체험용 견적)", quote["title"])
        self.assertEqual(quote["payment_mode"], "toss")  # test keys -> real Toss test window
        # Live keys are never used for demo quotes: they fall back to the mock flow.
        with patch.dict(os.environ, {"TOSS_CLIENT_KEY": "live_ck_x", "TOSS_SECRET_KEY": "live_sk_x"}):
            self.assertEqual(self.client.get(f"/api/quotes/{token}").json()["payment_mode"], "mock")
            order = self.client.post(f"/api/quotes/{token}/checkout").json()
            self.assertTrue(order["mock"])
            with patch.object(site_api, "toss_confirm") as toss:
                paid = self.client.post(f"/api/quotes/{token}/confirm", json={"payment_key": f"mock_{order['order_id']}", "order_id": order["order_id"], "amount": quote["deposit"]})
            toss.assert_not_called()
        self.assertEqual(paid.json()["status"], "paid")
        self.assertEqual(paid.json()["next_steps"][0]["title"], "착수 미팅 일정 조율")
        # Demo quotes never reach the database, the admin list or anyone's mailbox.
        self.assertEqual(site_store.list_inquiries(), [])
        self.assertEqual((self.sent, self.customer), ([], []))
        statuses = [self.client.post("/api/quotes/demo", json={}, headers={"X-Forwarded-For": "198.51.100.7"}).status_code for _ in range(11)]
        self.assertEqual(statuses[-1], 429)

    def test_payment_and_admin_degrade_without_keys(self):
        inquiry_id = self.inquiry().json()["id"]
        self.login()
        token = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json={
            "title": "연동", "items": [{"name": "개발", "amount": 1000000}], "deposit": 300000}).json()["token"]
        with patch.dict(os.environ, {"TOSS_CLIENT_KEY": "", "TOSS_SECRET_KEY": "", "ADMIN_PASSWORD": ""}):
            self.assertFalse(self.client.get(f"/api/quotes/{token}").json()["payment_ready"])
            self.assertEqual(self.client.post(f"/api/quotes/{token}/checkout").status_code, 503)
            self.assertEqual(self.client.post("/api/admin/login", json={"password": "anything"}, headers=ADMIN).status_code, 503)


if __name__ == "__main__":
    unittest.main()
