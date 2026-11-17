"""구독·고정지출 분석 (I/O 없음). 거래내역 → 반복 결제 묶음 → 서비스 정보 붙이기 → 중복·절감 후보·결제 예정.

서비스 정보의 출처(source)는 dictionary(알려진 서비스 사전) | ai(Claude 정리 결과) | rule(정보 없음, 가맹점명 그대로)
이고, 사람이 확인하면 review 가 confirm/reject 로 남는다. reject 한 묶음은 합계·중복·절감 계산에서 뺀다.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import cancel, detect, merchants

UPCOMING_DAYS = 30
ALERT_DAYS = 3
RECENT_TRIAL_DAYS = 90
KIND_LABELS = {"subscription": "구독", "fixed": "고정지출"}
CADENCE_LABELS = {"monthly": "매월", "weekly": "매주", "yearly": "매년"}
AMOUNT_LABELS = {"fixed": "고정 금액", "variable": "매달 달라짐", "fx": "해외결제(환율 영향)"}
SIGNAL_LABELS = {"price_increase": "가격 인상", "trial_conversion": "무료체험 → 유료 전환", "fx": "환율 영향",
                 "likely_cancelled": "해지 추정", "duplicate": "같은 종류 중복"}
SOURCE_LABELS = {"dictionary": "서비스 사전", "ai": "AI 정리", "rule": "가맹점명 그대로"}


class Invalid(Exception):
    pass


def series_id(key: str, index: int) -> str:
    return "sr-" + hashlib.sha1(f"{key}#{index}".encode()).hexdigest()[:10]


SUFFIX_RE = re.compile(r"\s*(자동이체|자동납부|정기결제|월회비|보험료|요금)$")


def _clean_name(raw: str) -> str:
    """화면에 보일 이름: 결제대행 접두어와 '자동이체'·'요금' 같은 꼬리말을 뗀다."""
    return SUFFIX_RE.sub("", merchants.PREFIX_RE.sub("", raw.strip())).strip()


def _info(key: str, cache: dict[str, dict]) -> dict | None:
    """사전 정보, 없으면 AI 정리 결과(분류만 쓰고 주기는 거래로 판단)."""
    known = merchants.lookup(key)
    if known:
        return {**known, "source": "dictionary"}
    ai = cache.get(key)
    if ai and ai["recurring"]:
        return {"service": ai["service"], "category": ai["category"], "kind": ai["kind"], "cadence": None,
                "source": "ai", "reason": ai["reason"]}
    return None


def find_series(transactions: list[dict], as_of: date, cache: dict[str, dict] | None = None
                ) -> tuple[list[dict], dict[str, list[dict]]]:
    """(반복 결제 묶음 목록, 묶음 id별 거래). 같은 서비스의 다른 표기는 merchants.canonical 로 한 묶음이 된다.
    정보가 없는 묶음은 info=None 으로 둔다."""
    cache = cache or {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in detect.effective(transactions):
        key = merchants.normalize(t["merchant_raw"])
        if key in cache and not cache[key]["recurring"]:
            continue
        groups[merchants.canonical(key, cache)].append({**t, "_key": key})
    found = []
    for canon, items in groups.items():
        latest = items[-1]
        key = latest["_key"]
        info = _info(key, cache)
        aliases = sorted({t["merchant_raw"] for t in items})
        whole = detect.analyze(items, info, as_of)
        parts = [(0, whole)] if whole else [
            (i, detect.analyze(c, info, as_of)) for i, c in enumerate(detect.split_by_amount(items))]
        for index, result in parts:
            if result is None:
                continue
            found.append({"id": series_id(canon, index), "canonical": canon, "key": key,
                          "keys": sorted({t["_key"] for t in items}), "merchant_raw": latest["merchant_raw"],
                          "aliases": aliases, "info": info, **result})
    return found, groups


def unknown_candidates(series: list[dict], cache: dict[str, dict]) -> list[dict]:
    """AI에 물어볼 가맹점: 사전에 없고 아직 정리 결과가 없는 반복 결제."""
    seen, out = set(), []
    for s in series:
        if s["info"] is None and s["key"] not in cache and s["key"] not in seen:
            seen.add(s["key"])
            out.append({"key": s["key"], "merchant": s["merchant_raw"], "amount": s["expected_amount"],
                        "cadence": s["cadence"]})
    return out


def _describe(s: dict) -> dict:
    info = s["info"]
    if info:
        return {"service": info["service"] or _clean_name(s["merchant_raw"]), "category": info["category"],
                "kind": info["kind"], "source": info["source"], "reason": info.get("reason")}
    return {"service": _clean_name(s["merchant_raw"]), "category": "other", "kind": "subscription", "source": "rule",
            "reason": None}


def analyze(data: dict, persona_id: str, cache: dict[str, dict], now: datetime | None = None) -> dict:
    """now: 해지 요청 처리 시각 판단용 (없으면 처리 중 상태를 그대로 둔다)."""
    persona = next((p for p in data["personas"] if p["id"] == persona_id), None)
    if persona is None:
        raise Invalid("없는 사용자입니다.")
    as_of = date.fromisoformat(data["as_of"])
    txs = data["transactions"][persona_id]
    found, _ = find_series(txs, as_of, cache)
    reviews = data["overrides"][persona_id]
    cancels = data["cancellations"][persona_id]
    if now is not None:
        for entry in cancels.values():
            cancel.refresh(entry, now)

    rows = []
    for s in found:
        desc = _describe(s)
        review = reviews.get(s["id"])
        confidence = 99 if review == "confirm" else s["confidence"]
        rows.append({
            "id": s["id"], "key": s["key"], "canonical": s["canonical"], "merchant_raw": s["merchant_raw"],
            "aliases": s["aliases"], **desc,
            "category_label": merchants.label(desc["category"]), "kind_label": KIND_LABELS[desc["kind"]],
            "source_label": SOURCE_LABELS[desc["source"]], "review": review,
            "cadence": s["cadence"], "cadence_label": CADENCE_LABELS[s["cadence"]], "count": s["count"],
            "first_date": s["first_date"], "last_date": s["last_date"], "next_date": s["next_date"],
            "amount_type": s["amount_type"], "amount_label": AMOUNT_LABELS[s["amount_type"]],
            "expected_amount": s["expected_amount"], "last_amount": s["last_amount"], "currency": s["currency"],
            "monthly_equivalent": s["monthly_equivalent"], "status": s["status"], "confidence": confidence,
            "signals": [{**sig, "label": SIGNAL_LABELS[sig["type"]]} for sig in s["signals"]],
            "transaction_ids": s["transaction_ids"],
        })
        row = rows[-1]
        row["cancel_method"] = cancel.method_for(row)
        row["cancel"] = cancel.view(cancels.get(s["id"]), row)

    _disambiguate(rows)
    def done(r: dict) -> bool:
        return bool(r["cancel"]) and r["cancel"]["status"] == "done"

    live = [r for r in rows if r["status"] == "active" and r["review"] != "reject" and not done(r)]
    _mark_duplicates(live)
    rows.sort(key=lambda r: (done(r), r["review"] == "reject", r["status"] != "active", -r["monthly_equivalent"]))
    upcoming = _upcoming(live, as_of)

    sub_total = sum(r["monthly_equivalent"] for r in live if r["kind"] == "subscription")
    fixed_total = sum(r["monthly_equivalent"] for r in live if r["kind"] == "fixed")
    series_of = {tid: r["id"] for r in rows for tid in r["transaction_ids"]}
    return {
        "persona": persona, "as_of": data["as_of"], "period": data["period"],
        "summary": {"monthly_total": sub_total + fixed_total, "subscription_monthly": sub_total,
                    "fixed_monthly": fixed_total, "yearly_total": (sub_total + fixed_total) * 12,
                    "subscription_count": sum(1 for r in live if r["kind"] == "subscription"),
                    "fixed_count": sum(1 for r in live if r["kind"] == "fixed"),
                    "saved_monthly": sum(r["monthly_equivalent"] for r in rows if done(r))},
        "series": rows,
        "upcoming": upcoming,
        "alerts": _alerts(upcoming, as_of),
        "savings": (savings := _savings(live, as_of)),
        "savings_total": _savings_total(live, savings),
        "ai_pending": len(unknown_candidates(found, cache)),
        "transactions": [{**t, "series_id": series_of.get(t["id"])}
                         for t in sorted(txs, key=lambda t: (t["date"], t["id"]), reverse=True)],
    }


def _disambiguate(rows: list[dict]) -> None:
    """서비스명이 같은 묶음(휴대폰 회선 2개 등)은 금액을 붙여 구분한다."""
    names = defaultdict(list)
    for r in rows:
        names[r["service"]].append(r)
    for same in names.values():
        if len(same) > 1:
            for r in same:
                r["service"] = f"{r['service']} ({r['expected_amount']:,}원)"


def _mark_duplicates(live: list[dict]) -> None:
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in live:
        if r["category"] in merchants.DUPLICATE_SENSITIVE:
            by_category[r["category"]].append(r)
    for category, items in by_category.items():
        if len(items) < 2:
            continue
        for r in items:
            others = ", ".join(o["service"] for o in items if o is not r)
            r["signals"].append({"type": "duplicate", "label": SIGNAL_LABELS["duplicate"], "date": None,
                                 "detail": f"{merchants.label(category)} 구독이 {len(items)}개 (함께: {others})"})


def _upcoming(live: list[dict], as_of: date) -> list[dict]:
    end = as_of + timedelta(days=UPCOMING_DAYS)
    out = []
    for r in live:
        d = date.fromisoformat(r["next_date"])
        while d <= end:
            if d > as_of:
                out.append({"date": d.isoformat(), "series_id": r["id"], "service": r["service"],
                            "amount": r["expected_amount"], "amount_type": r["amount_type"], "kind": r["kind"]})
            if r["cadence"] == "weekly":
                d += timedelta(days=7)
            elif r["cadence"] == "monthly":
                d = detect.add_months(d, 1)
            else:
                break
    return sorted(out, key=lambda u: (u["date"], -u["amount"]))


def _alerts(upcoming: list[dict], as_of: date) -> list[dict]:
    """결제 전 알림: 기준일 다음 날부터 ALERT_DAYS 일 안에 나갈 결제."""
    out = []
    for u in upcoming:
        d_day = (date.fromisoformat(u["date"]) - as_of).days
        if d_day <= ALERT_DAYS:
            out.append({**u, "d_day": d_day})
    return out


def _savings(live: list[dict], as_of: date) -> list[dict]:
    """절감 후보. 금액은 '최소한 이만큼' 기준이다 (중복은 가장 비싼 것 하나만 남길 때)."""
    out = []
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in live:
        if r["category"] in merchants.DUPLICATE_SENSITIVE:
            by_category[r["category"]].append(r)
    for category, items in by_category.items():
        if len(items) >= 2:
            ranked = sorted(items, key=lambda r: -r["monthly_equivalent"])
            out.append({"type": "duplicate", "title": f"{merchants.label(category)} 구독 {len(items)}개 정리",
                        "services": [r["service"] for r in items], "series_ids": [r["id"] for r in ranked[1:]],
                        "monthly": sum(r["monthly_equivalent"] for r in ranked[1:]),
                        "detail": "하나만 남기면 아래 금액부터 아낄 수 있어요 (가장 비싼 것을 남길 때 기준)."})
    for r in live:
        trial = next((s for s in r["signals"] if s["type"] == "trial_conversion"), None)
        if trial and (as_of - date.fromisoformat(trial["date"])).days <= RECENT_TRIAL_DAYS:
            out.append({"type": "trial", "title": f"{r['service']} 체험 후 유료 전환", "services": [r["service"]],
                        "series_ids": [r["id"]],
                        "monthly": r["monthly_equivalent"],
                        "detail": f"{trial['date']}부터 정상 요금이 나가고 있어요. 계속 쓸지 확인해 보세요."})
        up = next((s for s in r["signals"] if s["type"] == "price_increase"), None)
        if up:
            out.append({"type": "price", "title": f"{r['service']} 요금 인상", "services": [r["service"]],
                        "series_ids": [],
                        "monthly": up["to"] - up["from"],
                        "detail": f"{up['date']}부터 {up['detail']}. 요금제를 낮추거나 다른 서비스로 바꿀지 비교해 보세요."})
    out.sort(key=lambda s: -s["monthly"])
    return out


def _savings_total(live: list[dict], savings: list[dict]) -> int:
    """해지 후보로 든 구독을 한 번씩만 더한 월 금액 (중복 정리와 체험 전환에 같은 구독이 들어가도 한 번)."""
    ids = {sid for s in savings for sid in s["series_ids"]}
    return sum(r["monthly_equivalent"] for r in live if r["id"] in ids)


def cancel_action(data: dict, persona_id: str, sid: str, action: str, cache: dict[str, dict], now: datetime) -> dict:
    """해지 요청(request) / 직접 해지했어요(confirm) / 되돌리기(undo)."""
    view = analyze(data, persona_id, cache, now)
    row = next((r for r in view["series"] if r["id"] == sid), None)
    if row is None:
        raise Invalid("없는 항목입니다.")
    cancels = data["cancellations"][persona_id]
    try:
        if action == "request":
            if sid in cancels:
                raise Invalid("이미 해지를 진행 중이에요.")
            cancels[sid] = cancel.start(row, now)
        elif action == "confirm":
            if sid not in cancels:
                raise Invalid("해지를 시작하지 않은 항목이에요.")
            cancel.confirm_done(cancels[sid], now)
        else:
            cancels.pop(sid, None)
    except cancel.CancelError as exc:
        raise Invalid(str(exc)) from None
    return analyze(data, persona_id, cache, now)


def review(data: dict, persona_id: str, sid: str, decision: str, cache: dict[str, dict]) -> dict:
    view = analyze(data, persona_id, cache)
    if not any(r["id"] == sid for r in view["series"]):
        raise Invalid("없는 항목입니다.")
    if decision == "reset":
        data["overrides"][persona_id].pop(sid, None)
    else:
        data["overrides"][persona_id][sid] = decision
    return analyze(data, persona_id, cache)
