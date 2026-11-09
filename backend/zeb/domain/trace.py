"""계산 근거 추적.

엔진이 만드는 모든 숫자는 Ledger 에 Step 으로 기록된다.
Step 은 "무슨 값을, 어떤 식으로, 어떤 입력과 근거로" 계산했는지를 담는다.
화면의 근거 패널과 보고서의 산출 근거표는 이 기록을 그대로 렌더링한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SourceKind = Literal["law", "ordinance", "notice", "assumption", "input", "data"]


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    kind: SourceKind
    ref: str | None = None
    url: str | None = None
    verified: bool = True
    note: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "ref": self.ref,
            "url": self.url,
            "verified": self.verified,
            "note": self.note,
        }


@dataclass
class Step:
    key: str
    label: str
    value: float | str
    unit: str
    formula: str
    inputs: dict[str, float | str] = field(default_factory=dict)
    sources: list[Source] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return any(not s.verified for s in self.sources)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "formula": self.formula,
            "inputs": self.inputs,
            "sources": [s.to_dict() for s in self.sources],
            "needs_review": self.needs_review,
        }


class Ledger:
    """계산 단계 기록부. key 는 결과 전체에서 유일해야 한다."""

    def __init__(self) -> None:
        self._steps: dict[str, Step] = {}
        self.warnings: list[dict] = []

    def record(
        self,
        key: str,
        label: str,
        value: float | str,
        unit: str,
        formula: str,
        inputs: dict[str, float | str] | None = None,
        sources: list[Source] | None = None,
    ) -> float | str:
        if key in self._steps:
            raise ValueError(f"duplicate ledger key: {key}")
        self._steps[key] = Step(key, label, value, unit, formula, inputs or {}, sources or [])
        return value

    def warn(self, code: str, message: str, severity: Literal["info", "warning", "critical"] = "warning") -> None:
        self.warnings.append({"code": code, "message": message, "severity": severity})

    def get(self, key: str) -> Step:
        return self._steps[key]

    def steps(self) -> list[Step]:
        return list(self._steps.values())

    def to_list(self) -> list[dict]:
        return [s.to_dict() for s in self._steps.values()]


INPUT = Source(id="user-input", title="사용자 입력", kind="input")
