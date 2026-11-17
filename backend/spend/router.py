"""구독·고정지출 찾기 데모 API (/api/demo/spend).

방문자마다 가상 거래내역 샌드박스를 메모리에 만들고 2시간 뒤 지운다. DB에 남기지 않고, 방문자 입력(거래내역)도 받지 않는다.
분석 규칙은 detect.py(반복 결제)·merchants.py(가맹점 정리)·service.py(합계·중복·절감·알림), AI 정리는 enrich_ai.py,
가맹점 사전 현황은 intel.py, 해지 흐름(가상 처리)은 cancel.py 에 있다.

사용자 확인(맞아요·구독 아님)은 그 체험의 계산에 바로 반영하고, 서버 메모리의 제보 집계(REPORTS)에도 묶음 id 기준으로 쌓는다.
제보는 사전을 바로 바꾸지 않고 가맹점 사전 화면에 건수와 검수 대기로만 보인다.

AI 정리 결과는 가맹점 key 기준으로 서버 메모리에 함께 보관한다(AI_CACHE). 가상 데이터라 방문자 간에 같은 가맹점이 반복되므로,
한 번 정리한 가맹점은 다시 묻지 않아 호출 비용이 들지 않는다.
"""
from __future__ import annotations

import copy
import secrets
import time
from collections import deque
from datetime import date, datetime
from threading import RLock
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict

from . import enrich_ai, intel, seed, service

if __package__ and __package__.startswith("backend"):
    from ..site_api import KST, limit
else:
    from site_api import KST, limit

router = APIRouter(prefix="/api/demo/spend")
LOCK = RLock()
SANDBOXES: dict[str, dict] = {}
TTL = 2 * 3600
MAX_SANDBOXES = 300
AI_CACHE: dict[str, dict] = {}
AI_PER_SANDBOX = 5
AI_PER_HOUR = 60
AI_CALLS: deque[float] = deque()
REPORTS: dict[str, dict[str, set[str]]] = {}  # 묶음 id -> {"confirm": {체험 토큰}, "reject": {...}}
TokenHeader = Header(alias="X-Spend-Sandbox", pattern=r"^[A-Za-z0-9_-]{20,64}$")
Persona = Literal["jisoo", "junghoon", "haneul"]


def _now() -> datetime:
    return datetime.now(KST)


def _prune(now: float) -> None:
    for token in [t for t, box in SANDBOXES.items() if box["created"] < now - TTL]:
        del SANDBOXES[token]
    while len(SANDBOXES) >= MAX_SANDBOXES:
        del SANDBOXES[min(SANDBOXES, key=lambda t: SANDBOXES[t]["created"])]


def _data(token: str) -> dict:
    with LOCK:
        box = SANDBOXES.get(token)
        if not box or box["created"] < time.monotonic() - TTL:
            raise HTTPException(404, "체험 세션이 만료되었습니다. 새로 시작해 주세요.")
        return box["data"]


def _call(fn, *args):
    try:
        with LOCK:
            return fn(*args)
    except service.Invalid as exc:
        raise HTTPException(409, str(exc))


@router.post("/sandbox")
def create_sandbox(request: Request):
    limit(request, "spend-sandbox", 30, 3600)
    token = secrets.token_urlsafe(24)
    data = copy.deepcopy(seed.build())
    with LOCK:
        _prune(time.monotonic())
        SANDBOXES[token] = {"data": data, "created": time.monotonic()}
    return {"token": token, "expires_in": TTL, "as_of": data["as_of"], "period": data["period"],
            "personas": data["personas"], "ai_enabled": enrich_ai.enabled()}


@router.get("/personas/{persona_id}/analysis")
def analysis(persona_id: Persona, token: str = TokenHeader):
    data = _data(token)
    return _call(service.analyze, data, persona_id, AI_CACHE, _now())


@router.get("/merchants")
def merchants_registry(token: str = TokenHeader):
    data = _data(token)
    with LOCK:
        return intel.registry(data, AI_CACHE, REPORTS)


def _ai_slot(data: dict) -> bool:
    now = time.monotonic()
    with LOCK:
        while AI_CALLS and AI_CALLS[0] < now - 3600:
            AI_CALLS.popleft()
        if data["ai_runs"] >= AI_PER_SANDBOX or len(AI_CALLS) >= AI_PER_HOUR:
            return False
        data["ai_runs"] += 1
        AI_CALLS.append(now)
    return True


@router.post("/personas/{persona_id}/enrich")
def enrich(persona_id: Persona, request: Request, token: str = TokenHeader):
    """사전에 없는 반복 결제 가맹점을 AI로 정리한다. 이미 정리된 가맹점은 저장된 결과를 쓴다. AI 호출은 잠금 밖에서 한다."""
    limit(request, "spend-enrich", 20, 3600)
    data = _data(token)
    with LOCK:
        found, _ = service.find_series(data["transactions"][persona_id], date.fromisoformat(data["as_of"]),
                                       AI_CACHE)
        pending = service.unknown_candidates(found, AI_CACHE)
    result = {"asked": len(pending), "saved": 0, "status": "done"}
    if pending:
        if not enrich_ai.enabled():
            result["status"] = "no_ai"
        elif not _ai_slot(data):
            result["status"] = "limit"
        else:
            try:
                saved = enrich_ai.normalize(enrich_ai.classify(pending), {p["key"] for p in pending})
            except enrich_ai.EnrichError:
                result["status"] = "failed"
            else:
                with LOCK:
                    AI_CACHE.update(saved)
                result["saved"] = len(saved)
                if len(saved) < len(pending):
                    result["status"] = "partial"
    view = _call(service.analyze, data, persona_id, AI_CACHE, _now())
    return {**view, "enrich": result}


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["confirm", "reject", "reset"]


@router.post("/personas/{persona_id}/series/{series_id}/review")
def review(persona_id: Persona, body: ReviewIn, series_id: str = Path(pattern=r"^sr-[0-9a-f]{10}$"),
           token: str = TokenHeader):
    data = _data(token)
    view = _call(service.review, data, persona_id, series_id, body.decision, AI_CACHE)
    canon = next(r["canonical"] for r in view["series"] if r["id"] == series_id)
    with LOCK:
        votes = REPORTS.setdefault(canon, {"confirm": set(), "reject": set()})
        votes["confirm"].discard(token)
        votes["reject"].discard(token)
        if body.decision != "reset":
            votes[body.decision].add(token)
    return view


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["request", "confirm", "undo"]


@router.post("/personas/{persona_id}/series/{series_id}/cancel")
def cancel_series(persona_id: Persona, body: CancelIn, series_id: str = Path(pattern=r"^sr-[0-9a-f]{10}$"),
                  token: str = TokenHeader):
    data = _data(token)
    return _call(service.cancel_action, data, persona_id, series_id, body.action, AI_CACHE, _now())
