"""방문간호센터 홈페이지 샘플(/demo/nurse)의 관리자 인증코드 메일.

방문자가 입력한 주소로 실제 메일을 보내므로 스팸 통로가 되지 않게 막는다.
- 메일 본문은 고정 문구와 서버가 만든 숫자 코드뿐이다. 방문자가 쓴 글은 넣지 않는다.
- IP·받는 주소·하루 전체 발송 수를 제한한다.
- 코드는 해시로 메모리에만 10분 보관하고, 확인이 끝나거나 만료되면 지운다. DB에 남기지 않는다.
"""
from datetime import datetime
import hashlib
import hmac
import secrets
from threading import RLock
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

if __package__:
    from . import notify
    from .site_api import EMAIL, KST, limit
else:
    import notify
    from site_api import EMAIL, KST, limit

router = APIRouter(prefix="/api/demo/nurse")
LOCK = RLock()
SECRET = secrets.token_bytes(32)
CODES = {}  # (purpose, email) -> {"hash", "expires", "tries"}
SENT = {}  # email -> [monotonic times]
DAILY = {"day": "", "count": 0}
CODE_TTL = 10 * 60
MAX_TRIES = 5
PER_EMAIL = 3  # 같은 주소로 1시간에
DAILY_MAX = 200  # 데모 전체 하루 발송 수
MAX_ENTRIES = 2000
BLOCKED_TLDS = (".example", ".test", ".invalid", ".localhost", ".local")

Purpose = Literal["email", "reset"]
SUBJECTS = {"email": "관리자 이메일 변경 인증코드", "reset": "비밀번호 재설정 인증코드"}
ACTIONS = {"email": "관리자 이메일 변경", "reset": "관리자 비밀번호 재설정"}


class CodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Purpose
    email: str = Field(max_length=254)


class CodeCheck(CodeRequest):
    code: str = Field(pattern=r"^\d{6}$")


def _digest(purpose, email, code):
    return hmac.new(SECRET, f"{purpose}:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _clean_email(raw):
    email = raw.strip().lower()
    if not EMAIL.match(email):
        raise HTTPException(400, "이메일 형식을 확인해 주세요.")
    if email.endswith(BLOCKED_TLDS):
        raise HTTPException(400, "실제로 받을 수 있는 이메일 주소를 입력해 주세요.")
    return email


def _prune(now):
    for key in [k for k, v in CODES.items() if v["expires"] < now]:
        del CODES[key]
    for email in [e for e, times in SENT.items() if not times or times[-1] < now - 3600]:
        del SENT[email]


def mail_body(purpose, code):
    return (f"안녕하세요.\n\n"
            f"핏에이전트(fitagent.co.kr)의 방문간호센터 홈페이지 샘플에서 {ACTIONS[purpose]} 인증코드를 요청하셨습니다.\n\n"
            f"인증코드: {code}\n"
            f"10분 안에 샘플 화면에 입력해 주세요.\n\n"
            f"직접 요청하지 않으셨다면 이 메일은 무시하셔도 됩니다. 입력하신 주소는 사이트에 저장하지 않습니다.\n\n"
            f"이 메일은 데모 체험용으로 발송되었습니다. 늘곁방문간호센터는 샘플 속 가상의 센터입니다.\n"
            f"핏에이전트 https://fitagent.co.kr")


@router.post("/code")
def send_code(body: CodeRequest, request: Request):
    email = _clean_email(body.email)
    limit(request, "nurse-code", 5, 3600)
    now = time.monotonic()
    today = datetime.now(KST).date().isoformat()
    with LOCK:
        _prune(now)
        if DAILY["day"] != today:
            DAILY.update(day=today, count=0)
        if DAILY["count"] >= DAILY_MAX:
            raise HTTPException(429, "오늘 데모 메일 발송량을 모두 사용했습니다. 내일 다시 시도해 주세요.")
        times = [t for t in SENT.get(email, []) if t > now - 3600]
        if len(times) >= PER_EMAIL:
            raise HTTPException(429, "같은 주소로 너무 자주 요청했습니다. 잠시 후 다시 시도해 주세요.")
        if len(CODES) >= MAX_ENTRIES:
            raise HTTPException(429, "요청이 많습니다. 잠시 후 다시 시도해 주세요.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        if not notify.send_customer(email, f"[늘곁방문간호센터 샘플] {SUBJECTS[body.purpose]}", mail_body(body.purpose, code)):
            raise HTTPException(503, "메일 발송이 설정되어 있지 않습니다.")
        CODES[(body.purpose, email)] = {"hash": _digest(body.purpose, email, code), "expires": now + CODE_TTL, "tries": 0}
        SENT[email] = times + [now]
        DAILY["count"] += 1
    return {"sent": True, "ttl": CODE_TTL}


@router.post("/verify")
def verify_code(body: CodeCheck, request: Request):
    email = _clean_email(body.email)
    limit(request, "nurse-verify", 30, 3600)
    key = (body.purpose, email)
    with LOCK:
        entry = CODES.get(key)
        if not entry:
            raise HTTPException(400, "인증 요청 내역이 없습니다. 인증코드를 다시 받아 주세요.")
        if entry["expires"] < time.monotonic():
            del CODES[key]
            raise HTTPException(400, "인증코드가 만료되었습니다. 다시 받아 주세요.")
        if not hmac.compare_digest(entry["hash"], _digest(body.purpose, email, body.code)):
            entry["tries"] += 1
            if entry["tries"] >= MAX_TRIES:
                del CODES[key]
                raise HTTPException(400, "인증코드를 여러 번 틀렸습니다. 인증코드를 다시 받아 주세요.")
            raise HTTPException(400, "인증코드가 맞지 않습니다.")
        del CODES[key]
    return {"ok": True}
