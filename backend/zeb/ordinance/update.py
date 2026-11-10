"""추출값과 규칙 파일(zoning.yaml)을 비교해 수정안과 보고서를 만든다.

판단 기준 (용도지역·항목별)
- 조문 값이 지금 값과 같으면(서울도심·용도별 별도 기준 값이 함께 나와도) → 변경 없음, verified 유지
- 조문에 값이 하나뿐이고 지금 값과 다르면 → 새 값으로 바꾸고 verified: false
- 값을 못 찾았거나 여러 개라 판단할 수 없으면 → 값은 두고 verified: false (사람 확인)
즉 조례가 바뀐 뒤 사람이 확인하지 않은 값은 모두 화면에 '미검증'으로 보인다.

YAML 은 주석·서식을 보존하려고 해당 줄만 고친다 (PyYAML 로 다시 쓰면 근거 주석이 사라진다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import ZONE, Extracted
from .lawapi import OrdinanceVersion

LABEL = {"bcr": "건폐율", "far": "용적률"}


@dataclass
class ZoneResult:
    zone: str
    kind: str
    current: float
    found: list[int]
    status: str  # same | changed | manual
    new: int | None = None
    reason: str = ""


@dataclass
class Proposal:
    ordinance_id: str
    title: str
    version: OrdinanceVersion
    previous_promulgated_on: str | None
    results: list[ZoneResult] = field(default_factory=list)
    articles: dict[str, list[str]] = field(default_factory=dict)
    # 구역별 기준(서울도심 등) 중 조문과 다르거나 못 찾은 것: (구역 이름, 설명)
    subarea_issues: list[tuple[str, str]] = field(default_factory=list)

    @property
    def changed(self) -> list[ZoneResult]:
        return [r for r in self.results if r.status == "changed"]

    @property
    def manual(self) -> list[ZoneResult]:
        return [r for r in self.results if r.status == "manual"]


def compare(ordinance: dict, version: OrdinanceVersion, ext: Extracted) -> Proposal:
    prop = Proposal(
        ordinance_id=ordinance["id"],
        title=ordinance["title"],
        version=version,
        previous_promulgated_on=(ordinance.get("watch") or {}).get("promulgated_on"),
        articles=ext.articles,
    )
    for zone, z in ordinance["zones"].items():
        if not re.fullmatch(ZONE, zone):
            continue  # '제2종일반주거지역(7층이하)' 같은 서울 세분 이름은 조문에 그대로 나오지 않는다
        for kind in ("bcr", "far"):
            if kind not in z:
                continue  # 일괄 수집분은 한쪽 값만 있을 수 있다
            cur = z[kind]
            known = {cur}
            if kind == "far":
                for sa in ordinance.get("subareas", []):
                    if zone in sa.get("far", {}):
                        known.add(sa["far"][zone])
                for uo in ordinance.get("use_overrides", {}).get(zone, {}).values():
                    known.add(uo["far"])
            found = ext.values.get(kind, {}).get(zone, [])
            if not found:
                prop.results.append(ZoneResult(zone, kind, cur, found, "manual", reason="조문에서 값을 찾지 못함"))
            elif cur in found and set(found) <= known:
                prop.results.append(ZoneResult(zone, kind, cur, found, "same"))
            elif len(found) == 1:
                prop.results.append(ZoneResult(zone, kind, cur, found, "changed", new=found[0]))
            else:
                prop.results.append(ZoneResult(zone, kind, cur, found, "manual", reason="값이 여러 개라 자동 판단 불가"))
    for sa in ordinance.get("subareas", []):
        got = ext.subareas.get("far", {}).get(sa["name"])
        if not got:
            prop.subarea_issues.append((sa["name"], "조문에서 이 구역의 별도 용적률을 찾지 못함"))
            continue
        diffs = [f"{z} {cur}% → {got.get(z, '없음')}{'%' if z in got else ''}" for z, cur in sa["far"].items() if got.get(z) != cur]
        if diffs:
            prop.subarea_issues.append((sa["name"], ", ".join(diffs)))
    return prop


def _block(lines: list[str], ordinance_id: str) -> tuple[int, int]:
    start = next(i for i, l in enumerate(lines) if re.match(rf"\s*-\s+id:\s*{re.escape(ordinance_id)}\s*$", l))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if re.match(r"\s*-\s+id:", l) and len(l) - len(l.lstrip()) <= len(lines[start]) - len(lines[start].lstrip()):
            end = i
            break
        if l and not l[0].isspace() and not l.startswith("#"):
            end = i
            break
    return start, end


def apply(yaml_text: str, prop: Proposal, today: str) -> str:
    """제안을 규칙 파일 본문에 반영한다. 줄 단위로만 고친다."""
    nl = "\r\n" if "\r\n" in yaml_text else "\n"
    lines = yaml_text.split(nl)
    start, end = _block(lines, prop.ordinance_id)

    touched: dict[str, dict[str, int | None]] = {}
    for r in prop.results:
        if r.status != "same":
            touched.setdefault(r.zone, {})[r.kind] = r.new

    flagged = {name for name, _ in prop.subarea_issues}
    in_flagged_subarea = False
    for i in range(start, end):
        sm = re.match(r"^\s+-\s+name:\s*(.+?)\s*$", lines[i])
        if sm:
            in_flagged_subarea = sm.group(1) in flagged
        elif in_flagged_subarea and re.match(r"^\s+verified:\s*true", lines[i]):
            lines[i] = re.sub(r"verified:\s*true", "verified: false", lines[i])
            in_flagged_subarea = False
            continue
        m = re.match(rf"^(\s+)({ZONE}):\s*\{{.*\}}\s*$", lines[i])
        if m and m.group(2) in touched:
            line = lines[i]
            for kind, new in touched[m.group(2)].items():
                if new is not None:
                    line = re.sub(rf"\b{kind}:\s*[\d.]+", f"{kind}: {new}", line, count=1)
            line = re.sub(r"verified:\s*true", "verified: false", line, count=1)
            lines[i] = line
        elif re.match(r"^\s+checked_on:", lines[i]) and not _in_watch(lines, i, start):
            lines[i] = re.sub(r"checked_on:.*$", f'checked_on: "{today}"', lines[i])
        elif re.match(r"^\s+promulgated_on:", lines[i]):
            lines[i] = re.sub(r"promulgated_on:.*$", f'promulgated_on: "{prop.version.promulgated_on}"', lines[i])
    return nl.join(lines)


def _in_watch(lines: list[str], i: int, start: int) -> bool:
    ind = len(lines[i]) - len(lines[i].lstrip())
    for j in range(i - 1, start, -1):
        l = lines[j]
        if l.strip() and len(l) - len(l.lstrip()) < ind:
            return l.strip().startswith("watch:")
    return False


def report(props: list[Proposal], errors: list[str]) -> str:
    out = ["## 조례 개정 감지 결과", ""]
    for p in props:
        v = p.version
        out += [
            f"### {p.title}",
            f"- 공포일: {p.previous_promulgated_on or '기록 없음'} → **{v.promulgated_on}**"
            + (f" (시행 {v.effective_on})" if v.effective_on else ""),
            f"- 원문: https://www.law.go.kr/자치법규/{v.name.replace(' ', '')}",
            (
                f"- 찾은 조문: 건폐율 {', '.join(p.articles.get('bcr', [])) or '없음'} / "
                f"용적률 {', '.join(p.articles.get('far', [])) or '없음'}"
            ),
            (
                f"- 자동 판단: 같음 {len(p.results) - len(p.changed) - len(p.manual)}건, "
                f"**변경 {len(p.changed)}건, 수동 확인 {len(p.manual)}건**"
            ),
            "",
        ]
        for name, why in p.subarea_issues:
            out.append(f"- **구역별 기준 `{name}`: {why}** → 해당 구역 verified: false (값은 직접 수정)")
        if p.subarea_issues:
            out.append("")
        if p.changed or p.manual:
            out += ["| 용도지역 | 항목 | 지금 값 | 조문 값 | 처리 |", "|---|---|---|---|---|"]
            for r in p.changed + p.manual:
                found = ", ".join(f"{x}%" for x in r.found) or "-"
                act = f"{r.new}%로 변경 (미검증)" if r.status == "changed" else f"값 유지, 미검증 표시 — {r.reason}"
                out.append(f"| {r.zone} | {LABEL[r.kind]} | {r.current:g}% | {found} | {act} |")
            out.append("")
    if errors:
        out += ["### 조회 실패", *[f"- {e}" for e in errors], ""]
    out += [
        "### 승인 전 확인할 것",
        "1. 원문 링크에서 바뀐 값과 단서 조항을 확인합니다.",
        "2. 맞으면 해당 줄의 `verified: false` 를 `true` 로 고치고, 조문 번호가 바뀌었으면 `ref` 도 고칩니다.",
        "3. 테스트 통과를 확인한 뒤 병합하면 배포됩니다.",
    ]
    return "\n".join(out) + "\n"
