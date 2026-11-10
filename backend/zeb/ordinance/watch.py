"""조례 개정 감지 실행기.

    python -m backend.zeb.ordinance.watch --report ordinance-report.md
    (--rules 를 주지 않으면 zoning.yaml 과, 있으면 zoning_collected.yaml(일괄 수집분)을 함께 본다)

환경변수 LAW_OC: 법제처 Open API 인증값.
바뀐 조례가 있으면 규칙 파일을 고치고 보고서를 쓴 뒤, GITHUB_OUTPUT 에 changed=true 를 남긴다.
종료 코드: 0 정상(변경 유무 무관), 2 조회 실패만 있고 변경 없음.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path

import yaml

from .collect import COLLECTED_FILE, agency_predicate
from .extract import extract
from .lawapi import LawApiError, LawClient
from .update import Proposal, apply, compare, report

RULES_DIR = Path("backend/zeb/rules")


def default_rules() -> list[Path]:
    paths = [RULES_DIR / "zoning.yaml"]
    if (RULES_DIR / COLLECTED_FILE).exists():
        paths.append(RULES_DIR / COLLECTED_FILE)
    return paths


def run(rules_path: Path, client: LawClient, today: str, sleep=time.sleep) -> tuple[list[Proposal], list[str]]:
    text = rules_path.read_bytes().decode("utf-8")
    data = yaml.safe_load(text)
    props, errors = [], []
    for i, o in enumerate(data.get("ordinances") or []):
        w = o.get("watch")
        if not w:
            continue
        if i:
            sleep(0.2)
        agency = w.get("agency")
        ok = agency_predicate(*agency) if agency else None
        try:
            version = client.latest(w["law_name"], w.get("org"), agency_ok=ok)
            if version.promulgated_on and version.promulgated_on == w.get("promulgated_on"):
                continue  # 확인한 판 그대로
            prop = compare(o, version, extract(client.articles(version)))
        except LawApiError as e:
            errors.append(f"{o['title']}: {e}")
            continue
        text = apply(text, prop, today)
        props.append(prop)
    if props:
        rules_path.write_bytes(text.encode("utf-8"))
    return props, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="조례 개정 감지")
    ap.add_argument("--rules", action="append", type=Path, help="여러 번 줄 수 있다. 생략하면 zoning.yaml + zoning_collected.yaml")
    ap.add_argument("--report", default="ordinance-report.md", type=Path)
    args = ap.parse_args(argv)

    try:
        client = LawClient(os.environ.get("LAW_OC", ""))
    except LawApiError as e:
        print(e, file=sys.stderr)
        return 2
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    props, errors = [], []
    for path in args.rules or default_rules():
        p, e = run(path, client, today)
        props += p
        errors += e
    body = report(props, errors)
    args.report.write_text(body, encoding="utf-8")
    print(body)

    changed = bool(props)
    needs_manual = any(p.manual or p.changed or p.subarea_issues for p in props)
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
            f.write(f"needs_review={'true' if needs_manual else 'false'}\n")
    return 2 if errors and not changed else 0


if __name__ == "__main__":
    sys.exit(main())
