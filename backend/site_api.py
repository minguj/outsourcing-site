"""Public site API: AI 상담, 문의 접수·알림, 견적 확인·착수금 결제, 관리자."""
import base64
from collections import defaultdict, deque
import hmac
import os
import re
import secrets
from threading import RLock
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
import httpx
from pydantic import BaseModel, ConfigDict, Field

if __package__:
    from . import consult, notify, site_store as store
else:
    import consult
    import notify
    import site_store as store

router = APIRouter(prefix="/api")
LOCK = RLock()
HITS = defaultdict(deque)
DAILY = {"day": "", "count": 0}
ADMIN_SESSIONS = {}
ADMIN_COOKIE = "site_admin"
ADMIN_TTL = 12 * 3600
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")
TOSS_CONFIRM = "https://api.tosspayments.com/v1/payments/confirm"


def client_ip(request):
    # Only Caddy can reach the backend, and it sets X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def limit(request, bucket, count, window):
    key = (bucket, client_ip(request))
    now = time.monotonic()
    with LOCK:
        hits = HITS[key]
        while hits and hits[0] < now - window:
            hits.popleft()
        if len(hits) >= count:
            raise HTTPException(429, "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
        hits.append(now)


# ---------- AI 상담 ----------

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class Chat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


@router.post("/consult/chat")
def chat(body: Chat, request: Request):
    limit(request, "chat", 40, 3600)
    today = time.strftime("%Y-%m-%d")
    with LOCK:
        if DAILY["day"] != today:
            DAILY.update(day=today, count=0)
        if DAILY["count"] >= int(os.environ.get("CONSULT_DAILY_LIMIT") or 500):
            raise HTTPException(503, "오늘 AI 상담 이용량이 많아 잠시 쉬고 있어요. 아래 양식으로 문의를 남겨 주세요.")
        DAILY["count"] += 1
    try:
        return consult.reply([m.model_dump() for m in body.messages])
    except consult.ConsultError as error:
        raise HTTPException(error.status, str(error)) from None


@router.get("/site/config")
def site_config():
    return {"company": consult.company(), "consult_ready": bool(os.environ.get("ANTHROPIC_API_KEY"))}


# ---------- 문의 접수 ----------

class Inquiry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40)
    company: str = Field(default="", max_length=80)
    email: str = Field(max_length=254)
    phone: str = Field(default="", max_length=30)
    message: str = Field(default="", max_length=3000)
    brief: dict | None = None
    transcript: list[ChatMessage] = Field(default_factory=list, max_length=50)
    consent: bool
    website: str = Field(default="", max_length=200)  # honeypot: humans never fill this


def clean_brief(brief):
    if not brief:
        return {}
    keep = {}
    for key in ("project_type", "title", "summary", "current_process", "data_and_systems", "users_and_scale", "budget", "timeline"):
        if isinstance(brief.get(key), str):
            keep[key] = brief[key][:1500]
    for key in ("goals", "open_questions"):
        if isinstance(brief.get(key), list):
            keep[key] = [str(item)[:300] for item in brief[key][:10]]
    return keep


def brief_text(brief):
    labels = [("project_type", "유형"), ("title", "제목"), ("summary", "요약"), ("current_process", "현재 업무"),
              ("goals", "목표"), ("data_and_systems", "문서·데이터·시스템"), ("users_and_scale", "사용자·규모"),
              ("budget", "예산"), ("timeline", "일정"), ("open_questions", "추가 확인")]
    lines = []
    for key, label in labels:
        value = brief.get(key)
        if value:
            lines.append(f"- {label}: {', '.join(value) if isinstance(value, list) else value}")
    return "\n".join(lines) or "- (AI 상담 요약 없음)"


@router.post("/inquiries")
def submit_inquiry(body: Inquiry, request: Request):
    if body.website:
        return {"ok": True}  # silently drop bots
    limit(request, "inquiry", 5, 3600)
    if not body.consent:
        raise HTTPException(422, "개인정보 수집·이용에 동의해 주세요.")
    email = body.email.strip()
    if not EMAIL.match(email):
        raise HTTPException(422, "이메일 주소를 확인해 주세요.")
    brief = clean_brief(body.brief)
    if not brief and len(body.message.strip()) < 5:
        raise HTTPException(422, "의뢰 내용을 조금만 더 적어 주세요.")
    transcript = [m.model_dump() for m in body.transcript]
    inquiry_id = store.create_inquiry(body.name.strip(), body.company.strip(), email, body.phone.strip(),
                                      body.message.strip(), brief, transcript)
    link = f"{notify.base_url()}/admin?inquiry={inquiry_id}" if notify.base_url() else f"/admin?inquiry={inquiry_id}"
    notify.send(f"[새 상담 접수 #{inquiry_id}] {brief.get('title') or body.company or body.name}",
                f"새 상담이 접수되었습니다.\n\n이름: {body.name}\n회사: {body.company or '-'}\n이메일: {email}\n"
                f"전화: {body.phone or '-'}\n\n[AI 상담 요약]\n{brief_text(brief)}\n\n[직접 남긴 내용]\n{body.message or '-'}\n\n"
                f"관리 화면: {link}\n")
    return {"ok": True, "id": inquiry_id}


# ---------- 견적 확인·착수금 결제 ----------

def public_quote(quote):
    return {"title": quote["title"], "items": quote["items"], "total": quote["total"], "deposit": quote["deposit"],
            "schedule": quote["schedule"], "note": quote["note"], "status": quote["status"],
            "created_at": quote["created_at"], "paid_at": quote["paid_at"],
            "customer": {"name": quote["customer"].get("name", ""), "company": quote["customer"].get("company", "")},
            "payment_ready": bool(os.environ.get("TOSS_CLIENT_KEY") and os.environ.get("TOSS_SECRET_KEY")),
            "payment_test": (os.environ.get("TOSS_CLIENT_KEY") or "").startswith("test_")}


def quote_or_404(token):
    quote = store.get_quote(token) if re.fullmatch(r"[A-Za-z0-9_-]{10,64}", token) else None
    if not quote:
        raise HTTPException(404, "견적서를 찾을 수 없습니다. 받은 링크를 다시 확인해 주세요.")
    return quote


@router.get("/quotes/{token}")
def view_quote(token: str):
    return public_quote(quote_or_404(token))


@router.post("/quotes/{token}/checkout")
def checkout(token: str, request: Request):
    limit(request, "checkout", 20, 3600)
    quote = quote_or_404(token)
    if quote["status"] == "paid":
        raise HTTPException(409, "이미 착수금 결제가 완료된 견적입니다.")
    client_key = os.environ.get("TOSS_CLIENT_KEY")
    if not client_key or not os.environ.get("TOSS_SECRET_KEY"):
        raise HTTPException(503, "온라인 결제를 준비 중입니다. 담당자에게 결제 방법을 문의해 주세요.")
    order_id = f"Q{quote['id']}-{secrets.token_hex(8)}"
    store.set_order(token, order_id)
    return {"client_key": client_key, "order_id": order_id, "amount": quote["deposit"],
            "order_name": f"{quote['title'][:60]} 착수금", "customer_name": quote["customer"].get("name", ""),
            "customer_email": quote["customer"].get("email", "")}


class Confirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_key: str = Field(min_length=1, max_length=200)
    order_id: str = Field(min_length=6, max_length=64)
    amount: int = Field(gt=0)


def toss_confirm(payment_key, order_id, amount):
    """Call Toss Payments confirm. Separated so tests can replace it."""
    secret = os.environ["TOSS_SECRET_KEY"]
    auth = base64.b64encode(f"{secret}:".encode()).decode()
    try:
        response = httpx.post(TOSS_CONFIRM, json={"paymentKey": payment_key, "orderId": order_id, "amount": amount},
                              headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json",
                                       "Idempotency-Key": order_id}, timeout=30)
    except httpx.HTTPError:
        raise HTTPException(502, "결제 승인 서버에 연결하지 못했습니다. 잠시 후 새로고침해 주세요.") from None
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code != 200:
        raise HTTPException(402, data.get("message") or "결제 승인에 실패했습니다.")
    return data


@router.post("/quotes/{token}/confirm")
def confirm(token: str, body: Confirm, request: Request):
    limit(request, "confirm", 20, 3600)
    quote = quote_or_404(token)
    if quote["status"] == "paid":
        if quote["payment_key"] == body.payment_key:
            return public_quote(quote)
        raise HTTPException(409, "이미 착수금 결제가 완료된 견적입니다.")
    # The amount and order must match what this server issued; never trust the redirect alone.
    if not quote["order_id"] or not hmac.compare_digest(quote["order_id"], body.order_id) or body.amount != quote["deposit"]:
        raise HTTPException(400, "결제 정보가 견적과 일치하지 않습니다.")
    if not os.environ.get("TOSS_SECRET_KEY"):
        raise HTTPException(503, "온라인 결제를 준비 중입니다.")
    data = toss_confirm(body.payment_key, body.order_id, body.amount)
    store.mark_paid(token, body.payment_key, data.get("method") or "")
    notify.send(f"[착수금 결제 완료] {quote['title']} · {quote['deposit']:,}원",
                f"착수금 결제가 완료되었습니다.\n\n견적: {quote['title']}\n고객: {quote['customer'].get('name')} "
                f"({quote['customer'].get('company') or '-'})\n금액: {quote['deposit']:,}원\n결제수단: {data.get('method') or '-'}\n"
                f"주문번호: {body.order_id}\n")
    return public_quote(store.get_quote(token))


# ---------- 관리자 ----------

def require_admin(request):
    token = request.cookies.get(ADMIN_COOKIE)
    with LOCK:
        expires = ADMIN_SESSIONS.get(token)
        if not expires or expires < time.monotonic():
            raise HTTPException(401, "관리자 로그인이 필요합니다.")
    if request.method != "GET" and request.headers.get("X-Admin-Client") != "1":
        raise HTTPException(403, "관리 화면에서 요청해 주세요.")


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(max_length=200)


@router.post("/admin/login")
def admin_login(body: Login, request: Request, response: Response):
    limit(request, "admin-login", 10, 900)
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if len(password) < 8:
        raise HTTPException(503, "관리자 비밀번호(ADMIN_PASSWORD, 8자 이상)가 서버에 설정되지 않았습니다.")
    if request.headers.get("X-Admin-Client") != "1" or not hmac.compare_digest(body.password.encode(), password.encode()):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다.")
    token = secrets.token_urlsafe(32)
    with LOCK:
        now = time.monotonic()
        for key in [k for k, v in ADMIN_SESSIONS.items() if v < now]:
            del ADMIN_SESSIONS[key]
        ADMIN_SESSIONS[token] = now + ADMIN_TTL
    response.set_cookie(ADMIN_COOKIE, token, max_age=ADMIN_TTL, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https", path="/api")
    return {"ok": True}


@router.post("/admin/logout")
def admin_logout(request: Request, response: Response):
    with LOCK:
        ADMIN_SESSIONS.pop(request.cookies.get(ADMIN_COOKIE), None)
    response.delete_cookie(ADMIN_COOKIE, path="/api")
    return {"ok": True}


@router.get("/admin/inquiries")
def admin_inquiries(request: Request):
    require_admin(request)
    return {"inquiries": store.list_inquiries(), "smtp": notify.configured(),
            "consult": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "payments": bool(os.environ.get("TOSS_CLIENT_KEY") and os.environ.get("TOSS_SECRET_KEY"))}


@router.get("/admin/inquiries/{inquiry_id}")
def admin_inquiry(inquiry_id: int, request: Request):
    require_admin(request)
    inquiry = store.get_inquiry(inquiry_id)
    if not inquiry:
        raise HTTPException(404, "문의를 찾을 수 없습니다.")
    return inquiry


class InquiryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["new", "contacted", "quoted", "deposit_paid", "in_progress", "closed"] | None = None
    admin_note: str | None = Field(default=None, max_length=5000)


@router.post("/admin/inquiries/{inquiry_id}")
def admin_update(inquiry_id: int, body: InquiryUpdate, request: Request):
    require_admin(request)
    if not store.get_inquiry(inquiry_id):
        raise HTTPException(404, "문의를 찾을 수 없습니다.")
    store.update_inquiry(inquiry_id, body.status, body.admin_note)
    return store.get_inquiry(inquiry_id)


class QuoteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    amount: int = Field(ge=0, le=1_000_000_000)


class QuoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=120)
    items: list[QuoteItem] = Field(min_length=1, max_length=30)
    deposit: int = Field(gt=0, le=1_000_000_000)
    schedule: str = Field(default="", max_length=1000)
    note: str = Field(default="", max_length=3000)


@router.post("/admin/inquiries/{inquiry_id}/quotes")
def admin_quote(inquiry_id: int, body: QuoteCreate, request: Request):
    require_admin(request)
    if not store.get_inquiry(inquiry_id):
        raise HTTPException(404, "문의를 찾을 수 없습니다.")
    total = sum(item.amount for item in body.items)
    if body.deposit > total:
        raise HTTPException(422, "착수금은 견적 합계보다 클 수 없습니다.")
    token = store.create_quote(inquiry_id, body.title.strip(), [i.model_dump() for i in body.items], total,
                               body.deposit, body.schedule.strip(), body.note.strip())
    return {"token": token, "path": f"/quote?t={token}", "inquiry": store.get_inquiry(inquiry_id)}

