"""전국 도시계획 조례 일괄 수집.

    python -m backend.zeb.ordinance.collect --rules-dir backend/zeb/rules --report collect-report.md

- 대상: rules/authorities.yaml (건폐율·용적률을 조례로 정하는 시도·시군 160곳 안팎)
- 지자체마다 '○○시 도시계획 조례' / '○○군 군계획 조례'를 법제처 API 로 찾아 본문을 받고,
  감지와 같은 추출기(extract.py)로 용도지역별 건폐율·용적률을 뽑는다.
- 결과는 rules/zoning_collected.yaml 에 쓴다 (사람이 확인한 zoning.yaml 과 분리). 값은 모두 verified: false 로 들어가고,
  계산에는 쓰되 화면·보고서에 '미검증(자동 수집)'으로 표시된다. 사람이 원문을 확인해 true 로 고친 값은 다시 수집해도 유지한다.
- zoning.yaml 에 이미 있는 관할(예: 서울)은 건너뛴다.
- 법정 상한을 넘는 값, 같은 용도지역에 값이 여러 개인 경우는 쓰지 않고 보고서에 남긴다 (잘못 뽑느니 비워 둔다).
- 표준 라이브러리 + PyYAML 만 쓴다 (배포 서버의 기본 python3 에서 실행).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .extract import extract
from .lawapi import LawApiError, LawClient, OrdinanceVersion

if TYPE_CHECKING:
    from collections.abc import Callable

COLLECTED_FILE = "zoning_collected.yaml"

# 법제처 지자체기관명은 '경기도 수원시', '강원특별자치도 고성군'처럼 온다. 도 이름이 바뀐 곳은 옛 이름도 받는다.
SIDO_ALIASES = {
    # 광주·전남 행정통합(2026): 전남 시·군 기관명이 '전남광주통합특별시 ○○'로, 광주 조례는 '(구)광주광역시'로 남아 있다
    "29": ("광주광역시", "(구)광주광역시"),
    "41": ("경기도",),
    "43": ("충청북도",),
    "44": ("충청남도",),
    "46": ("전남광주통합특별시", "전라남도"),
    "47": ("경상북도",),
    "48": ("경상남도",),
    "51": ("강원특별자치도", "강원도"),
    "52": ("전북특별자치도", "전라북도"),
}


def agency_predicate(sido: str, sido_name: str, local: str) -> Callable[[str], bool]:
    """지자체기관명이 이 지자체인지. 광역 단위는 시도 이름 그대로, 시·군은 '도 이름 + 시·군 이름'."""
    prefixes = tuple(p.replace(" ", "") for p in SIDO_ALIASES.get(sido, (sido_name,)))

    def ok(agency: str) -> bool:
        a = agency.replace(" ", "")
        if local == sido_name:
            return a in prefixes
        return a.startswith(prefixes) and a.endswith(local)

    return ok


def candidate_names(a: dict) -> list[str]:
    """군은 이름이 제각각이다: '군계획 조례', '계획 조례'·'계획조례'(공백은 비교 때 무시), '관리계획 조례'(장흥·무안)."""
    if a["kind"] == "county":
        n = a["name"]
        return [f"{n} 군계획 조례", f"{n} 계획 조례", f"{n} 도시계획 조례", f"{n} 관리계획 조례"]
    return [f"{a['name']} 도시계획 조례"]


@dataclass
class Collected:
    authority: dict
    version: OrdinanceVersion | None = None
    zones: dict[str, dict] = field(default_factory=dict)
    articles: dict[str, list[str]] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    error: str | None = None
    # 못 찾은 용도지역이 조문에 어떻게 쓰여 있는지 (추출 규칙 보강용)
    diagnostics: list[str] = field(default_factory=list)
    # 조문에 이름이 아예 없는 용도지역 (그 지자체에 지정되지 않은 것으로 본다). kind → 용도지역 목록
    absent: dict[str, list[str]] = field(default_factory=lambda: {"bcr": [], "far": []})

    @property
    def counts(self) -> tuple[int, int]:
        return (sum("bcr" in z for z in self.zones.values()), sum("far" in z for z in self.zones.values()))

    @property
    def complete(self) -> bool:
        """뽑은 값 + 조문에 없는 용도지역 = 16개면 다 뽑은 것으로 본다."""
        b, f = self.counts
        return b + len(self.absent["bcr"]) == 16 and f + len(self.absent["far"]) == 16


def collect_one(a: dict, client: LawClient, national: dict) -> Collected:
    out = Collected(a)
    ok = agency_predicate(a["sido"], a["sido_name"], a["name"])
    version = None
    hints = []
    for name in candidate_names(a):
        try:
            version = client.latest(name, agency_ok=ok)
            break
        except LawApiError as e:
            if "찾지 못했습니다" not in str(e):
                out.error = str(e)
                return out
            if " — " in str(e):
                hints.append(str(e).split(" — ", 1)[1])
    if version is None:
        out.error = "조례를 찾지 못함 (" + " / ".join(candidate_names(a)) + ")" + (f" {hints[0]}" if hints else "")
        return out
    out.version = version
    if str(version.org or "").startswith("(구)"):
        out.issues.append(f"통합 전 기관({version.org}) 조례 — 새 조례 제정 전 경과 적용으로 보고 수집")
    try:
        articles = client.articles(version)
    except LawApiError as e:
        out.error = str(e)
        return out
    ext = extract(articles)
    out.articles = ext.articles
    for kind in ("bcr", "far"):
        not_found = []
        for zone in national:
            values = ext.values.get(kind, {}).get(zone, [])
            if not values:
                if ext.texts.get(kind) and zone not in ext.texts[kind]:
                    out.absent[kind].append(zone)
                else:
                    not_found.append(zone)
                continue
            # 값이 여러 개면 제1항(예외 조항 앞)의 첫 값을 기본값으로 본다. 다른 값은 메모로 남긴다.
            head = ext.primary.get(kind, {}).get(zone) or values
            value, others = head[0], [v for v in values if v != head[0]]
            cap = national[zone][kind]
            if value > cap:
                out.issues.append(f"{zone} {kind_label(kind)} {value}%가 법정 상한 {cap}%를 넘음 — 비워 둠")
                out.diagnostics.append(_diagnose(kind, zone, ext.texts.get(kind, "")))
                continue
            z = out.zones.setdefault(zone, {})
            z[kind] = value
            if others:
                note = f"{kind_label(kind)}: 조문에 다른 값도 있음({'·'.join(map(str, others))}%) — 제1항 첫 값 사용"
                z["note"] = f"{z['note']} / {note}" if "note" in z else note
                out.issues.append(f"{zone} {kind_label(kind)} {value}% 사용 (다른 값 {'·'.join(map(str, others))}%)")
        if out.absent[kind] and len(out.absent[kind]) < len(national):
            out.issues.append(f"{kind_label(kind)} 조문에 없음(지정 안 된 듯): {', '.join(out.absent[kind])}")
        if not_found and len(not_found) < len(national):
            out.issues.append(f"{kind_label(kind)} 못 찾음: {', '.join(not_found)}")
            out.diagnostics += [_diagnose(kind, z, ext.texts.get(kind, "")) for z in not_found]
    if not out.zones:
        related = [f"제{a.number}조({a.title})" for a in articles if "건폐율" in a.title or "용적률" in a.title]
        out.error = "용도지역 조문에서 값을 찾지 못함 (별표로 정했거나 조 제목·문구 형식이 다름). 관련 조: " + (
            ", ".join(related[:6]) if related else "제목에 건폐율·용적률이 들어간 조 없음"
        )
        sample = ext.texts.get("bcr") or ext.texts.get("far")
        if sample and "별표" in sample:
            out.error = (
                "값을 별표로 정함 (법제처 API 는 서울 외 별표를 주지 않음) — 원문 확인 후 zoning.yaml 에 수동 입력 대상. 관련 조: "
                + ", ".join(related[:3])
            )
        elif sample:
            out.error += f". 조문 앞부분: `{sample[:160].replace('|', '/')}`"
    for name in ext.subareas.get("far", {}):
        out.issues.append(f"구역별 별도 용적률 '{name}' 있음 — 자동 반영 안 함")
    return out


def _diagnose(kind: str, zone: str, text: str) -> str:
    """못 찾은 용도지역: 조문에 이름이 없으면 그 지역이 지정되지 않은 경우가 많고, 있으면 뒤따르는 문구를 보여 준다."""
    i = text.find(zone)
    if i < 0:
        return f"{kind_label(kind)} {zone}: 조문에 이름 없음 (이 지자체에 지정되지 않은 용도지역일 수 있음)"
    snippet = text[i : i + len(zone) + 40].replace("|", "/")
    return f"{kind_label(kind)} {zone}: `{snippet}`"


def kind_label(kind: str) -> str:
    return "건폐율" if kind == "bcr" else "용적률"


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render(results: list[Collected], previous: dict, today: str, zone_order: list[str]) -> str:
    """zoning_collected.yaml 본문. 감지(update.apply)가 줄 단위로 고칠 수 있게 용도지역 줄은 한 줄 흐름 형식으로 쓴다."""
    prev_zones = {o["id"]: o.get("zones", {}) for o in (previous.get("ordinances") or [])}
    lines = [
        "# 자동 생성 파일 — backend/zeb/ordinance/collect.py (직접 값을 고치지 말고, 확인한 값은 verified: true 로만 바꾼다)",
        "# 법제처 API 로 받은 조례 원문에서 '용도지역 안에서의 건폐율/용적률' 조의 값을 뽑았다. 사람이 확인하기 전까지는",
        "# 계산에 쓰되 '미검증(자동 수집)'으로 표시된다. 같은 관할이 zoning.yaml 에 있으면 그쪽이 우선한다.",
        "schema_version: 1",
        f"collected_on: {_q(today)}",
        "ordinances:",
    ]
    missing = []
    for r in results:
        a = r.authority
        if r.error or not r.version:
            missing.append(r)
            continue
        oid = f"auto-{a['prefix']}"
        v = r.version
        refs = r.articles.get("bcr", []) + [x for x in r.articles.get("far", []) if x not in r.articles.get("bcr", [])]
        lines += [
            f"  - id: {oid}",
            f"    jurisdiction: {_q(a['prefix'])}",
            f"    jurisdiction_name: {_q(a['sido_name'] if a['name'] == a['sido_name'] else a['sido_name'] + ' ' + a['name'])}",
            f"    title: {_q(v.name)}",
            f"    ref: {_q(', '.join(refs))}",
            f"    url: {_q('https://www.law.go.kr/자치법규/' + v.name.replace(' ', ''))}",
            "    effective_from: null",
            f"    checked_on: {_q(today)}",
            "    collected: true",
            "    watch:",
            f"      law_name: {_q(v.name)}",
            f"      agency: [{_q(a['sido'])}, {_q(a['sido_name'])}, {_q(a['name'])}]",
            f"      promulgated_on: {_q(v.promulgated_on)}",
            "    zones:",
        ]
        for zone in zone_order:
            z = r.zones.get(zone)
            if not z:
                continue
            old = prev_zones.get(oid, {}).get(zone, {})
            keep = bool(old.get("verified")) and all(old.get(k) == z.get(k) for k in ("bcr", "far"))
            parts = [f"{k}: {z[k]}" for k in ("bcr", "far") if k in z]
            parts.append(f"verified: {'true' if keep else 'false'}")
            if z.get("note"):
                parts.append(f"note: {_q(z['note'])}")
            lines.append(f"      {zone}: {{ {', '.join(parts)} }}")
    lines.append("# 값을 얻지 못한 지자체 (사람이 확인하거나 추출 규칙을 보강할 대상)")
    lines.append("missing:")
    for r in missing:
        a = r.authority
        lines.append(f"  - {{ prefix: {_q(a['prefix'])}, name: {_q(a['sido_name'] + ' ' + a['name'] if a['name'] != a['sido_name'] else a['name'])}, reason: {_q(r.error or '')} }}")
    if not missing:
        lines[-1] = "missing: []"
    return "\n".join(lines) + "\n"


def report(results: list[Collected], skipped: list[dict]) -> str:
    full = [r for r in results if not r.error and r.complete]
    part = [r for r in results if not r.error and not r.complete]
    fail = [r for r in results if r.error]
    out = [
        "## 조례 일괄 수집 결과",
        "",
        f"- 대상 {len(results)}곳 (이미 확인한 관할 {len(skipped)}곳 제외: {', '.join(a['name'] for a in skipped) or '없음'})",
        (
            f"- **전체 추출 {len(full)}곳, 일부 추출 {len(part)}곳, 실패 {len(fail)}곳**"
            " (조문에 이름이 없는 용도지역은 그 지자체에 지정되지 않은 것으로 보고 전체 추출에 포함)"
        ),
        "- 추출한 값은 모두 `verified: false`(미검증)로 들어가 계산에 쓰이고, 화면·보고서에 '미검증(자동 수집)'으로 표시됩니다.",
        "",
    ]
    if part or full:
        out += ["### 추출한 지자체", "", "| 지자체 | 조례 | 공포일 | 건폐율 | 용적률 | 참고 |", "|---|---|---|---|---|---|"]
        for r in part + full:
            b, f = r.counts
            note = "; ".join(r.issues[:4]) + (" …" if len(r.issues) > 4 else "")
            out.append(f"| {r.authority['sido_name']} {r.authority['name'] if r.authority['name'] != r.authority['sido_name'] else ''} | {r.version.name} | {r.version.promulgated_on} | {b}/16 | {f}/16 | {note} |")
        out.append("")
    diag = [r for r in part if r.diagnostics]
    if diag:
        out += ["### 못 찾은 용도지역 진단 (조문 문구)", ""]
        for r in diag:
            out.append(f"<details><summary>{r.authority['sido_name']} {r.authority['name']}</summary>")
            out.append("")
            out += [f"- {d}" for d in r.diagnostics]
            out += ["", "</details>"]
        out.append("")
    if fail:
        out += ["### 실패", "", "| 지자체 | 이유 |", "|---|---|"]
        for r in fail:
            out.append(f"| {r.authority['sido_name']} {r.authority['name']} | {r.error} |")
        out.append("")
    out += [
        "### 확인 방법",
        "1. 원문 링크(파일의 url)에서 값을 확인하고, 맞으면 해당 줄을 `verified: true` 로 고칩니다. 다시 수집해도 같은 값이면 유지됩니다.",
        "2. 실패·일부 추출 지자체는 문구 형식을 보고 추출 규칙(extract.py)을 보강하거나, 확인한 값을 zoning.yaml 에 직접 넣습니다.",
    ]
    return "\n".join(out) + "\n"


def run(rules_dir: Path, client: LawClient, today: str, only: str | None = None,
        sleep: Callable[[float], None] = time.sleep) -> tuple[list[Collected], list[dict], bool]:
    zoning = yaml.safe_load((rules_dir / "zoning.yaml").read_text(encoding="utf-8"))
    national = zoning["national"]["zones"]
    manual = {o["jurisdiction"] for o in zoning.get("ordinances", [])}
    authorities = yaml.safe_load((rules_dir / "authorities.yaml").read_text(encoding="utf-8"))["authorities"]
    target, skipped = [], []
    for a in authorities:
        if only and not a["prefix"].startswith(only):
            continue
        (skipped if a["prefix"] in manual else target).append(a)
    results = []
    for i, a in enumerate(target):
        if i:
            sleep(0.3)  # 법제처 서버 부담을 줄인다
        results.append(collect_one(a, client, national))
    path = rules_dir / COLLECTED_FILE
    previous = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if only and previous:
        # 일부만 다시 수집했으면 나머지 지자체 결과는 이전 파일 그대로 둔다
        results = _merge_previous(results, previous, authorities, only)
    body = render(results, previous or {}, today, list(national.keys()))
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    changed = _without_dates(old) != _without_dates(body)
    if changed:
        path.write_bytes(body.encode("utf-8"))  # LF 고정 (yaml 은 LF)
    return [r for r in results if not only or r.authority["prefix"].startswith(only)], skipped, changed


def _without_dates(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if "collected_on:" not in l and "checked_on:" not in l)


def _merge_previous(results: list[Collected], previous: dict, authorities: list[dict], only: str) -> list[Collected]:
    by_prefix = {a["prefix"]: a for a in authorities}
    merged = list(results)
    for o in previous.get("ordinances") or []:
        p = o["jurisdiction"]
        if p.startswith(only) or p not in by_prefix:
            continue
        w = o["watch"]
        c = Collected(by_prefix[p], OrdinanceVersion(w["law_name"], "", "", w["promulgated_on"], None, None))
        c.zones = {z: {k: v[k] for k in ("bcr", "far", "note") if k in v} for z, v in o["zones"].items()}
        c.articles = {"bcr": [o["ref"]], "far": []}
        merged.append(c)
    for m in previous.get("missing") or []:
        if not m["prefix"].startswith(only) and m["prefix"] in by_prefix:
            merged.append(Collected(by_prefix[m["prefix"]], error=m["reason"]))
    order = {a["prefix"]: i for i, a in enumerate(authorities)}
    return sorted(merged, key=lambda r: order.get(r.authority["prefix"], 0))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="전국 도시계획 조례 일괄 수집")
    ap.add_argument("--rules-dir", default="backend/zeb/rules", type=Path)
    ap.add_argument("--report", default="collect-report.md", type=Path)
    ap.add_argument("--only", help="이 코드로 시작하는 관할만 (예: 41 = 경기)")
    args = ap.parse_args(argv)
    try:
        client = LawClient(os.environ.get("LAW_OC", ""))
    except LawApiError as e:
        print(e, file=sys.stderr)
        return 2
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    results, skipped, changed = run(args.rules_dir, client, today, args.only)
    body = report(results, skipped)
    args.report.write_text(body, encoding="utf-8")
    print(body)
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
            f.write("needs_review=true\n")
    ok = [r for r in results if not r.error]
    return 0 if ok or not results else 2


if __name__ == "__main__":
    sys.exit(main())
