"""Bounded, browser-isolated in-memory sample demo sessions."""
import secrets
from threading import RLock
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

if __package__:
    from .purchase_orders import ReviewError, apply_review, export_order, load_master, order_view, parse_order, text
    from .customer_format import export_customer_format
else:
    from purchase_orders import ReviewError, apply_review, export_order, load_master, order_view, parse_order, text
    from customer_format import export_customer_format

router = APIRouter(prefix="/api/demo/purchase-orders")
COOKIE = "purchase_demo"
TTL = 1800
LOCK = RLock()
SESSIONS = {}


class Start(BaseModel):
    model_config = ConfigDict(extra="forbid")
    samples: list[Literal["A", "B", "C"]] = Field(min_length=1, max_length=3)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    action: Literal["resolve", "exclude", "reset", "register", "restore"]
    quantity: str | None = Field(default=None, max_length=24)
    item_code: str | None = Field(default=None, max_length=12)
    confirmed_amount: str | None = Field(default=None, max_length=30)
    reason: str | None = Field(default=None, max_length=200)
    new_code: str | None = Field(default=None, max_length=20)
    new_name: str | None = Field(default=None, max_length=60)
    new_unit: str | None = Field(default=None, max_length=20)
    new_price: str | None = Field(default=None, max_length=20)


def session(request):
    value = SESSIONS.get(request.cookies.get(COOKIE))
    if not value or value["expires"] < time.monotonic():
        raise HTTPException(401, "체험이 없거나 30분이 지나 만료되었습니다. 다시 시작해 주세요.")
    return value


def snapshot(value):
    orders = [order_view(order, value["master"]) for order in value["orders"].values()]
    return {"revision": value["revision"], "csrf": value["csrf"], "orders": orders,
            "master": [{**item, "price": text(item["price"])} for item in value["master"].values()],
            "summary": {"source_rows": sum(len(o["rows"]) for o in orders), "accepted": sum(o["accepted"] for o in orders),
                        "review": sum(o["review"] for o in orders), "canceled": sum(o["canceled"] for o in orders)}}


@router.get("/samples/{sample}/preview")
def source_preview(sample: str):
    try:
        order = parse_order(sample)
    except ReviewError as error:
        raise HTTPException(400, str(error)) from None
    return {key: order[key] for key in ("sample", "filename", "sheet", "preview", "layout_rows")}


@router.post("/start")
def start(body: Start, request: Request, response: Response):
    if request.headers.get("X-Demo-Client") != "purchase-orders":
        raise HTTPException(403, "체험 화면에서 시작해 주세요.")
    with LOCK:
        now = time.monotonic()
        for key in list(SESSIONS):
            if SESSIONS[key]["expires"] < now:
                del SESSIONS[key]
        old = request.cookies.get(COOKIE)
        if len(SESSIONS) >= 64 and old not in SESSIONS:
            raise HTTPException(429, "현재 체험이 많습니다. 잠시 후 다시 시도해 주세요.")
        value = {"master": load_master(), "orders": {s: parse_order(s) for s in dict.fromkeys(body.samples)},
                 "csrf": secrets.token_urlsafe(32), "revision": 0, "expires": now + TTL}
        SESSIONS.pop(old, None)
        key = secrets.token_urlsafe(32)
        SESSIONS[key] = value
        response.set_cookie(COOKIE, key, max_age=TTL, httponly=True, samesite="strict",
                            secure=request.url.scheme == "https", path="/api/demo/purchase-orders")
        return snapshot(value)


@router.get("/session")
def current(request: Request):
    with LOCK:
        return snapshot(session(request))


@router.post("/{sample}/rows/{row_id}")
def review(sample: str, row_id: int, body: Review, request: Request):
    with LOCK:
        value = session(request)
        if not secrets.compare_digest(request.headers.get("X-Demo-CSRF", ""), value["csrf"]):
            raise HTTPException(403, "체험 확인 정보가 올바르지 않습니다.")
        if value["revision"] != body.revision:
            raise HTTPException(409, "다른 창에서 검수가 변경되었습니다. 진행 중 체험을 다시 불러오세요.")
        order = value["orders"].get(sample)
        row = next((r for r in order["rows"] if r["id"] == row_id), None) if order else None
        if row is None:
            raise HTTPException(404, "현재 체험의 원본 행이 아닙니다.")
        try:
            apply_review(row, value["master"], body.model_dump())
        except ReviewError as error:
            raise HTTPException(422, str(error)) from None
        value["revision"] += 1
        return snapshot(value)


@router.get("/{sample}/download")
def download(sample: str, revision: int, request: Request, layout: Literal["standard", "A", "B", "C"] = "standard"):
    with LOCK:
        value = session(request)
        if revision != value["revision"]:
            raise HTTPException(409, "검수 상태가 변경되었습니다. 현재 결과를 다시 확인해 주세요.")
        if sample not in value["orders"]:
            raise HTTPException(404, "현재 체험의 거래처가 아닙니다.")
        try:
            if layout == "standard":
                workbook, filename = export_order(value["orders"][sample], value["master"]), f"statement_{sample}.xlsx"
            else:
                workbook = export_customer_format(value["orders"][sample], value["orders"], value["master"], layout)
                filename = f"statement_{sample}_as_{layout}_form.xlsx"
        except ReviewError as error:
            raise HTTPException(409, str(error)) from None
        return Response(workbook, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})
