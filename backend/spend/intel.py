"""가맹점 사전(머천트 인텔리전스) 현황 (I/O 없음).

가상 사용자 3명의 거래 전체를 놓고, 반복 결제로 잡힌 가맹점을 서비스(묶음 id) 단위로 모아
- 거래내역에 찍힌 여러 표기(별칭)와 정리한 key
- 정보 출처: 서비스 사전 / AI 정리 / 정리 안 됨, AI 근거
- 사용자 확인(제보): 맞아요·구독 아님 건수. '구독 아님' 제보가 2건 이상이고 '맞아요'보다 많으면 검수 대기로 표시
를 보여 준다. 제보는 바로 사전을 바꾸지 않는다 (실서비스라면 검수 뒤 사전에 반영).
"""
from __future__ import annotations

from datetime import date

from . import merchants
from .service import SOURCE_LABELS, _clean_name, find_series

REVIEW_MIN_REPORTS = 2


def registry(data: dict, cache: dict[str, dict], reports: dict[str, dict[str, set]]) -> dict:
    as_of = date.fromisoformat(data["as_of"])
    rows: dict[str, dict] = {}
    general = set()
    for persona in data["personas"]:
        txs = data["transactions"][persona["id"]]
        found, groups = find_series(txs, as_of, cache)
        recurring = {s["canonical"] for s in found}
        for canon, items in groups.items():
            if canon not in recurring:
                general.add(canon)
        for s in found:
            row = rows.setdefault(s["canonical"], {
                "canonical": s["canonical"], "keys": set(), "aliases": set(), "personas": set(),
                "info": s["info"], "key": s["key"],
            })
            row["keys"].update(s["keys"])
            row["aliases"].update(s["aliases"])
            row["personas"].add(persona["name"])
    out = []
    for canon, row in rows.items():
        info = row["info"]
        source = info["source"] if info else "rule"
        votes = reports.get(canon, {})
        confirm, reject = len(votes.get("confirm", ())), len(votes.get("reject", ()))
        out.append({
            "canonical": canon,
            "service": info["service"] if info and info["service"] else _clean_name(sorted(row["aliases"])[-1]),
            "category_label": merchants.label(info["category"]) if info else merchants.label("other"),
            "source": source, "source_label": SOURCE_LABELS[source],
            "reason": info.get("reason") if info else None,
            "aliases": sorted(row["aliases"]), "keys": sorted(row["keys"]), "personas": sorted(row["personas"]),
            "reports": {"confirm": confirm, "reject": reject},
            "needs_review": reject >= REVIEW_MIN_REPORTS and reject > confirm,
        })
    out.sort(key=lambda r: ({"dictionary": 0, "ai": 1, "rule": 2}[r["source"]], r["service"]))
    by_source = {s: sum(1 for r in out if r["source"] == s) for s in ("dictionary", "ai", "rule")}
    total = len(out)
    return {
        "merchants": out,
        "stats": {"recurring_merchants": total, **by_source,
                  "coverage_pct": round(100 * (total - by_source["rule"]) / total) if total else 100,
                  "alias_merchants": sum(1 for r in out if len(r["aliases"]) > 1),
                  "general_merchants": len(general - set(rows))},
    }
