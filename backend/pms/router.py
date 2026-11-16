"""운영 플랫폼(PMS) 데모 API (/api/demo/pms).

방문자마다 가상 데이터가 담긴 샌드박스를 메모리에 만들고 2시간 뒤 지운다. DB에 남기지 않는다.
요청 헤더 X-Pms-Sandbox(샌드박스 토큰)와 X-Pms-User(체험할 사용자 id)로 역할을 바꿔 가며 체험한다.
업무 규칙은 service.py, 권한은 access.py, 금액 계산은 billing.py 에 있다.
민원 분류는 voc.py(규칙)·voc_ai.py(Claude), 출입 연동은 integration.py, 회계 분개는 ledger.py 에 있다.
"""
from __future__ import annotations

import copy
import logging
import secrets
import time
from collections import deque
from datetime import date as Date, datetime
from threading import RLock
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import seed, service, voc, voc_ai
from .access import ROLES, Forbidden, NotFound, actor_from_user

if __package__ and __package__.startswith("backend"):
    from ..site_api import KST, limit
else:
    from site_api import KST, limit

log = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/demo/pms")
LOCK = RLock()
SANDBOXES: dict[str, dict] = {}  # token -> {"data", "created"}
TTL = 2 * 3600
MAX_SANDBOXES = 300
Month = Field(pattern=r"^20\d\d-(0[1-9]|1[0-2])$")
TokenHeader = Header(alias="X-Pms-Sandbox", pattern=r"^[A-Za-z0-9_-]{20,64}$")
UserHeader = Header(alias="X-Pms-User", pattern=r"^[a-z0-9-]{2,40}$")
# 민원 AI 분류 사용량 상한: 체험 1회당, 서버 전체 1시간당. 넘으면 규칙 분류로 대신한다.
AI_PER_SANDBOX = 10
AI_PER_HOUR = 200
AI_CALLS: deque[float] = deque()


def _today() -> Date:
    return datetime.now(KST).date()


def _now() -> datetime:
    return datetime.now(KST)


def _prune(now: float) -> None:
    for token in [t for t, box in SANDBOXES.items() if box["created"] < now - TTL]:
        del SANDBOXES[token]
    while len(SANDBOXES) >= MAX_SANDBOXES:
        oldest = min(SANDBOXES, key=lambda t: SANDBOXES[t]["created"])
        del SANDBOXES[oldest]


def _context(token: str, user_id: str):
    with LOCK:
        box = SANDBOXES.get(token)
        if not box or box["created"] < time.monotonic() - TTL:
            raise HTTPException(404, "체험 세션이 만료되었습니다. 새로 시작해 주세요.")
        data = box["data"]
    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if user is None:
        raise HTTPException(404, "없는 사용자입니다.")
    return data, actor_from_user(user)


def _call(fn, *args, **kwargs):
    try:
        with LOCK:
            return fn(*args, **kwargs)
    except Forbidden:
        raise HTTPException(403, "이 역할로는 할 수 없는 작업입니다.")
    except NotFound:
        raise HTTPException(404, "찾을 수 없습니다.")
    except service.Invalid as exc:
        raise HTTPException(409, str(exc))


def _user_card(user: dict, data: dict) -> dict:
    role = ROLES[user["role"]]
    sites = [s["name"] for s in data["sites"]] if role.get("all_sites") else \
        [s["name"] for s in data["sites"] if s["id"] in user["site_ids"]]
    return {"id": user["id"], "name": user["name"], "role": user["role"], "role_label": role["label"],
            "sites": sites, "permissions": sorted(role["perms"])}


@router.post("/sandbox")
def create_sandbox(request: Request):
    limit(request, "pms-sandbox", 30, 3600)
    token = secrets.token_urlsafe(24)
    data = copy.deepcopy(seed.build())
    data["access_system"]["secret"] = secrets.token_hex(16)  # 체험마다 다른 연동 서명 키 (메모리에만 둔다)
    with LOCK:
        _prune(time.monotonic())
        SANDBOXES[token] = {"data": data, "created": time.monotonic()}
    return {"token": token, "expires_in": TTL, "operator": data["operator"],
            "users": [_user_card(u, data) for u in data["users"]]}


@router.get("/me")
def me(token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    user = next(u for u in data["users"] if u["id"] == actor.user_id)
    return _user_card(user, data)


@router.get("/sites")
def sites(token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_sites, actor, data)


@router.get("/sites/{site_id}/units")
def units(site_id: str, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_units, actor, data, site_id, _today())


@router.get("/sites/{site_id}/residents")
def residents(site_id: str, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_residents, actor, data, site_id)


@router.get("/residents/{resident_id}")
def resident(resident_id: str, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.get_resident, actor, data, resident_id, _now())


class UsageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: str = Field(pattern=r"^[a-z_]{2,30}$")
    quantity: int = Field(ge=1, le=100)
    date: Date


@router.post("/residents/{resident_id}/usages")
def add_usage(resident_id: str, body: UsageIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.record_usage, actor, data, resident_id, body.service, body.quantity, body.date)


@router.get("/sites/{site_id}/contracts")
def contracts(site_id: str, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_contracts, actor, data, site_id)


class TransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: Literal["signed", "active", "terminated", "cancelled"]
    date: Date | None = None


@router.post("/contracts/{contract_id}/transition")
def contract_transition(contract_id: str, body: TransitionIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.transition, actor, data, contract_id, body.to, body.date or _today(), _today(), _now())


class BillingRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str = Month


@router.post("/sites/{site_id}/billing-runs")
def billing_run(site_id: str, body: BillingRunIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.run_billing, actor, data, site_id, body.month)


@router.get("/sites/{site_id}/invoices")
def invoices(site_id: str, month: str | None = Query(default=None, pattern=r"^20\d\d-(0[1-9]|1[0-2])$"),
             as_of: Date | None = None, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_invoices, actor, data, site_id, month, as_of or _today())


class PaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: int = Field(ge=10, le=10_000_000_000)
    paid_on: Date
    as_of: Date | None = None


@router.post("/invoices/{invoice_id}/payments")
def payment(invoice_id: str, body: PaymentIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.add_payment, actor, data, invoice_id, body.amount, body.paid_on, body.as_of or _today())


@router.get("/audit")
def audit(token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_audit, actor, data)


# ---------- 민원 ----------

@router.get("/sites/{site_id}/vocs")
def vocs(site_id: str, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_vocs, actor, data, site_id)


class VocIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=voc.MAX_CHARS)


def _ai_slot(data: dict) -> bool:
    """AI 분류를 쓸 수 있으면 사용량을 하나 차지하고 True."""
    if not voc_ai.enabled():
        return False
    now = time.monotonic()
    with LOCK:
        while AI_CALLS and AI_CALLS[0] < now - 3600:
            AI_CALLS.popleft()
        if data["voc_ai_calls"] >= AI_PER_SANDBOX or len(AI_CALLS) >= AI_PER_HOUR:
            return False
        data["voc_ai_calls"] += 1
        AI_CALLS.append(now)
    return True


def classify(data: dict, redacted: str) -> tuple[dict, str]:
    """(분류 결과, 출처). 출처: ai | rule. AI 호출은 잠금 밖에서 한다."""
    if _ai_slot(data):
        try:
            result = voc.normalize_ai(voc_ai.classify(redacted))
            if result:
                return result, "ai"
            log.warning("민원 분류 AI 응답 형식이 맞지 않아 규칙 분류로 대신합니다.")
        except voc_ai.VocAIError:
            pass
    return voc.rule_classify(redacted), "rule"


@router.post("/residents/{resident_id}/vocs")
def add_voc(resident_id: str, body: VocIn, request: Request, token: str = TokenHeader, user_id: str = UserHeader):
    limit(request, "pms-voc", 20, 3600)
    data, actor = _context(token, user_id)
    resident, redacted = _call(service.prepare_voc, actor, data, resident_id, body.text)
    result, source = classify(data, redacted)
    return _call(service.create_voc, actor, data, resident, body.text, redacted, result, source, _now())


class VocStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: Literal["in_progress", "done"]


@router.post("/vocs/{voc_id}/status")
def voc_status(voc_id: str, body: VocStatusIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.voc_status, actor, data, voc_id, body.to)


# ---------- 출입 시스템 연동 ----------

@router.get("/sites/{site_id}/integration")
def integration_view(site_id: str, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.list_integration, actor, data, site_id)


class ProcessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: Date | None = None


@router.post("/sites/{site_id}/integration/process")
def integration_process(site_id: str, body: ProcessIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.process_integration, actor, data, site_id, body.as_of or _today(), _now())


@router.post("/integration/events/{event_id}/resend")
def integration_resend(event_id: str, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.resend_event, actor, data, event_id, _now())


class FailNextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(ge=0, le=4)


@router.post("/integration/fail-next")
def integration_fail_next(body: FailNextIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.set_fail_next, actor, data, body.count)


# ---------- 회계 내보내기·마감 ----------

MonthQuery = Query(pattern=r"^20\d\d-(0[1-9]|1[0-2])$")


@router.get("/sites/{site_id}/ledger")
def ledger_view(site_id: str, month: str = MonthQuery, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.ledger_view, actor, data, site_id, month)


@router.get("/sites/{site_id}/ledger.csv")
def ledger_csv(site_id: str, month: str = MonthQuery, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    text = _call(service.ledger_csv, actor, data, site_id, month)
    return Response(text.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="journal-{site_id}-{month}.csv"'})


class CloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str = Month


@router.post("/sites/{site_id}/ledger/close")
def ledger_close(site_id: str, body: CloseIn, token: str = TokenHeader, user_id: str = UserHeader):
    data, actor = _context(token, user_id)
    return _call(service.close_month, actor, data, site_id, body.month, _now())
