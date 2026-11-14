"""방문간호센터 샘플의 인증코드 메일 API checks. SMTP is mocked."""
import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import notify, nurse_demo, site_api
from backend.main import app


class NurseDemoTests(unittest.TestCase):
    def setUp(self):
        site_api.HITS.clear()
        nurse_demo.CODES.clear()
        nurse_demo.SENT.clear()
        nurse_demo.DAILY.update(day="", count=0)
        self.mails = []
        mail = patch.object(notify, "send_customer", side_effect=lambda to, subject, body: self.mails.append((to, subject, body)) or True)
        mail.start()
        self.addCleanup(mail.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def request(self, email="Owner@Example.com", purpose="email"):
        return self.client.post("/api/demo/nurse/code", json={"purpose": purpose, "email": email})

    def verify(self, code, email="owner@example.com", purpose="email"):
        return self.client.post("/api/demo/nurse/verify", json={"purpose": purpose, "email": email, "code": code})

    def code(self):
        return re.search(r"인증코드: (\d{6})", self.mails[-1][2]).group(1)

    def test_sends_fixed_mail_without_returning_code_and_verifies_once(self):
        response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("code", response.json())
        to, subject, body = self.mails[-1]
        self.assertEqual(to, "owner@example.com")
        self.assertIn("이메일 변경 인증코드", subject)
        self.assertIn("직접 요청하지 않으셨다면", body)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        code = self.code()
        self.assertEqual(self.verify(code, purpose="reset").status_code, 400)  # 용도가 다르면 다른 코드
        self.assertEqual(self.verify(code).json(), {"ok": True})
        self.assertEqual(self.verify(code).status_code, 400)  # 한 번 쓰면 끝

    def test_rejects_bad_or_fake_addresses_and_extra_fields(self):
        self.assertEqual(self.request("not-an-email").status_code, 400)
        self.assertEqual(self.request("admin@neulgyeot.example").status_code, 400)
        self.assertEqual(self.client.post("/api/demo/nurse/code", json={"purpose": "email", "email": "a@b.com", "body": "광고"}).status_code, 422)
        self.assertEqual(self.client.post("/api/demo/nurse/code", json={"purpose": "spam", "email": "a@b.com"}).status_code, 422)
        self.assertEqual(self.mails, [])

    def test_wrong_code_attempts_then_expiry(self):
        self.request()
        code = self.code()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(nurse_demo.MAX_TRIES - 1):
            self.assertEqual(self.verify(wrong).json()["detail"], "인증코드가 맞지 않습니다.")
        self.assertIn("여러 번 틀렸습니다", self.verify(wrong).json()["detail"])
        self.assertIn("요청 내역이 없습니다", self.verify(code).json()["detail"])
        self.request(email="late@example.com")
        nurse_demo.CODES[("email", "late@example.com")]["expires"] = 0
        self.assertIn("만료", self.verify(self.code(), email="late@example.com").json()["detail"])

    def test_limits_per_address_per_ip_and_per_day(self):
        for _ in range(nurse_demo.PER_EMAIL):
            self.assertEqual(self.request().status_code, 200)
        self.assertEqual(self.request().status_code, 429)
        self.assertEqual(self.request("second@example.com").status_code, 200)
        self.assertEqual(self.request("third@example.com").status_code, 429)  # IP당 1시간 5통
        site_api.HITS.clear()
        nurse_demo.DAILY["count"] = nurse_demo.DAILY_MAX
        self.assertEqual(self.request("fourth@example.com").status_code, 429)

    def test_reports_unconfigured_smtp(self):
        with patch.object(notify, "send_customer", return_value=False):
            response = self.request()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(nurse_demo.CODES, {})


if __name__ == "__main__":
    unittest.main()
