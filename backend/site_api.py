"""Public site API: AI 상담, 문의 접수·알림, 견적 확인·착수금 결제, 관리자."""
import base64
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import hmac
import logging
import os
from pathlib import Path
import re
import secrets
from threading import RLock
import time
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.datastructures import UploadFile

if __package__:
    from . import consult, notify, site_store as store, uploads
    from .site_knowledge import QUOTE_STEP, kickoff_steps, kickoff_text
else:
    import consult
    import notify
    import site_store as store
    import uploads
    from site_knowledge import QUOTE_STEP, kickoff_steps, kickoff_text

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)
LOCK = RLock()
HITS = defaultdict(deque)
DAILY = {"day": "", "count": 0}
ADMIN_SESSIONS = {}
ADMIN_COOKIE = "site_admin"
ADMIN_TTL = 12 * 3600
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")
TOSS_CONFIRM = "https://api.tosspayments.com/v1/payments/confirm"
KST = timezone(timedelta(hours=9))  # slim images may lack tzdata
DEMO_QUOTES = {}
DEMO_TTL = 2 * 3600
DEMO_MAX = 500


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


Lang = Literal["ko", "en"]


SessionId = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,64}$")


class Chat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)
    lang: Lang = "ko"
    session: str | None = SessionId  # 상담창마다 브라우저가 만든 무작위 번호. 대화 기록을 묶는 데만 쓴다.


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
    messages = [m.model_dump() for m in body.messages]
    try:
        result = consult.reply(messages, body.lang)
    except consult.ConsultError as error:
        raise HTTPException(error.status, str(error)) from None
    if body.session:
        try:
            store.save_consult(body.session, body.lang, messages + [{"role": "assistant", "content": result["reply"]}], clean_brief(result.get("brief")))
        except Exception:  # 기록 저장 실패가 상담 응답을 막지 않게 한다
            log.exception("AI 상담 기록 저장 실패")
    return result


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
    overseas_consent: bool = False  # 예전 화면 호환용. 국외 처리위탁은 안내(처리방침)로 알리고 별도 동의는 받지 않는다.
    lang: Lang = "ko"
    session: str | None = SessionId
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


BRIEF_LABELS = {
    "ko": [("project_type", "도입 유형"), ("title", "제목"), ("summary", "요약"), ("current_process", "현재 업무"),
           ("goals", "목표"), ("data_and_systems", "문서·데이터·시스템"), ("users_and_scale", "사용자·규모"),
           ("budget", "예산"), ("timeline", "일정"), ("open_questions", "추가 확인")],
    "en": [("project_type", "Adoption type"), ("title", "Title"), ("summary", "Summary"), ("current_process", "Current process"),
           ("goals", "Goals"), ("data_and_systems", "Documents, data and systems"), ("users_and_scale", "Users and scale"),
           ("budget", "Budget"), ("timeline", "Timeline"), ("open_questions", "Open questions")],
}


def brief_text(brief, lang="ko"):
    labels = BRIEF_LABELS["en" if lang == "en" else "ko"]
    lines = []
    for key, label in labels:
        value = brief.get(key)
        if value:
            lines.append(f"- {label}: {', '.join(value) if isinstance(value, list) else value}")
    return "\n".join(lines) or ("- (no AI summary)" if lang == "en" else "- (AI 상담 요약 없음)")


async def read_inquiry(request, forms):
    """Accept JSON, or multipart with a JSON 'payload' field plus up to three 'files'."""
    files = []
    try:
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            form = await request.form(max_files=uploads.MAX_FILES + 1, max_fields=5, max_part_size=64 * 1024)
            forms.append(form)
            raw = form.get("payload")
            files = [f for f in form.getlist("files") if isinstance(f, UploadFile)]
            if not isinstance(raw, str):
                raise HTTPException(422, "접수 내용을 확인해 주세요.")
        else:
            raw = await request.body()
        return Inquiry.model_validate_json(raw), files
    except ValidationError:
        raise HTTPException(422, "입력값을 확인해 주세요.") from None
    except HTTPException:
        raise
    except Exception:  # malformed multipart, too many files or fields
        raise HTTPException(422, f"첨부 파일은 {uploads.MAX_FILES}개까지, 접수 내용은 양식으로 보내 주세요.") from None


@router.post("/inquiries")
async def submit_inquiry(request: Request):
    forms = []
    try:
        return await handle_inquiry(request, forms)
    finally:
        for form in forms:
            await form.close()  # remove spooled upload temp files


async def handle_inquiry(request, forms):
    body, files = await read_inquiry(request, forms)
    if body.website:
        return {"ok": True}  # silently drop bots
    limit(request, "inquiry", 5, 3600)
    try:
        files = uploads.check(files)
    except uploads.UploadError as error:
        raise HTTPException(422, str(error)) from None
    if not body.consent:
        raise HTTPException(422, "개인정보 수집·이용에 동의해 주세요.")
    email = body.email.strip()
    if not EMAIL.match(email):
        raise HTTPException(422, "이메일 주소를 확인해 주세요.")
    brief = clean_brief(body.brief)
    if not brief and len(body.message.strip()) < 5:
        raise HTTPException(422, "문의 내용을 조금만 더 적어 주세요.")
    transcript = [m.model_dump() for m in body.transcript]
    inquiry_id = store.create_inquiry(body.name.strip(), body.company.strip(), email, body.phone.strip(),
                                      body.message.strip(), brief, transcript, body.lang)
    try:
        saved = await uploads.save(inquiry_id, files)
    except uploads.UploadError as error:
        store.delete_inquiry(inquiry_id)
        raise HTTPException(422, str(error)) from None
    for display, stored, size in saved:
        store.add_file(inquiry_id, display, stored, size)
    if body.session:
        store.link_consult(body.session, inquiry_id)
    attached = "\n".join(f"- {display} ({size / 1024 / 1024:.1f}MB)" for display, _, size in saved) or "- 없음"
    link = f"{notify.base_url()}/admin?inquiry={inquiry_id}" if notify.base_url() else f"/admin?inquiry={inquiry_id}"
    english = body.lang == "en"
    asked = sum(m["role"] == "user" for m in transcript)
    talk = f"고객 메시지 {asked}개 (전체 대화는 관리 화면에서 확인)" if asked else "없음"
    notify.send(f"[새 상담 접수 #{inquiry_id}]{' [영문]' if english else ''} {brief.get('title') or body.company or body.name}",
                f"새 상담이 접수되었습니다.{' 영문 사이트에서 접수되어 고객 메일은 영어로 보냈습니다. 답장도 영어로 해 주세요.' if english else ''}\n\n"
                f"이름: {body.name}\n회사: {body.company or '-'}\n이메일: {email}\n"
                f"전화: {body.phone or '-'}\n\n[AI 상담 요약]\n{brief_text(brief)}\n\n[AI 상담 대화]\n{talk}\n\n[직접 남긴 내용]\n{body.message or '-'}\n\n"
                f"[첨부 파일]\n{attached}\n\n관리 화면: {link}\n\n이 메일에 바로 답장하면 고객에게 전달됩니다.\n", reply_to=email)
    name, company = body.name.strip(), consult.company(body.lang)
    if english:
        files_part = f"[Attachments]\n{attached}\n\n" if saved else ""
        notify.send_customer(email, f"[{company}] We received your inquiry",
                             f"Hi {name},\n\nThank you for contacting {company}.\n\n"
                             f"[Your request]\n{brief_text(brief, 'en') if brief else body.message.strip()}\n\n{files_part}"
                             f"[Next step]\n{QUOTE_STEP['en']}\n\n"
                             f"If you have anything to add or reference materials to share, just reply to this e-mail.\n\nBest regards,\n{company}\n")
    else:
        notify.send_customer(email, f"[{company}] 상담이 접수되었습니다",
                             f"{name}님, {company}에 상담을 남겨 주셔서 감사합니다.\n\n"
                             f"[접수 내용]\n{brief_text(brief) if brief else body.message.strip()}\n\n"
                             + (f"[첨부 파일]\n{attached}\n\n" if saved else "")
                             + f"[다음 단계]\n담당자가 내용을 검토한 뒤 이 메일 주소로 연락드립니다. {QUOTE_STEP['ko']}\n\n"
                             f"덧붙일 내용이나 참고 자료가 있으면 이 메일에 회신해 주세요.\n\n{company} 드림\n")
    return {"ok": True, "id": inquiry_id}


# ---------- 견적 확인·착수금 결제 ----------

def toss_ready():
    return bool(os.environ.get("TOSS_CLIENT_KEY") and os.environ.get("TOSS_SECRET_KEY"))


def mock_payments():
    """Local-only simulated payment (PAYMENT_MOCK=1). Never active when real Toss keys are configured."""
    return os.environ.get("PAYMENT_MOCK") == "1" and not toss_ready()


def payment_mode():
    return "toss" if toss_ready() else "mock" if mock_payments() else "off"


def quote_payment_mode(quote):
    """Demo quotes are never charged: Toss only with test keys, otherwise the mock flow."""
    if quote.get("is_demo"):
        return "toss" if toss_ready() and os.environ["TOSS_CLIENT_KEY"].startswith("test_") else "mock"
    return payment_mode()


def quote_link(token):
    return f"{notify.base_url()}/quote?t={token}"


def quote_lang(quote):
    return "en" if (quote.get("lang") or quote["customer"].get("lang")) == "en" else "ko"


def public_quote(quote):
    mode = quote_payment_mode(quote)
    return {"title": quote["title"], "items": quote["items"], "total": quote["total"], "deposit": quote["deposit"],
            "schedule": quote["schedule"], "note": quote["note"], "status": quote["status"],
            "created_at": quote["created_at"], "paid_at": quote["paid_at"],
            "customer": {"name": quote["customer"].get("name", ""), "company": quote["customer"].get("company", "")},
            "payment_ready": mode != "off", "payment_mode": mode, "is_demo": bool(quote.get("is_demo")),
            "payment_test": bool(quote.get("is_demo")) or (os.environ.get("TOSS_CLIENT_KEY") or "").startswith("test_"),
            "lang": quote_lang(quote),
            "next_steps": [{"title": title, "text": text} for title, text in kickoff_steps(quote_lang(quote))]}


def prune_demo():
    now = time.time()
    with LOCK:
        for key in [k for k, v in DEMO_QUOTES.items() if v["created_at"] + DEMO_TTL < now]:
            del DEMO_QUOTES[key]


def quote_or_404(token):
    quote = None
    if re.fullmatch(r"[A-Za-z0-9_-]{10,64}", token):
        prune_demo()
        quote = DEMO_QUOTES.get(token) or store.get_quote(token)
    if not quote:
        raise HTTPException(404, "견적서를 찾을 수 없습니다. 받은 링크를 다시 확인해 주세요.")
    return quote


class DemoQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=80)
    lang: Lang = "ko"


DEMO_COPY = {
    "ko": {"title": "AI 상담 에이전트 구축", "suffix": "체험용 견적",
           "items": ["요구사항 정리와 화면 설계", "개발과 중간 시연", "운영 서버 배포와 안정화"],
           "schedule": "착수 후 약 6주 (예시)", "customer": "체험 고객",
           "note": "체험용 견적서입니다. 금액과 일정은 예시이며 실제 견적과 관계없고, 결제해도 청구되지 않습니다."},
    "en": {"title": "AI consultation agent", "suffix": "sample quote",
           "items": ["Requirements and screen design", "Development and interim demo", "Production deployment and stabilization"],
           "schedule": "About 6 weeks from kickoff (example)", "customer": "Demo customer",
           "note": "This is a sample quote. Amounts and schedule are examples unrelated to a real quote, and paying does not charge you."},
}


@router.post("/quotes/demo")
def create_demo_quote(body: DemoQuote, request: Request):
    """견적·결제 흐름 체험: a sample quote kept in memory for two hours and never charged."""
    limit(request, "demo-quote", 10, 3600)
    prune_demo()
    with LOCK:
        if len(DEMO_QUOTES) >= DEMO_MAX:
            raise HTTPException(429, "지금 체험이 많습니다. 잠시 후 다시 시도해 주세요.")
        token = "demo-" + secrets.token_urlsafe(18)
        copy = DEMO_COPY[body.lang]
        title = (body.title or "").strip() or copy["title"]
        items = [{"name": name, "amount": amount} for name, amount in zip(copy["items"], (1500000, 4500000, 1000000))]
        total = sum(item["amount"] for item in items)
        DEMO_QUOTES[token] = {
            "id": f"D{secrets.token_hex(3)}", "token": token, "is_demo": True, "created_at": time.time(), "lang": body.lang,
            "title": f"{title} ({copy['suffix']})", "items": items, "total": total, "deposit": total * 3 // 10,
            "schedule": copy["schedule"], "note": copy["note"],
            "status": "sent", "order_id": None, "payment_key": None, "paid_at": None, "payment_method": None,
            "customer": {"name": copy["customer"], "company": "", "email": ""}}
    return {"token": token, "path": f"/quote?t={token}"}


@router.get("/quotes/{token}")
def view_quote(token: str):
    return public_quote(quote_or_404(token))


@router.post("/quotes/{token}/checkout")
def checkout(token: str, request: Request):
    limit(request, "checkout", 20, 3600)
    quote = quote_or_404(token)
    if quote["status"] == "paid":
        raise HTTPException(409, "이미 착수금 결제가 완료된 견적입니다.")
    mode = quote_payment_mode(quote)
    if mode == "off":
        raise HTTPException(503, "온라인 결제를 준비 중입니다. 담당자에게 결제 방법을 문의해 주세요.")
    order_id = f"Q{quote['id']}-{secrets.token_hex(8)}"
    if quote.get("is_demo"):
        quote["order_id"] = order_id
    else:
        store.set_order(token, order_id)
    return {"mock": mode == "mock", "client_key": os.environ.get("TOSS_CLIENT_KEY") or "", "order_id": order_id, "amount": quote["deposit"],
            "order_name": f"{quote['title'][:60]} {'deposit' if quote_lang(quote) == 'en' else '착수금'}", "customer_name": quote["customer"].get("name", ""),
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
    mode = quote_payment_mode(quote)
    if mode == "mock":
        if body.payment_key != f"mock_{body.order_id}":
            raise HTTPException(400, "모의 결제 정보가 올바르지 않습니다.")
        data = {"method": "모의 결제"}
    elif mode == "toss":
        data = toss_confirm(body.payment_key, body.order_id, body.amount)
    else:
        raise HTTPException(503, "온라인 결제를 준비 중입니다.")
    if quote.get("is_demo"):
        quote.update(status="paid", payment_key=body.payment_key, paid_at=time.time(), payment_method=data.get("method") or "")
        return public_quote(quote)
    store.mark_paid(token, body.payment_key, data.get("method") or "")
    customer = quote["customer"]
    english = quote_lang(quote) == "en"
    if customer.get("email") and english:
        notify.send_customer(customer["email"], f"[{consult.company('en')}] Deposit received: next steps",
                             f"Hi {customer.get('name')},\n\nWe received your deposit of KRW {quote['deposit']:,} for '{quote['title']}'. Thank you.\n\n"
                             f"[Next steps]\n{kickoff_text('en')}\n\nQuote and payment record: {quote_link(token)}\n\n"
                             f"If you have any questions, just reply to this e-mail.\n\nBest regards,\n{consult.company('en')}\n")
    elif customer.get("email"):
        notify.send_customer(customer["email"], f"[{consult.company()}] 착수금 결제 완료와 진행 안내",
                             f"{customer.get('name')}님, '{quote['title']}' 착수금 {quote['deposit']:,}원 결제가 확인되었습니다. 감사합니다.\n\n"
                             f"[앞으로의 진행]\n{kickoff_text()}\n\n견적서와 결제 내역: {quote_link(token)}\n\n"
                             f"궁금한 점은 이 메일에 회신해 주세요.\n\n{consult.company()} 드림\n")
    admin = f"{notify.base_url()}/admin?inquiry={quote['inquiry_id']}"
    notify.send(f"[착수금 결제 완료 #{quote['inquiry_id']}]{' [영문]' if english else ''} {quote['title']} · {quote['deposit']:,}원",
                f"착수금 결제가 완료되었습니다. 고객에게 착수 미팅 일정을 연락해 주세요.{' (영문 고객: 영어로 연락해 주세요.)' if english else ''}\n\n"
                f"[고객 연락처]\n이름: {customer.get('name') or '-'}\n회사: {customer.get('company') or '-'}\n"
                f"이메일: {customer.get('email') or '-'}\n전화: {customer.get('phone') or '-'}\n\n"
                f"[결제 내용]\n견적: {quote['title']}\n견적 합계: {quote['total']:,}원\n착수금: {quote['deposit']:,}원\n"
                f"결제수단: {data.get('method') or '-'}\n결제 시각: {datetime.now(KST):%Y-%m-%d %H:%M} (한국 시간)\n주문번호: {body.order_id}\n\n"
                f"견적서: {quote_link(token)}\n관리 화면: {admin}\n\n이 메일에 바로 답장하면 고객에게 전달됩니다.\n",
                reply_to=customer.get("email") or None)
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
            "payments": payment_mode()}


@router.get("/admin/inquiries/{inquiry_id}")
def admin_inquiry(inquiry_id: int, request: Request):
    require_admin(request)
    inquiry = store.get_inquiry(inquiry_id)
    if not inquiry:
        raise HTTPException(404, "문의를 찾을 수 없습니다.")
    return inquiry


@router.get("/admin/consults")
def admin_consults(request: Request, days: int = 30, q: str = ""):
    require_admin(request)
    days = min(max(days, 1), 365)
    store.purge_consults()
    return {"consults": store.list_consults(days, q[:100]), "stats": store.consult_stats(days)}


@router.get("/admin/consults/{session_id}")
def admin_consult(session_id: str, request: Request):
    require_admin(request)
    record = store.get_consult(session_id)
    if not record:
        raise HTTPException(404, "상담 기록을 찾을 수 없습니다.")
    return record


@router.delete("/admin/consults/{session_id}")
def admin_delete_consult(session_id: str, request: Request):
    """정보주체가 삭제를 요청하면 관리자가 바로 지울 수 있게 한다."""
    require_admin(request)
    if not store.delete_consult(session_id):
        raise HTTPException(404, "상담 기록을 찾을 수 없습니다.")
    return {"ok": True}


@router.get("/admin/files/{file_id}")
def admin_file(file_id: int, request: Request):
    """Attachments are only ever served to the admin, always as a download (never rendered inline)."""
    require_admin(request)
    record = store.get_file(file_id)
    try:
        path = uploads.path_of(record["stored_name"]) if record else None
    except uploads.UploadError:
        path = None
    if not path or not path.is_file():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    name = record["original_name"]
    fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_.") or "attachment"
    if not re.search(r"\.[A-Za-z0-9]+$", fallback):
        fallback += Path(name).suffix.lower()
    disposition = f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name)}"
    return FileResponse(path, media_type="application/octet-stream",
                        headers={"Content-Disposition": disposition, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


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
    send_email: bool = True


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
    inquiry = store.get_inquiry(inquiry_id)
    emailed = False
    if body.send_email:
        if not notify.base_url():
            raise HTTPException(422, "견적서를 메일로 보내려면 서버에 PUBLIC_BASE_URL(사이트 주소)을 설정해 주세요. 링크만 만들려면 메일 발송을 끄세요.")
        title, schedule, company = body.title.strip(), body.schedule.strip(), consult.company(inquiry.get("lang") or "ko")
        if inquiry.get("lang") == "en":
            emailed = notify.send_customer(inquiry["email"], f"[{company}] Your quote: {title}",
                                           f"Hi {inquiry['name']},\n\nHere is the quote for '{title}' you requested.\n\n"
                                           f"Total KRW {total:,} / Deposit KRW {body.deposit:,}\n"
                                           + (f"Schedule: {schedule}\n" if schedule else "")
                                           + f"\nReview the quote and pay the deposit at the link below, and we will start development.\n{quote_link(token)}\n\n"
                                           f"If you would like to adjust the scope or price, just reply to this e-mail.\n\nBest regards,\n{company}\n")
        else:
            emailed = notify.send_customer(inquiry["email"], f"[{company}] 견적서를 보내 드립니다: {title}",
                                           f"{inquiry['name']}님, 요청하신 '{title}' 견적서를 보내 드립니다.\n\n"
                                           f"합계 {total:,}원 / 착수금 {body.deposit:,}원\n"
                                           + (f"일정: {schedule}\n" if schedule else "")
                                           + f"\n아래 링크에서 견적서를 확인해 주세요. 내용에 합의하시면 계약서를 작성하고, 착수금이 계좌이체로 입금되면 개발을 시작합니다. 입금 계좌와 진행 순서는 견적서 화면에 있습니다.\n{quote_link(token)}\n\n"
                                           f"범위나 금액을 조정하고 싶으시면 이 메일에 회신해 주세요.\n\n{company} 드림\n")
    return {"token": token, "path": f"/quote?t={token}", "emailed": emailed, "inquiry": inquiry}

