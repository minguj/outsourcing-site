"""PMS 업무 규칙. 데이터는 샌드박스 dict 하나에 있고, 모든 조회는 Actor 범위를 거친다."""
from __future__ import annotations

from datetime import date, datetime, time

from . import billing, integration, ledger, voc
from .access import Actor, Forbidden, NotFound, view_resident
from .seed import people_names

CONTRACT_FLOW = {
    "draft": {"signed", "cancelled"},
    "signed": {"active", "cancelled"},
    "active": {"terminated"},
    "terminated": set(),
    "cancelled": set(),
}
CONTRACT_LABELS = {"draft": "작성 중", "signed": "체결", "active": "입주", "terminated": "해지", "cancelled": "취소"}
RESIDENT_LABELS = {"applicant": "입주 상담", "resident": "입주 중", "moved_out": "퇴거"}
UNIT_LABELS = {"vacant": "공실", "reserved": "입주 예정", "occupied": "입주", "maintenance": "정비"}


class Invalid(Exception):
    """업무 규칙 위반 (409)."""


def _get(data: dict, kind: str, item_id: str) -> dict:
    for item in data[kind]:
        if item["id"] == item_id:
            return item
    raise NotFound(item_id)


def _site_scoped(actor: Actor, item: dict) -> dict:
    if not actor.sees_site(item["site_id"]):
        raise NotFound(item["id"])
    return item


def _site(actor: Actor, data: dict, site_id: str) -> dict:
    site = _get(data, "sites", site_id)
    if not actor.sees_site(site["id"]):
        raise NotFound(site_id)
    return site


def _resident_scoped(actor: Actor, data: dict, resident_id: str) -> dict:
    resident = _get(data, "residents", resident_id)
    if not actor.sees_resident(resident):
        raise NotFound(resident_id)
    return resident


def _closed(data: dict, site_id: str, month: str) -> bool:
    return any(c["site_id"] == site_id and c["month"] == month for c in data["closed"])


def _require_open(data: dict, site_id: str, month: str) -> None:
    if _closed(data, site_id, month):
        raise Invalid(f"{month}은(는) 회계 마감된 달이라 바꿀 수 없습니다.")


def _names(data: dict) -> tuple[dict, dict]:
    residents = {r["id"]: r["name"] for r in data["residents"]}
    units = {u["id"]: u["building"] + u["number"] for u in data["units"]}
    return residents, units


def _audit(data: dict, actor: Actor, action: str, target: dict, fields: list[str], at: datetime) -> None:
    data["audit"].append({
        "at": at.isoformat(timespec="seconds"), "user_id": actor.user_id, "user_name": actor.name,
        "role": actor.role, "action": action, "target": target["id"], "target_name": target["name"], "fields": fields,
    })


# ---------- 사업장·호실 ----------

def list_sites(actor: Actor, data: dict) -> list[dict]:
    actor.require("site.read")
    return [s for s in data["sites"] if actor.sees_site(s["id"])]


def unit_status(data: dict, unit: dict, today: date) -> str:
    if unit["maintenance"]:
        return "maintenance"
    for c in data["contracts"]:
        if c["unit_id"] != unit["id"]:
            continue
        end = date.fromisoformat(c["end_date"]) if c["end_date"] else None
        if c["status"] in ("active", "terminated") and date.fromisoformat(c["start_date"]) <= today and (end is None or today <= end):
            return "occupied"
        if c["status"] == "signed" or (c["status"] == "active" and date.fromisoformat(c["start_date"]) > today):
            return "reserved"
    return "vacant"


def list_units(actor: Actor, data: dict, site_id: str, today: date) -> list[dict]:
    actor.require("unit.read")
    _site(actor, data, site_id)
    out = []
    for unit in data["units"]:
        if unit["site_id"] == site_id:
            status = unit_status(data, unit, today)
            out.append({**unit, "status": status, "status_label": UNIT_LABELS[status]})
    return out


# ---------- 입주자 ----------

def get_resident(actor: Actor, data: dict, resident_id: str, now: datetime) -> dict:
    actor.require("resident.read")
    resident = _resident_scoped(actor, data, resident_id)
    view, revealed = view_resident(actor, resident)
    if revealed:
        _audit(data, actor, "resident.view", resident, revealed, now)
    return view


def list_residents(actor: Actor, data: dict, site_id: str) -> list[dict]:
    """이름·호실·상태만 담은 목록. 연락처·건강정보는 상세 조회에서 권한에 따라 보여 준다."""
    actor.require("resident.read")
    _site(actor, data, site_id)
    units = {u["id"]: u for u in data["units"]}
    out = []
    for r in data["residents"]:
        if r["site_id"] == site_id and actor.sees_resident(r):
            unit = units.get(r["unit_id"])
            out.append({"id": r["id"], "name": r["name"], "unit_id": r["unit_id"],
                        "unit_number": unit["building"] + unit["number"] if unit else None,
                        "status": r["status"], "status_label": RESIDENT_LABELS[r["status"]]})
    return out


def record_usage(actor: Actor, data: dict, resident_id: str, service: str, quantity: int, on: date) -> dict:
    actor.require("service.write")
    resident = _resident_scoped(actor, data, resident_id)
    site = _get(data, "sites", resident["site_id"])
    if service not in site["prices"]:
        raise Invalid(f"이 사업장에 없는 서비스입니다: {service}")
    if resident["status"] != "resident":
        raise Invalid("입주 중인 입주자만 서비스 이용을 기록할 수 있습니다.")
    _require_open(data, site["id"], on.isoformat()[:7])
    usage = {"id": f"u-{len(data['usages']) + 1}", "site_id": site["id"], "resident_id": resident_id,
             "service": service, "date": on.isoformat(), "quantity": quantity}
    data["usages"].append(usage)
    return usage


# ---------- 계약 ----------

def list_contracts(actor: Actor, data: dict, site_id: str) -> list[dict]:
    actor.require("contract.read")
    _site(actor, data, site_id)
    residents, units = _names(data)
    return [{**c, "status_label": CONTRACT_LABELS[c["status"]], "resident_name": residents.get(c["resident_id"]),
             "unit_number": units.get(c["unit_id"]), "next": sorted(CONTRACT_FLOW[c["status"]])}
            for c in data["contracts"] if c["site_id"] == site_id]


def transition(actor: Actor, data: dict, contract_id: str, to: str, on: date,
               today: date | None = None, now: datetime | None = None) -> dict:
    """on: 해지(퇴거)일. today/now: 연동 이벤트를 지금 보낼지 정하는 기준 (없으면 on 기준)."""
    actor.require("contract.write")
    contract = _site_scoped(actor, _get(data, "contracts", contract_id))
    if to not in CONTRACT_FLOW[contract["status"]]:
        raise Invalid(f"'{CONTRACT_LABELS[contract['status']]}' 상태에서 '{CONTRACT_LABELS.get(to, to)}'(으)로 바꿀 수 없습니다.")
    unit = _get(data, "units", contract["unit_id"])
    resident = _get(data, "residents", contract["resident_id"])
    if to in ("signed", "active"):
        if unit["maintenance"]:
            raise Invalid("정비 중인 호실입니다.")
        for other in data["contracts"]:
            if other["id"] != contract["id"] and other["unit_id"] == unit["id"] and other["status"] in ("signed", "active"):
                if other["status"] == "active" and other["end_date"] and date.fromisoformat(other["end_date"]) < date.fromisoformat(contract["start_date"]):
                    continue
                raise Invalid("같은 호실에 진행 중인 다른 계약이 있습니다.")
    if to == "active":
        resident["status"] = "resident"
    if to == "terminated":
        start = date.fromisoformat(contract["start_date"])
        if on < start:
            raise Invalid("퇴거일은 입주일보다 빠를 수 없습니다.")
        contract["end_date"] = on.isoformat()
        resident["status"] = "moved_out"
    contract["status"] = to
    if to == "active":
        _enqueue(data, "access.grant", contract, date.fromisoformat(contract["start_date"]), today or on, now)
    if to == "terminated":
        _enqueue(data, "access.revoke", contract, on, today or on, now)
    residents, units = _names(data)
    return {**contract, "status_label": CONTRACT_LABELS[to], "resident_name": residents.get(contract["resident_id"]),
            "unit_number": units.get(contract["unit_id"]), "next": sorted(CONTRACT_FLOW[to])}


# ---------- 청구·수납 ----------

def _invoice_view(data: dict, invoice: dict, as_of: date) -> dict:
    site = _get(data, "sites", invoice["site_id"])
    payments = [p for p in data["payments"] if p["invoice_id"] == invoice["id"]]
    due = date.fromisoformat(invoice["due_date"])
    left = billing.outstanding(invoice["total"], payments)
    residents, units = _names(data)
    contract = next(c for c in data["contracts"] if c["id"] == invoice["contract_id"])
    return {
        **invoice,
        "resident_name": residents.get(invoice["resident_id"]),
        "unit_number": units.get(contract["unit_id"]),
        "paid": invoice["total"] - left,
        "outstanding": left,
        "late_fee": billing.late_fee(left, due, as_of, site["billing"]["late_rate_pct"]),
        "status": billing.invoice_status(invoice["total"], payments, due, as_of),
        "payments": payments,
    }


def run_billing(actor: Actor, data: dict, site_id: str, month: str) -> dict:
    """사업장 한 곳의 월 청구를 만든다. 같은 계약·같은 달은 한 번만 만든다."""
    actor.require("billing.write")
    site = _site(actor, data, site_id)
    _require_open(data, site_id, month)
    created, skipped = [], []
    for contract in data["contracts"]:
        if contract["site_id"] != site_id or contract["status"] not in ("active", "terminated"):
            continue
        if any(i["contract_id"] == contract["id"] and i["month"] == month for i in data["invoices"]):
            skipped.append(contract["id"])
            continue
        first, last = billing.month_range(month)
        usages = [u for u in data["usages"]
                  if u["resident_id"] == contract["resident_id"] and first <= date.fromisoformat(u["date"]) <= last]
        draft = billing.build_invoice(contract, month, usages, site["prices"])
        if draft is None:
            continue
        invoice = {
            "id": f"inv-{contract['id']}-{month}", "site_id": site_id, "contract_id": contract["id"],
            "resident_id": contract["resident_id"], "month": month,
            "due_date": billing.due_date(month, site["billing"]["due_day"]).isoformat(),
            "lines": [line.__dict__ for line in draft.lines], "total": draft.total,
        }
        data["invoices"].append(invoice)
        created.append(invoice["id"])
    return {"created": created, "skipped": skipped}


def list_invoices(actor: Actor, data: dict, site_id: str, month: str | None, as_of: date) -> list[dict]:
    actor.require("billing.read")
    _site(actor, data, site_id)
    out = []
    for invoice in data["invoices"]:
        if invoice["site_id"] != site_id or (month and invoice["month"] != month):
            continue
        if actor.own_residents_only and invoice["resident_id"] not in actor.resident_ids:
            continue
        out.append(_invoice_view(data, invoice, as_of))
    return out


def add_payment(actor: Actor, data: dict, invoice_id: str, amount: int, paid_on: date, as_of: date) -> dict:
    actor.require("billing.write")
    invoice = _site_scoped(actor, _get(data, "invoices", invoice_id))
    current = _invoice_view(data, invoice, as_of)
    if amount > current["outstanding"]:
        raise Invalid(f"남은 금액({current['outstanding']:,}원)보다 많이 받을 수 없습니다.")
    _require_open(data, invoice["site_id"], paid_on.isoformat()[:7])
    data["payments"].append({"id": f"pay-{len(data['payments']) + 1}", "invoice_id": invoice_id,
                             "amount": amount, "paid_on": paid_on.isoformat(), "by": actor.user_id})
    return _invoice_view(data, invoice, as_of)


# ---------- 감사 기록 ----------

def list_audit(actor: Actor, data: dict) -> list[dict]:
    actor.require("audit.read")
    if actor.all_sites:
        return list(data["audit"])
    out = []
    for entry in data["audit"]:
        resident = next((r for r in data["residents"] if r["id"] == entry["target"]), None)
        if resident and actor.sees_site(resident["site_id"]):
            out.append(entry)
    return out


# ---------- 민원(VOC) ----------

def prepare_voc(actor: Actor, data: dict, resident_id: str, text: str) -> tuple[dict, str]:
    """권한·범위를 확인하고 AI에 보낼 가린 문장을 만든다. AI 호출은 잠금 밖에서 한다."""
    actor.require("voc.write")
    resident = _resident_scoped(actor, data, resident_id)
    if resident["status"] != "resident":
        raise Invalid("입주 중인 입주자의 민원만 접수할 수 있습니다.")
    text = text.strip()
    if not text:
        raise Invalid("민원 내용을 입력해 주세요.")
    if len(text) > voc.MAX_CHARS:
        raise Invalid(f"민원은 {voc.MAX_CHARS}자까지 입력할 수 있습니다.")
    return resident, voc.redact(text, people_names(data["residents"], data["users"]))


def create_voc(actor: Actor, data: dict, resident: dict, text: str, redacted: str, result: dict, source: str,
               now: datetime) -> dict:
    data["seq"]["voc"] += 1
    _, units = _names(data)
    item = {
        "id": f"voc-{data['seq']['voc']}", "site_id": resident["site_id"], "resident_id": resident["id"],
        "unit_number": units.get(resident["unit_id"]), "text": text.strip(), "redacted": redacted,
        **result, "source": source, "assignee_role": voc.ROUTE[result["category"]], "status": "received",
        "created_at": now.isoformat(timespec="seconds"), "created_by": actor.user_id,
        "created_by_name": f"{actor.name} ({ROLE_SHORT.get(actor.role, actor.role)})",
        "reopened": 0,
        "history": [{"at": now.isoformat(timespec="seconds"), "by": actor.name, "from": None, "to": "received",
                     "action": "접수", "reason": None}],
    }
    data["vocs"].append(item)
    return _voc_view(actor, item)


ROLE_SHORT = {"hq_admin": "본사", "site_manager": "매니저", "care_staff": "케어 직원", "accountant": "회계",
              "guardian": "보호자"}
URGENCY_ORDER = {"high": 0, "normal": 1, "low": 2}


def _voc_view(actor: Actor, item: dict) -> dict:
    """연락처 원문 권한이 있거나 내 가족 민원이면 원문, 아니면 가린 문장을 보여 준다."""
    original = actor.can("pii.read") or actor.voc_scope == "own"
    out = {k: v for k, v in item.items() if k not in ("text", "redacted")}
    out["text"] = item["text"] if original else item["redacted"]
    out["masked"] = not original and item["text"] != item["redacted"]
    out["category_label"] = voc.CATEGORIES[item["category"]]
    out["urgency_label"] = voc.URGENCY[item["urgency"]]
    out["status_label"] = voc.STATUS_LABELS[item["status"]]
    out["assignee_label"] = ROLE_SHORT.get(item["assignee_role"], item["assignee_role"])
    out["next"] = [{"to": to, "label": label, "reason": needs}
                   for (frm, to), (label, needs) in voc.TRANSITIONS.items()
                   if frm == item["status"]] if actor.can("voc.manage") else []
    out["history"] = [{**h, "from_label": voc.STATUS_LABELS.get(h["from"]) if h["from"] else None,
                       "to_label": voc.STATUS_LABELS[h["to"]]} for h in item["history"]]
    return out


def list_vocs(actor: Actor, data: dict, site_id: str) -> list[dict]:
    actor.require("voc.read")
    _site(actor, data, site_id)
    items = [v for v in data["vocs"] if v["site_id"] == site_id and actor.sees_voc(v)]
    items.sort(key=lambda v: v["created_at"], reverse=True)
    items.sort(key=lambda v: (v["status"] == "done", URGENCY_ORDER[v["urgency"]]))
    return [_voc_view(actor, v) for v in items]


def voc_status(actor: Actor, data: dict, voc_id: str, to: str, reason: str | None, now: datetime) -> dict:
    """상태를 바꾸고 이력을 남긴다. 되돌리기·다시 열기는 사유가 있어야 한다."""
    actor.require("voc.manage")
    item = _get(data, "vocs", voc_id)
    if not actor.sees_voc(item):
        raise NotFound(voc_id)
    rule = voc.TRANSITIONS.get((item["status"], to))
    if rule is None:
        raise Invalid(f"'{voc.STATUS_LABELS[item['status']]}' 상태에서 '{voc.STATUS_LABELS.get(to, to)}'(으)로 바꿀 수 없습니다.")
    label, needs_reason = rule
    reason = (reason or "").strip()
    if needs_reason and not reason:
        raise Invalid(f"'{label}'에는 사유가 필요합니다.")
    if len(reason) > voc.REASON_MAX:
        raise Invalid(f"사유는 {voc.REASON_MAX}자까지 입력할 수 있습니다.")
    item["history"].append({"at": now.isoformat(timespec="seconds"), "by": actor.name, "from": item["status"], "to": to,
                            "action": label, "reason": reason or None})
    if (item["status"], to) == ("done", "in_progress"):
        item["reopened"] += 1
    item["status"] = to
    return _voc_view(actor, item)


# ---------- 출입 시스템 연동 ----------

def _enqueue(data: dict, kind: str, contract: dict, due: date, today: date, now: datetime | None) -> dict:
    data["seq"]["evt"] += 1
    resident = _get(data, "residents", contract["resident_id"])
    _, units = _names(data)
    event = integration.new_event(data["seq"]["evt"], kind, contract, resident, units[contract["unit_id"]], due)
    data["events"].append(event)
    if integration.due(event, today):
        integration.deliver(event, data["access_system"], now or datetime.combine(today, time(9)))
    return event


def _event_view(event: dict) -> dict:
    return {**event, "kind_label": integration.KIND_LABELS[event["kind"]],
            "status_label": integration.STATUS_LABELS[event["status"]]}


def list_integration(actor: Actor, data: dict, site_id: str) -> dict:
    actor.require("integration.read")
    _site(actor, data, site_id)
    residents, _ = _names(data)
    site_residents = {r["id"] for r in data["residents"] if r["site_id"] == site_id}
    state = data["access_system"]
    events = [e for e in data["events"] if e["site_id"] == site_id]
    keys = {e["idempotency_key"] for e in events}
    cards = [{"resident_id": rid, "resident_name": residents.get(rid), **card}
             for rid, card in state["credentials"].items() if rid in site_residents]
    return {
        "events": [_event_view(e) for e in reversed(events)],
        "credentials": sorted(cards, key=lambda c: c.get("unit", "")),
        "receiver_log": [entry for entry in reversed(state["log"]) if entry["key"] in keys],
        "fail_next": state["fail_next"],
    }


def process_integration(actor: Actor, data: dict, site_id: str, as_of: date, now: datetime) -> dict:
    """기준일까지 예약된 이벤트와 재시도 대기 이벤트를 보낸다 (데모라 재시도 대기 시간은 건너뛴다)."""
    actor.require("integration.write")
    _site(actor, data, site_id)
    sent = []
    for event in data["events"]:
        if event["site_id"] == site_id and integration.due(event, as_of):
            integration.deliver(event, data["access_system"], now)
            sent.append({"id": event["id"], "status": event["status"]})
    return {"sent": sent}


def resend_event(actor: Actor, data: dict, event_id: str, now: datetime) -> dict:
    """전달된 이벤트를 같은 Idempotency-Key 로 한 번 더 보낸다. 받는 쪽이 중복으로 무시하는지 보는 용도."""
    actor.require("integration.write")
    event = _site_scoped(actor, _get(data, "events", event_id))
    if event["status"] != "delivered":
        raise Invalid("전달 완료된 이벤트만 다시 보낼 수 있습니다.")
    code, message = integration.send(event, data["access_system"], now)
    return {"code": code, "message": message}


def set_fail_next(actor: Actor, data: dict, count: int) -> dict:
    actor.require("integration.write")
    data["access_system"]["fail_next"] = count
    return {"fail_next": count}


# ---------- 회계 내보내기·마감 ----------

def ledger_view(actor: Actor, data: dict, site_id: str, month: str) -> dict:
    actor.require("ledger.export")
    _site(actor, data, site_id)
    residents, _ = _names(data)
    invoices = [i for i in data["invoices"] if i["site_id"] == site_id]
    ids = {i["id"] for i in invoices}
    payments = [p for p in data["payments"] if p["invoice_id"] in ids]
    rows = ledger.journal(month, invoices, payments, residents)
    closed = next((c for c in data["closed"] if c["site_id"] == site_id and c["month"] == month), None)
    return {"month": month, "rows": rows, "totals": ledger.totals(rows), "closed": closed}


def ledger_csv(actor: Actor, data: dict, site_id: str, month: str) -> str:
    view = ledger_view(actor, data, site_id, month)
    if not view["totals"]["balanced"]:
        raise Invalid("차변과 대변 합계가 맞지 않아 내보낼 수 없습니다.")
    return ledger.to_csv(view["rows"])


def close_month(actor: Actor, data: dict, site_id: str, month: str, now: datetime) -> dict:
    """마감한 달은 청구 실행·수납·서비스 이용 기록을 막는다."""
    actor.require("ledger.close")
    _site(actor, data, site_id)
    _require_open(data, site_id, month)
    view = ledger_view(actor, data, site_id, month)
    if not view["rows"]:
        raise Invalid(f"{month}에 청구나 수납이 없어 마감할 내용이 없습니다.")
    if not view["totals"]["balanced"]:
        raise Invalid("차변과 대변 합계가 맞지 않아 마감할 수 없습니다.")
    data["closed"].append({"site_id": site_id, "month": month, "at": now.isoformat(timespec="seconds"),
                           "by": actor.name})
    return ledger_view(actor, data, site_id, month)


__all__ = ["Forbidden", "Invalid", "NotFound"]
