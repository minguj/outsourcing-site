"""역할 × 사업장 권한 (I/O 없음).

- 역할은 할 수 있는 일(권한)을, 배정은 볼 수 있는 사업장 범위를 정한다. 둘 다 통과해야 한다.
- 범위 밖 데이터는 '없음'으로 응답한다. 존재 여부도 알려 주지 않는다.
- 연락처는 pii.read, 건강·돌봄 정보는 health.read 가 있어야 원문을 본다. 원문을 보면 감사 기록을 남긴다.
- 민원은 voc_scope 로 범위를 한 번 더 좁힌다: all(사업장 전체), assigned(내 역할에 배정된 민원), own(내 가족 민원).
"""
from __future__ import annotations

from dataclasses import dataclass

ROLES = {
    "hq_admin": {
        "label": "본사 관리자",
        "all_sites": True,
        "perms": {"site.read", "unit.read", "contract.read", "contract.write",
                  "billing.read", "resident.read", "pii.read", "audit.read",
                  "voc.read", "integration.read", "ledger.export", "ledger.close"},
        "voc_scope": "all",
    },
    "site_manager": {
        "label": "사업장 매니저",
        "perms": {"site.read", "unit.read", "contract.read", "contract.write", "billing.read", "billing.write",
                  "resident.read", "pii.read", "health.read", "service.write", "audit.read",
                  "voc.read", "voc.write", "voc.manage", "integration.read", "integration.write"},
        "voc_scope": "all",
    },
    "care_staff": {
        "label": "현장 케어 직원",
        "perms": {"site.read", "unit.read", "resident.read", "health.read", "service.write",
                  "voc.read", "voc.write", "voc.manage"},
        "voc_scope": "assigned",
    },
    "accountant": {
        "label": "회계 담당",
        "perms": {"site.read", "unit.read", "contract.read", "billing.read", "billing.write", "resident.read", "pii.read",
                  "voc.read", "voc.manage", "ledger.export", "ledger.close"},
        "voc_scope": "assigned",
    },
    "guardian": {
        "label": "보호자",
        "own_residents_only": True,
        "perms": {"site.read", "billing.read", "resident.read", "voc.read", "voc.write"},
        "voc_scope": "own",
    },
}


class Forbidden(Exception):
    """권한이 없다 (403)."""


class NotFound(Exception):
    """없거나 범위 밖이다 (404)."""


@dataclass(frozen=True)
class Actor:
    user_id: str
    name: str
    role: str
    site_ids: frozenset[str]
    resident_ids: frozenset[str] = frozenset()

    @property
    def perms(self) -> set[str]:
        return ROLES[self.role]["perms"]

    @property
    def all_sites(self) -> bool:
        return bool(ROLES[self.role].get("all_sites"))

    @property
    def own_residents_only(self) -> bool:
        return bool(ROLES[self.role].get("own_residents_only"))

    def can(self, perm: str) -> bool:
        return perm in self.perms

    def require(self, perm: str) -> None:
        if not self.can(perm):
            raise Forbidden(perm)

    def sees_site(self, site_id: str) -> bool:
        return self.all_sites or site_id in self.site_ids

    @property
    def voc_scope(self) -> str:
        return ROLES[self.role].get("voc_scope", "all")

    def sees_voc(self, voc: dict) -> bool:
        if not self.sees_site(voc["site_id"]):
            return False
        if self.voc_scope == "own":
            return voc["resident_id"] in self.resident_ids
        if self.voc_scope == "assigned":
            return voc["assignee_role"] == self.role
        return True

    def sees_resident(self, resident: dict) -> bool:
        if not self.sees_site(resident["site_id"]):
            return False
        return not self.own_residents_only or resident["id"] in self.resident_ids


def actor_from_user(user: dict) -> Actor:
    return Actor(
        user_id=user["id"], name=user["name"], role=user["role"],
        site_ids=frozenset(user.get("site_ids", [])), resident_ids=frozenset(user.get("resident_ids", [])),
    )


def mask_phone(phone: str) -> str:
    digits = [c for c in phone if c.isdigit()]
    if len(digits) < 8:
        return "***"
    return f"{''.join(digits[:3])}-****-{''.join(digits[-4:])}"


def view_resident(actor: Actor, resident: dict) -> tuple[dict, list[str]]:
    """역할에 맞게 가린 입주자 정보와, 원문으로 보여 준 민감 항목 목록을 돌려준다."""
    revealed: list[str] = []
    out = {k: resident[k] for k in ("id", "site_id", "unit_id", "name", "birth_year", "status")}
    guardian = dict(resident["guardian"])
    if actor.can("pii.read") or actor.own_residents_only:
        out["phone"] = resident["phone"]
        if not actor.own_residents_only:
            revealed.append("phone")
    else:
        out["phone"] = mask_phone(resident["phone"])
        guardian["phone"] = mask_phone(guardian["phone"])
    out["guardian"] = guardian
    if actor.can("health.read"):
        out["care"] = resident["care"]
        revealed.append("care")
    else:
        out["care"] = None
    return out, revealed
