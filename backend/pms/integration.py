"""출입 시스템 연동 (I/O 없음, 받는 쪽도 가상).

계약이 입주로 바뀌면 출입 권한 발급(access.grant), 해지되면 퇴거일에 회수(access.revoke) 이벤트를 아웃박스에 쌓고 보낸다.
- 본문은 정렬한 JSON, 서명은 HMAC-SHA256(비밀키, "타임스탬프." + 본문). 받는 쪽은 서명을 확인한다.
- Idempotency-Key 는 계약·이벤트 종류마다 하나다. 같은 키가 다시 오면 받는 쪽은 처리하지 않고 '이미 처리함'으로 답한다.
- 실패하면 1분·5분·30분 간격으로 다시 보내고, 4번째도 실패하면 '실패(수동 확인)'로 남긴다.
  데모에서는 '처리' 버튼이 대기 시간을 건너뛰고 바로 다시 보낸다.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timedelta

BACKOFF_MIN = (1, 5, 30)
MAX_ATTEMPTS = len(BACKOFF_MIN) + 1
KIND_LABELS = {"access.grant": "출입 권한 발급", "access.revoke": "출입 권한 회수"}
STATUS_LABELS = {"scheduled": "예약", "pending": "보낼 차례", "retrying": "재시도 대기", "delivered": "전달 완료",
                 "dead": "실패(수동 확인)"}
OPEN = ("scheduled", "pending", "retrying")


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sign(secret: str, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign(secret, timestamp, body), signature or "")


def new_event(seq: int, kind: str, contract: dict, resident: dict, unit_number: str, due: date) -> dict:
    return {
        "id": f"evt-{seq:04d}", "site_id": contract["site_id"], "kind": kind,
        "idempotency_key": f"{kind}:{contract['id']}",
        "payload": {"type": kind, "contract_id": contract["id"], "resident_id": resident["id"],
                    "unit": unit_number, "effective_date": due.isoformat()},
        "scheduled_for": due.isoformat(), "status": "scheduled", "attempts": [], "next_attempt_at": None,
    }


def receive(state: dict, headers: dict, body: bytes, at: datetime) -> tuple[int, str]:
    """가상 출입 시스템. 실제 업체 API 자리에 들어가는 받는 쪽."""
    if not verify(state["secret"], headers.get("X-Timestamp", ""), body, headers.get("X-Signature", "")):
        result = (401, "서명이 맞지 않습니다")
    elif state.get("fail_next", 0) > 0:
        state["fail_next"] -= 1
        result = (503, "출입 시스템 점검 중 (데모에서 일부러 실패)")
    elif headers.get("Idempotency-Key") in state["seen_keys"]:
        result = (200, "이미 처리한 요청입니다 (중복 무시)")
    else:
        payload = json.loads(body)
        card = state["credentials"].setdefault(payload["resident_id"], {"card": f"CARD-{payload['unit']}", "status": "none"})
        card["status"] = "active" if payload["type"] == "access.grant" else "revoked"
        card["unit"] = payload["unit"]
        card["updated_at"] = at.isoformat(timespec="seconds")
        state["seen_keys"].append(headers["Idempotency-Key"])
        result = (200, "처리했습니다")
    state["log"].append({"at": at.isoformat(timespec="seconds"), "key": headers.get("Idempotency-Key"),
                         "code": result[0], "message": result[1]})
    del state["log"][:-30]
    return result


def send(event: dict, state: dict, at: datetime, secret: str | None = None) -> tuple[int, str]:
    body = canonical(event["payload"])
    timestamp = str(int(at.timestamp()))
    headers = {"Idempotency-Key": event["idempotency_key"], "X-Timestamp": timestamp,
               "X-Signature": sign(state["secret"] if secret is None else secret, timestamp, body)}
    return receive(state, headers, body, at)


def deliver(event: dict, state: dict, at: datetime) -> dict:
    """이벤트를 한 번 보내고 결과에 따라 상태를 바꾼다."""
    code, message = send(event, state, at)
    event["attempts"].append({"at": at.isoformat(timespec="seconds"), "code": code, "message": message})
    if 200 <= code < 300:
        event["status"], event["next_attempt_at"] = "delivered", None
    elif len(event["attempts"]) >= MAX_ATTEMPTS:
        event["status"], event["next_attempt_at"] = "dead", None
    else:
        wait = BACKOFF_MIN[len(event["attempts"]) - 1]
        event["status"] = "retrying"
        event["next_attempt_at"] = (at + timedelta(minutes=wait)).isoformat(timespec="seconds")
    return event


def due(event: dict, as_of: date) -> bool:
    return event["status"] in OPEN and date.fromisoformat(event["scheduled_for"]) <= as_of
