// 행정구역 코드 변경 대응 (backend/zeb/domain/regions.py 와 같은 표. 테스트가 둘을 맞춰 본다).
// 2026-07-01 전남광주통합특별시 출범으로 시군구 코드가 46·29 → 12 로 바뀌었다.
// 브이월드 토지특성 데이터가 아직 예전 PNU 로만 있는 필지가 있어, 새 PNU 로 비면 예전 PNU 로 한 번 더 조회한다.

// 전남 시군 (예전 코드). 새 코드는 앞 2자리만 12
const JEONNAM = [
  "46110", "46130", "46150", "46170", "46230",
  "46710", "46720", "46730", "46770", "46780", "46790", "46800", "46810", "46820",
  "46830", "46840", "46860", "46870", "46880", "46890", "46900", "46910",
];
// 광주 자치구: 새 코드 → 예전 코드 (5개 구 모두 실제 필지로 확인)
const GWANGJU: Record<string, string> = {
  "12210": "29110",
  "12240": "29140",
  "12270": "29155",
  "12300": "29170",
  "12330": "29200",
};

const NEW_TO_OLD: Record<string, string> = {
  ...Object.fromEntries(JEONNAM.map((c) => ["12" + c.slice(2), c])),
  ...GWANGJU,
};

/** 새 코드(관할코드·PNU)를 예전 코드로. 바뀐 지역이 아니면 null. */
export function legacyCode(code: string): string | null {
  const old = code.length >= 5 ? NEW_TO_OLD[code.slice(0, 5)] : undefined;
  return old ? old + code.slice(5) : null;
}
