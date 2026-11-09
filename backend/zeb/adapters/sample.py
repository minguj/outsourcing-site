from __future__ import annotations

import json
from pathlib import Path

from .base import Parcel, ParcelSummary

DATA = Path(__file__).resolve().parent.parent / "data"


class SampleParcelProvider:
    name = "sample"

    def __init__(self) -> None:
        raw = json.loads((DATA / "sample_parcels.json").read_text(encoding="utf-8"))
        self._parcels = {p["pnu"]: p for p in raw["parcels"]}

    async def search(self, query: str, limit: int = 10) -> list[ParcelSummary]:
        q = query.replace(" ", "")
        hits = [p for p in self._parcels.values() if not q or q in p["address"].replace(" ", "") or q in p["pnu"]]
        return [ParcelSummary(p["pnu"], p["address"], p.get("lat"), p.get("lng")) for p in hits[:limit]]

    async def get(self, pnu: str) -> Parcel | None:
        p = self._parcels.get(pnu)
        if not p:
            return None
        return Parcel(
            pnu=p["pnu"],
            address=p["address"],
            area_m2=p["area_m2"],
            zone=p["zone"],
            land_use_plans=p.get("land_use_plans", []),
            adjacent_plans=p.get("adjacent_plans", []),
            land_category=p.get("land_category", "대"),
            lat=p.get("lat"),
            lng=p.get("lng"),
            data_source="sample",
            tags=p.get("tags", []),
        )


class RedevelopmentCatalog:
    def __init__(self) -> None:
        raw = json.loads((DATA / "redevelopment_projects.json").read_text(encoding="utf-8"))
        self._projects = raw["projects"]

    def search(self, query: str) -> list[dict]:
        q = query.replace(" ", "")
        return [p for p in self._projects if not q or q in (p["name"] + p["district"] + p["type"]).replace(" ", "")]
