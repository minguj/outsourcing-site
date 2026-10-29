"""AI 상담 / 문의 접수 / 견적·결제 / 관리자 API checks. External services are mocked."""
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import consult, notify, site_api, site_store
from backend.main import app

ADMIN = {"X-Admin-Client": "1"}
ENV = {"ADMIN_PASSWORD": "test-admin-pass", "TOSS_CLIENT_KEY": "test_ck_x", "TOSS_SECRET_KEY": "test_sk_x",
       "ANTHROPIC_API_KEY": "sk-test", "SMTP_HOST": "", "NOTIFY_EMAIL": ""}


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        site_store.connect(os.path.join(self.folder.name, "site.db"))
        site_api.HITS.clear()
        site_api.ADMIN_SESSIONS.clear()
        site_api.DAILY.update(day="", count=0)
        env = patch.dict(os.environ, ENV)
        env.start()
        self.addCleanup(env.stop)
        self.sent = []
        mail = patch.object(notify, "send", side_effect=lambda subject, body: self.sent.append((subject, body)) or True)
        mail.start()
        self.addCleanup(mail.stop)
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
        self.assertTrue(any("착수금 결제 완료" in subject for subject, _ in self.sent))

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
