"""규칙 데이터 로더.

법규·조례·고시 값은 코드가 아니라 app/rules/*.yaml 에 있다.
이 모듈은 YAML 을 읽어 엔진이 쓰기 좋은 형태로 바꾸고,
기준일(as_of)에 맞는 규칙 버전을 고른다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .regions import legacy_code
from .trace import Source

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


class RuleNotFound(LookupError):
    pass


def _load(name: str) -> dict[str, Any]:
    with open(RULES_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_optional(name: str) -> dict[str, Any]:
    """조례 일괄 수집 결과(zoning_collected.yaml). 아직 수집 전이면 빈 묶음."""
    return _load(name) if (RULES_DIR / name).exists() else {"ordinances": []}


def _parse_date(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


@dataclass(frozen=True)
class ZoneLimit:
    zone: str
    bcr: float  # 건폐율 %
    far: float  # 용적률 %
    max_floors: int | None
    source: Source


@dataclass(frozen=True)
class ResolvedZoning:
    zone: str
    canonical_zone: str
    national: ZoneLimit
    ordinance: ZoneLimit | None
    use_override_far: tuple[float, Source] | None
    subarea: dict | None = None  # 같은 지자체 안에서 구역에 따라 다른 값 (예: 서울도심 상업지역)
    collected: bool = False  # 조례값이 일괄 수집분(사람 미확인)에서 왔는지


@dataclass(frozen=True)
class Grade:
    grade: str
    label: str
    min_self_sufficiency: float


class RuleBook:
    """기준일 기준으로 고정된 규칙 묶음. 계산 1회에 RuleBook 1개를 쓴다."""

    def __init__(self, as_of: date | None = None) -> None:
        self.as_of = as_of or date.today()
        self.zoning = _load("zoning.yaml")
        self.collected = _load_optional("zoning_collected.yaml")
        self.zeb = _load("zeb.yaml")
        self.assumptions = _load("assumptions.yaml")
        self.equipment = _load("equipment.yaml")

    # ---------- 버전/재현성 ----------
    def fingerprint(self) -> str:
        """규칙 데이터 전체의 해시. 보고서에 찍어 같은 결과를 재현할 수 있게 한다."""
        blob = json.dumps(
            [self.zoning, self.collected.get("ordinances"), self.zeb, self.assumptions, self.equipment],
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def versions(self) -> dict[str, str]:
        return {
            "zoning": self.zoning["national"]["checked_on"],
            "zeb": self._grade_set()["id"],
            "assumptions": self.assumptions["version"],
            "equipment": self.equipment["version"],
            "fingerprint": self.fingerprint(),
            "as_of": self.as_of.isoformat(),
        }

    # ---------- 용도지역 ----------
    def zone_names(self) -> list[str]:
        names = list(self.zoning["national"]["zones"].keys())
        names += list(self.zoning["national"].get("aliases", {}).keys())
        return names

    def resolve_zone(self, zone: str, jurisdiction: str | None, building_use: str) -> ResolvedZoning:
        nat = self.zoning["national"]
        canonical = nat.get("aliases", {}).get(zone, zone)
        if canonical not in nat["zones"]:
            raise RuleNotFound(f"등록되지 않은 용도지역: {zone}")

        nz = nat["zones"][canonical]
        national = ZoneLimit(
            zone=canonical,
            bcr=nz["bcr"],
            far=nz["far"],
            max_floors=None,
            source=Source(
                id=nat["id"],
                title=nat["title"],
                kind="law",
                ref=nat["ref"],
                url=nat.get("url"),
                verified=bool(nz.get("verified", False)),
            ),
        )

        ordinance = None
        override = None
        ord_rule = self._ordinance_for(jurisdiction)
        if ord_rule:
            oz = ord_rule["zones"].get(zone) or ord_rule["zones"].get(canonical)
            if oz:
                collected = bool(ord_rule.get("collected"))
                note = oz.get("note")
                missing = [label for key, label in (("bcr", "건폐율"), ("far", "용적률")) if key not in oz]
                if missing:
                    # 일괄 수집에서 한쪽 값만 뽑힌 경우: 빠진 쪽은 법정 상한으로 채우고 알린다
                    note = f"{'·'.join(missing)}은 조문에서 찾지 못해 법정 상한을 사용" + (f" / {note}" if note else "")
                src = Source(
                    id=ord_rule["id"],
                    title=ord_rule["title"] + (" (자동 수집)" if collected else ""),
                    kind="ordinance",
                    ref=_ordinance_ref(ord_rule),
                    url=ord_rule.get("url"),
                    verified=bool(oz.get("verified", False)),
                    note=note,
                )
                ordinance = ZoneLimit(
                    zone, oz.get("bcr", nz["bcr"]), oz.get("far", nz["far"]), oz.get("max_floors"), src
                )
            uo = ord_rule.get("use_overrides", {}).get(canonical, {}).get(building_use)
            if uo:
                override = (
                    float(uo["far"]),
                    Source(
                        id=f"{ord_rule['id']}:use:{canonical}:{building_use}",
                        title=ord_rule["title"],
                        kind="ordinance",
                        ref=f"{ord_rule['ref']} ({building_use} 별도 기준)",
                        url=ord_rule.get("url"),
                        verified=bool(uo.get("verified", False)),
                        note=uo.get("note"),
                    ),
                )
        subarea = None
        if ord_rule and jurisdiction:
            for sa in ord_rule.get("subareas", []):
                if canonical in sa.get("far", {}) and any(jurisdiction.startswith(j) for j in sa["jurisdictions"]):
                    subarea = {"name": sa["name"], "far": sa["far"][canonical], "note": sa.get("note")}
        return ResolvedZoning(
            zone, canonical, national, ordinance, override, subarea,
            collected=bool(ordinance and ord_rule and ord_rule.get("collected")),
        )

    def _ordinance_for(self, jurisdiction: str | None) -> dict | None:
        if not jurisdiction:
            return None
        # 전남광주통합(2026-07) 뒤 새 코드(12…)는 규칙 파일의 예전 코드(46…·29…)로도 찾는다
        codes = [c for c in (jurisdiction, legacy_code(jurisdiction)) if c]
        candidates = [
            o
            for o in [*self.zoning["ordinances"], *(self.collected.get("ordinances") or [])]
            if any(c.startswith(o["jurisdiction"]) for c in codes)
            and (_parse_date(o.get("effective_from")) or date.min) <= self.as_of
        ]
        if not candidates:
            return None
        # 가장 구체적인(코드가 긴) 관할, 같으면 사람이 확인한 규칙(zoning.yaml)이 일괄 수집분보다 우선, 그다음 최근 시행분
        candidates.sort(
            key=lambda o: (
                len(o["jurisdiction"]),
                not o.get("collected"),
                _parse_date(o.get("effective_from")) or date.min,
            ),
            reverse=True,
        )
        return candidates[0]

    def override_plans(self) -> list[dict]:
        return self.zoning.get("override_plans", [])

    def height_plan_keywords(self) -> list[str]:
        """높이를 제한하지만 높이값은 데이터로 주어지지 않는 지역·지구 (고시문 확인 후 '높이 제한' 입력 필요)."""
        return [p["keyword"] for p in self.override_plans() if p.get("height_related")]

    def land_category_check(self, category: str | None) -> dict | None:
        if not category:
            return None
        for rule in self.zoning.get("land_categories", {}).values():
            if category in rule["values"]:
                return rule
        return None

    def canonical_zone(self, name: str) -> str | None:
        """'제2종 일반주거지역' 같은 표기도 규칙 키로 맞춘다. 용도지역이 아니면 None."""
        key = name.replace(" ", "")
        nat = self.zoning["national"]
        key = nat.get("aliases", {}).get(key, key)
        return key if key in nat["zones"] else None

    # ---------- ZEB ----------
    def _grade_set(self) -> dict:
        sets = [g for g in self.zeb["grade_sets"] if _parse_date(g["effective_from"]) <= self.as_of]
        if not sets:
            raise RuleNotFound(f"{self.as_of} 기준 ZEB 등급 기준이 없습니다")
        return max(sets, key=lambda g: g["effective_from"])

    def zeb_grades(self) -> tuple[list[Grade], Source]:
        gs = self._grade_set()
        grades = [Grade(g["grade"], g["label"], float(g["min_self_sufficiency"])) for g in gs["grades"]]
        grades.sort(key=lambda g: g.min_self_sufficiency, reverse=True)
        src = Source(
            id=gs["id"],
            title=gs["title"],
            kind="notice",
            ref=gs.get("ref"),
            url=gs.get("url"),
            verified=bool(gs.get("verified", False)),
            note=gs.get("note"),
        )
        return grades, src

    def mandate(self, is_public: bool, gfa: float) -> tuple[str | None, Source | None]:
        scope = "public" if is_public else "private"
        hits = [
            m
            for m in self.zeb["mandates"]
            if m["applies_to"] == scope and _parse_date(m["effective_from"]) <= self.as_of and gfa >= m["min_gfa_m2"]
        ]
        if not hits:
            return None, None
        m = max(hits, key=lambda m: m["effective_from"])
        return m["min_grade"], Source(
            id=m["id"],
            title=m["title"],
            kind="notice",
            verified=bool(m.get("verified", False)),
            note=m.get("note"),
        )

    def incentive(self) -> tuple[dict, Source]:
        inc = self.zeb["incentives"][0]
        return inc, Source(
            id=inc["id"],
            title=inc["title"],
            kind="notice",
            ref=inc.get("ref"),
            verified=bool(inc.get("verified", False)),
            note=inc.get("note"),
        )

    # ---------- 가정값 ----------
    def assumption_source(self, path: str, note: str | None = None) -> Source:
        return Source(
            id=f"{self.assumptions['id']}:{path}",
            title=f"초기 기획 가정값 ({self.assumptions['version']})",
            kind="assumption",
            ref=path,
            verified=True,
            note=note,
        )

    def building_uses(self) -> list[str]:
        return list(self.assumptions["building_uses"].keys())

    def performance_levels(self) -> dict[str, str]:
        return {k: v["label"] for k, v in self.assumptions["performance_levels"].items()}

    def solar_yield(self, jurisdiction: str | None) -> tuple[float, str, Source]:
        """지역별 태양광 연간 발전량 (kWh/kWp·yr). 시도코드(앞 2자리)로 찾고, 없으면 전국 평균."""
        sb = self.equipment["solar_by_region"]
        hit = sb["regions"].get((jurisdiction or "")[:2])
        entry = hit or sb["default"]
        src = Source(
            id="solar-by-region",
            title=sb["source"],
            kind="data",
            ref=f"{entry['label']} {entry['value']:,} kWh/kWp·yr",
            verified=True,
            note=None if hit else "지역별 값이 등록되지 않아 전국 평균을 사용",
        )
        return float(entry["value"]), entry["label"], src

    def regulation_source(self, ref: str) -> Source:
        rs = self.equipment["regulation_source"]
        return Source(id="kr-renewable-unit-output", title=rs["title"], kind="notice", ref=ref, url=rs.get("url"), verified=True)


@lru_cache(maxsize=8)
def rulebook(as_of: date | None = None) -> RuleBook:
    return RuleBook(as_of)


def _ordinance_ref(o: dict) -> str:
    """조문 + 어느 판을 언제 확인했는지. 개정 감지로 바뀐 판이면 공포일이 함께 보인다."""
    parts = []
    promulgated = (o.get("watch") or {}).get("promulgated_on")
    if promulgated:
        parts.append(f"{promulgated} 공포판")
    if o.get("checked_on"):
        parts.append(f"{o['checked_on']} 확인")
    return f"{o['ref']} ({', '.join(parts)})" if parts else o["ref"]
