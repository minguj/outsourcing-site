"""브이월드 키 발급 후 실제 응답 구조를 확인하는 스크립트 (저장소 루트에서 실행).

    PowerShell:
      $env:VWORLD_API_KEY="..."; $env:VWORLD_DOMAIN="https://fitagent.co.kr"
      .\\backend\\.venv\\Scripts\\python.exe -m backend.zeb.check_vworld "서울특별시 마포구 아현동 1"

1) 검색 결과에서 PNU 를 고르고
2) 토지특성/토지이용계획 원본 응답 일부를 출력해 backend/tests/fixtures/zeb/*.recorded.json 으로 저장한 뒤
3) 어댑터가 파싱한 결과를 출력한다.
필드명이 다르면 zeb/adapters/vworld.py 의 FIELD_MAP 만 수정한다.
*.recorded.json 은 키가 들어 있지 않지만 실제 필지 정보이므로 커밋하기 전에 내용을 확인한다.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from .adapters.vworld import VWorldParcelProvider

FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "zeb"


async def main(query: str) -> None:
    p = VWorldParcelProvider(os.environ["VWORLD_API_KEY"], os.environ.get("VWORLD_DOMAIN", "https://fitagent.co.kr"))
    hits = await p.search(query, limit=5)
    print("# 검색 결과")
    for h in hits:
        print(f"  {h.pnu}  {h.address}")
    if not hits:
        return
    pnu = hits[0].pnu
    FIX.mkdir(parents=True, exist_ok=True)
    for name, path, params in [
        ("land_characteristics", "/ned/data/getLandCharacteristics", {"pnu": pnu, "numOfRows": 10, "pageNo": 1}),
        ("land_use_attr", "/ned/data/getLandUseAttr", {"pnu": pnu, "numOfRows": 100, "pageNo": 1}),
    ]:
        raw = await p._get(path, params)
        out = FIX / f"vworld_{name}.recorded.json"
        out.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n# {name} 원본 저장 → {out}")
        print(json.dumps(raw, ensure_ascii=False)[:800])
    print("\n# 파싱 결과")
    print(await p.get(pnu))


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "서울특별시 마포구 아현동 1"))
