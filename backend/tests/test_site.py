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

    def test_bottom_form_can_carry_the_chat(self):
        # The page's bottom form sends the AI chat (and its summary when there is one) with the inquiry.
        chat = [{"role": "assistant", "content": "안녕하세요"}, {"role": "user", "content": "기간은 얼마나 걸리나요?"},
                {"role": "assistant", "content": "1~2주"}, {"role": "user", "content": "엑셀 변환 툴이 필요해요"}]
        inquiry_id = self.inquiry(brief=None, message="", transcript=chat).json().get("id")
        self.assertIsNone(inquiry_id)  # chat without a summary still needs a written request
        response = self.inquiry(brief=None, message="거래처 엑셀 변환 문의", transcript=chat)
        stored = site_store.get_inquiry(response.json()["id"])
        self.assertEqual(len(stored["transcript"]), 4)
        self.assertIn("고객 메시지 2개", self.sent[-1][1])
        with_brief = self.inquiry(message="", transcript=chat)
        self.assertEqual(site_store.get_inquiry(with_brief.json()["id"])["brief"]["title"], "발주서 변환")
        self.inquiry(transcript=[])
        self.assertIn("[AI 상담 대화]\n없음", self.sent[-1][1])

    def test_consult_is_product_demo_guide(self):
        prompt = consult.system_prompt()
        self.assertIn("데모 안내자", prompt)
        self.assertIn("/demo/purchase-orders", prompt)
        for word in ("외주", "유지보수", "포인트"):
            self.assertNotIn(word, prompt)
        project_type = consult.BRIEF_TOOL["input_schema"]["properties"]["project_type"]["description"]
        self.assertIn("우리 사이트에 맞춤 적용", project_type)

    def test_english_site_flow(self):
        fake = {"content": [{"type": "text", "text": "Got it."}]}
        with patch.object(consult, "call_claude", return_value=fake) as call:
            self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "hi"}], "lang": "en"})
        self.assertEqual(call.call_args.args[1], "en")
        self.assertIn("English site", consult.system_prompt("en"))
        self.assertIn("방문자가 대화에서 직접 말한 내용만", consult.system_prompt())
        self.assertNotIn("English site", consult.system_prompt())
        self.assertEqual(self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "hi"}], "lang": "fr"}).status_code, 422)
        inquiry_id = self.inquiry(lang="en", brief={"title": "PO converter", "summary": "Convert orders", "budget": "Undecided", "timeline": "Q1"}).json()["id"]
        to, subject, body = self.customer[-1]
        self.assertEqual(subject, "[FitAgent] We received your inquiry")
        self.assertIn("Title: PO converter", body)
        self.assertIn("[영문]", self.sent[-1][0])
        self.login()
        self.assertEqual(self.client.get("/api/admin/inquiries").json()["inquiries"][0]["lang"], "en")
        created = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json={
            "title": "PO converter", "items": [{"name": "Development", "amount": 5000000}], "deposit": 1500000}).json()
        self.assertIn("Deposit KRW 1,500,000", self.customer[-1][2])
        quote = self.client.get(f"/api/quotes/{created['token']}").json()
        self.assertEqual(quote["lang"], "en")
        self.assertEqual(quote["next_steps"][0]["title"], "Kickoff meeting")
        order = self.client.post(f"/api/quotes/{created['token']}/checkout").json()
        self.assertTrue(order["order_name"].endswith("deposit"))
        with patch.object(site_api, "toss_confirm", return_value={"method": "card"}):
            self.client.post(f"/api/quotes/{created['token']}/confirm", json={"payment_key": "pk", "order_id": order["order_id"], "amount": 1500000})
        self.assertIn("Deposit received", self.customer[-1][1])
        self.assertIn("[영문]", self.sent[-1][0])
        demo = self.client.get(self.client.post("/api/quotes/demo", json={"lang": "en"}).json()["path"].replace("/quote?t=", "/api/quotes/")).json()
        self.assertEqual((demo["lang"], demo["items"][0]["name"]), ("en", "Requirements and screen design"))
        self.assertIn("(sample quote)", demo["title"])

    def test_existing_database_gains_language_column(self):
        path = os.path.join(self.folder.name, "old.db")
        import sqlite3
        old = sqlite3.connect(path)
        old.executescript(site_store.SCHEMA.split("CREATE TABLE IF NOT EXISTS quotes")[0])
        old.execute("INSERT INTO inquiries (created_at, name, email) VALUES (1, 'a', 'a@example.com')")
        old.commit(); old.close()
        site_store.connect(path)
        self.assertEqual(site_store.get_inquiry(1)["lang"], "ko")

    def test_payment_and_admin_degrade_without_keys(self):
        inquiry_id = self.inquiry().json()["id"]
        self.login()
        token = self.client.post(f"/api/admin/inquiries/{inquiry_id}/quotes", headers=ADMIN, json={
            "title": "연동", "items": [{"name": "개발", "amount": 1000000}], "deposit": 300000}).json()["token"]
        with patch.dict(os.environ, {"TOSS_CLIENT_KEY": "", "TOSS_SECRET_KEY": "", "ADMIN_PASSWORD": ""}):
            self.assertFalse(self.client.get(f"/api/quotes/{token}").json()["payment_ready"])
            self.assertEqual(self.client.post(f"/api/quotes/{token}/checkout").status_code, 503)
            self.assertEqual(self.client.post("/api/admin/login", json={"password": "anything"}, headers=ADMIN).status_code, 503)

    def test_consult_sessions_are_kept_linked_and_admin_only(self):
        session = "s" * 20
        fake = {"content": [{"type": "text", "text": "어떤 업무인가요?"}]}
        brief = {"content": [{"type": "text", "text": "정리했어요."}, {"type": "tool_use", "name": "save_brief", "input": {"title": "발주서 변환", "evil": "x"}}]}
        with patch.object(consult, "call_claude", side_effect=[fake, brief, fake]):
            self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "발주서 자동화"}], "session": session})
            self.client.post("/api/consult/chat", json={"session": session, "messages": [
                {"role": "user", "content": "발주서 자동화"}, {"role": "assistant", "content": "어떤 업무인가요?"}, {"role": "user", "content": "거래처 3곳"}]})
            # 세션 번호 없이 온 대화는 남기지 않는다
            self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "익명"}]})
        self.assertEqual(self.client.post("/api/consult/chat", json={"messages": [{"role": "user", "content": "x"}], "session": "bad id!"}).status_code, 422)
        self.assertEqual(self.client.get("/api/admin/consults").status_code, 401)
        inquiry_id = self.inquiry(session=session).json()["id"]
        self.login()
        listing = self.client.get("/api/admin/consults").json()
        self.assertEqual(len(listing["consults"]), 1)
        row = listing["consults"][0]
        self.assertEqual((row["user_turns"], row["title"], row["inquiry_id"], row["first"]), (2, "발주서 변환", inquiry_id, "발주서 자동화"))
        self.assertEqual((listing["stats"]["total"], listing["stats"]["briefs"], listing["stats"]["submitted"]), (1, 1, 1))
        record = self.client.get(f"/api/admin/consults/{session}").json()
        self.assertEqual(len(record["messages"]), 4)
        self.assertNotIn("evil", record["brief"])
        self.assertEqual(len(self.client.get("/api/admin/consults?q=거래처").json()["consults"]), 1)
        self.assertEqual(len(self.client.get("/api/admin/consults?q=없는말").json()["consults"]), 0)
        # 보관 기간이 지나면 지워진다
        site_store.db().execute("UPDATE consult_sessions SET updated_at = 0"); site_store.db().commit()
        self.assertEqual(self.client.get("/api/admin/consults").json()["consults"], [])
        self.assertEqual(self.client.get(f"/api/admin/consults/{session}").status_code, 404)

    def test_admin_can_delete_a_consult(self):
        site_store.save_consult("d" * 20, "ko", [{"role": "user", "content": "지워 주세요"}], {})
        self.login()
        self.assertEqual(self.client.delete(f"/api/admin/consults/{'d' * 20}").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/admin/consults/{'d' * 20}", headers=ADMIN).status_code, 200)
        self.assertEqual(self.client.get(f"/api/admin/consults/{'d' * 20}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
