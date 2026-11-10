// 브이월드 브라우저 조회.
// 브이월드는 해외·클라우드 IP 를 차단하므로(운영 서버는 시드니) 방문자 브라우저(국내 IP)에서 직접 조회한다.
// 응답 해석은 하지 않는다. 원본을 그대로 서버(/feasibility 의 vworld_raw)로 보내 서버의 검증된 해석 코드를 쓴다.
// 키는 브이월드 지도 API 처럼 페이지에 전달되며, 브이월드에 등록한 도메인에서만 동작한다.

import { legacyCode } from "./regions";

const BASE = "https://api.vworld.kr";

export type VWorldConf = { key: string; domain: string };
export type VWorldRaw = { pnu: string; land_characteristics: unknown; land_use_attr: unknown };
type Json = Record<string, unknown>;

function jsonp(url: string, timeoutMs = 10_000): Promise<Json> {
  return new Promise((resolve, reject) => {
    const cb = `__zbVworld${Date.now()}${Math.floor(Math.random() * 1e6)}`;
    const w = window as unknown as Record<string, unknown>;
    const script = document.createElement("script");
    const finish = (fn: () => void) => {
      clearTimeout(timer);
      delete w[cb];
      script.remove();
      fn();
    };
    const timer = setTimeout(() => finish(() => reject(new Error("브이월드 응답 시간이 초과되었습니다."))), timeoutMs);
    w[cb] = (data: Json) => finish(() => resolve(data));
    script.onerror = () => finish(() => reject(new Error("브이월드에 연결하지 못했습니다.")));
    script.src = `${url}&callback=${cb}`;
    document.head.appendChild(script);
  });
}

async function call(conf: VWorldConf, path: string, params: Record<string, string>): Promise<Json> {
  const q = new URLSearchParams({ key: conf.key, domain: conf.domain, format: "json", ...params });
  const url = `${BASE}${path}?${q}`;
  let data: Json;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(String(r.status));
    data = (await r.json()) as Json;
  } catch {
    // CORS 를 허용하지 않는 API 는 JSONP 로 다시 시도한다.
    data = await jsonp(url);
  }
  const response = (data?.response ?? {}) as Json;
  const status = response.status as string | undefined;
  if (status && status !== "OK" && status !== "NOT_FOUND") {
    const text = String(((response.error ?? {}) as Json).text ?? status);
    throw new Error(`브이월드 오류: ${text.split(conf.key).join("***")}`);
  }
  return data;
}

export async function searchParcels(conf: VWorldConf, query: string) {
  if (!query.trim()) return [];
  const data = await call(conf, "/req/search", {
    service: "search", request: "search", version: "2.0", crs: "EPSG:4326", size: "10", page: "1",
    query, type: "address", category: "parcel", errorformat: "json",
  });
  const result = ((data.response as Json)?.result ?? {}) as Json;
  const raw = result.items;
  const items = (Array.isArray(raw) ? raw : raw ? [raw] : []) as Json[];
  return items
    .filter((it) => typeof it.id === "string")
    .map((it) => ({
      pnu: it.id as string,
      address: String(((it.address ?? {}) as Json).parcel ?? it.title ?? it.id),
    }));
}

const landCache = new Map<string, Promise<VWorldRaw>>();

function hasRows(data: Json, container: string): boolean {
  const field = ((data?.[container] ?? {}) as Json).field;
  return Array.isArray(field) ? field.length > 0 : Boolean(field);
}

async function fetchRaw(conf: VWorldConf, pnu: string): Promise<[Json, Json]> {
  return Promise.all([
    call(conf, "/ned/data/getLandCharacteristics", { pnu, numOfRows: "10", pageNo: "1" }),
    call(conf, "/ned/data/getLandUseAttr", { pnu, numOfRows: "100", pageNo: "1" }),
  ]);
}

/** 토지특성 + 토지이용계획 원본. 같은 필지는 페이지 안에서 한 번만 조회한다.
 *  전남광주통합(2026-07) 뒤 새 PNU(12…)로 토지특성이 비면 같은 필지의 예전 PNU 로 다시 조회한다.
 *  돌려주는 pnu 는 새 PNU 그대로 (관할·조례는 서버가 예전 코드로도 찾는다). */
export function fetchLand(conf: VWorldConf, pnu: string): Promise<VWorldRaw> {
  let p = landCache.get(pnu);
  if (!p) {
    p = (async () => {
      let [land_characteristics, land_use_attr] = await fetchRaw(conf, pnu);
      const old = legacyCode(pnu);
      if (old && !hasRows(land_characteristics, "landCharacteristicss")) {
        [land_characteristics, land_use_attr] = await fetchRaw(conf, old);
      }
      return { pnu, land_characteristics, land_use_attr };
    })();
    p.catch(() => landCache.delete(pnu));
    landCache.set(pnu, p);
  }
  return p;
}
