"""해지 흐름 (I/O 없음). 실제 서비스에 해지를 요청하지 않는 가상 처리다.

- 고정지출(통신·보험·관리비·공과금)은 해지 대상이 아니다 (요금제 변경은 각 회사에서).
- 서비스 사전에 있는 구독: '간편해지(가상)' — 요청하면 처리 중이 되고, 몇 초 뒤 완료된다.
- 그 밖의 구독: '해지 방법 안내' — 일반적인 해지 순서를 보여 주고, 사용자가 '해지했어요'를 누르면 완료로 본다.
- 해지 완료된 구독은 합계·중복·결제 예정·절감 후보에서 빠지고, '아낀 돈'에 더해진다.
- '되돌리기'로 언제든 원래대로 돌릴 수 있다 (데모).
"""
from __future__ import annotations

from datetime import datetime, timedelta

PROCESS_SECONDS = 4
STATUS_LABELS = {"processing": "해지 요청 처리 중", "guide": "해지 방법 안내 중", "done": "해지 완료"}
METHOD_LABELS = {"easy": "간편해지(가상 처리)", "guide": "해지 방법 안내"}


class CancelError(Exception):
    pass


def method_for(row: dict) -> str | None:
    if row["kind"] != "subscription":
        return None
    return "easy" if row["source"] == "dictionary" else "guide"


def guide_steps(row: dict) -> list[str]:
    """서비스마다 실제 메뉴 이름은 다르므로 일반적인 순서만 안내한다."""
    return [
        f"{row['service']} 앱이나 웹사이트에 로그인합니다.",
        "결제·이용권(멤버십) 메뉴에서 '해지' 또는 '자동결제 해지'를 고릅니다.",
        f"다음 결제일({row['next_date']}) 전에 해지하면 다음 결제가 나가지 않아요.",
        "해지 완료 화면이나 메일을 보관해 두세요.",
    ]


def start(row: dict, now: datetime) -> dict:
    method = method_for(row)
    if method is None:
        raise CancelError("고정지출은 해지 대상이 아니에요. 요금제 변경은 각 회사에서 할 수 있어요.")
    if row["status"] != "active":
        raise CancelError("이미 결제가 멈춘 항목이에요.")
    entry = {"method": method, "requested_at": now.isoformat(timespec="seconds")}
    if method == "easy":
        entry.update(status="processing", due_at=(now + timedelta(seconds=PROCESS_SECONDS)).isoformat(timespec="seconds"))
    else:
        entry.update(status="guide")
    return entry


def refresh(entry: dict, now: datetime) -> dict:
    if entry["status"] == "processing" and now >= datetime.fromisoformat(entry["due_at"]):
        entry["status"], entry["done_at"] = "done", entry["due_at"]
    return entry


def confirm_done(entry: dict, now: datetime) -> dict:
    if entry["status"] != "guide":
        raise CancelError("안내 중인 해지만 직접 완료로 바꿀 수 있어요.")
    entry["status"], entry["done_at"] = "done", now.isoformat(timespec="seconds")
    return entry


def view(entry: dict | None, row: dict) -> dict | None:
    if entry is None:
        return None
    out = {**entry, "status_label": STATUS_LABELS[entry["status"]], "method_label": METHOD_LABELS[entry["method"]]}
    if entry["method"] == "guide":
        out["steps"] = guide_steps(row)
    return out
