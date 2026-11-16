"""운영 플랫폼(PMS) 데모 API (/api/demo/pms).

방문자마다 가상 데이터가 담긴 샌드박스를 메모리에 만들고 2시간 뒤 지운다. DB에 남기지 않는다.
요청 헤더 X-Pms-Sandbox(샌드박스 토큰)와 X-Pms-User(체험할 사용자 id)로 역할을 바꿔 가며 체험한다.
업무 규칙은 service.py, 권한은 access.py, 금액 계산은 billing.py 에 있다.
"""
from __future__ import annotations

import copy
import secrets
import time
from datetime import date as Date, datetime
from threading import RLock
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from . import seed, service
from .access import ROLES, Forbidden, NotFound, actor_from_user

if __package__ and __package__.startswith("backend"):
    from ..site_api import KST, limit
else:
    from site_api import KST, limit

router = APIRouter(prefix="/api/demo/pms")
LOCK = RLock()
SANDBOXES: dict[str, dict] = {}  # token -> {"data", "created"}
TTL = 2 * 3600
MAX_SANDBOXES = 300
Month = Field(pattern=r"^20\d\d-(0[1-9]|1[0-2])$")
TokenHeader = Header(alias="X-Pms-Sandbox", pattern=r"^[A-Za-z0-9_-]{20,64}$")
UserHeader = Header(alias="X-Pms-User", pattern=r"^[a-z0-9-]{2,40}$")


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
    return _call(service.transition, actor, data, contract_id, body.to, body.date or _today())


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
