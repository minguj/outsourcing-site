export type SourceRef = {
  id: string;
  title: string;
  kind: "law" | "ordinance" | "notice" | "assumption" | "input" | "data";
  ref?: string | null;
  url?: string | null;
  verified: boolean;
  note?: string | null;
};

export type TraceStep = {
  key: string;
  label: string;
  value: number | string;
  unit: string;
  formula: string;
  inputs: Record<string, number | string>;
  sources: SourceRef[];
  needs_review: boolean;
};

export type Pick = {
  key: string;
  name: string;
  unit: string;
  units: number;
  production_kwh: number;
  cost_krw: number;
  utilization_pct: number;
};

export type Scenario = {
  target_grade: string;
  target_label: string;
  required_pct: number;
  feasible: boolean;
  achieved_pct: number;
  achieved_grade: string | null;
  total_cost_krw: number;
  cost_per_gfa_krw: number;
  picks: Pick[];
  shortfall_kwh: number;
  mandatory: boolean;
  note: string | null;
};

export type Warning = { code: string; message: string; severity: "info" | "warning" | "critical" };

export type Feasibility = {
  calc_id: string;
  engine_version: string;
  computed_at: string;
  rule_versions: Record<string, string>;
  site: {
    site_area_m2: number;
    zone: string;
    jurisdiction: string | null;
    address: string | null;
    pnu: string | null;
    land_use_plans: string[];
    partial_plans: string[];
    adjacent_plans: string[];
    land_category: string | null;
    secondary_zone: string | null;
    data_source: string;
  };
  options: {
    building_use: string;
    height_limit_m: number | null;
    floor_height_m: number | null;
    is_public: boolean;
    apply_zeb_incentive_grade: string | null;
  };
  massing: {
    bcr_pct: number;
    far_pct: number;
    far_effective_pct: number;
    max_building_area_m2: number;
    max_gfa_m2: number;
    floors: number;
    building_area_m2: number;
    gfa_m2: number;
    height_m: number;
    floor_height_m: number;
    binding_constraint: string;
    far_utilization_pct: number;
  };
  energy: {
    demand_intensity: number;
    demand_kwh: number;
    max_self_sufficiency_pct: number;
    max_grade: string | null;
    mandatory_grade: string | null;
    options: {
      key: string;
      name: string;
      unit: string;
      max_units: number;
      production_per_unit: number;
      unit_cost_krw: number;
      cost_per_kwh: number | null;
      limit_reason: string;
    }[];
  };
  grade_source: SourceRef;
  scenarios: Scenario[];
  insights: string[];
  warnings: Warning[];
  trace: TraceStep[];
  review_required: string[];
};

export type ParcelSummary = { pnu: string; address: string; lat?: number | null; lng?: number | null };
export type Redevelopment = {
  id: string;
  name: string;
  type: string;
  stage: string;
  district: string;
  representative_pnu: string;
  area_m2: number;
};
export type Meta = {
  engine_version: string;
  parcel_source: "sample" | "vworld";
  building_uses: string[];
  zones: string[];
  grades: { grade: string; label: string; min_self_sufficiency: number }[];
  rule_versions: Record<string, string>;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => fetch("/api/demo/zeb/meta").then(json<Meta>),
  searchParcels: (q: string, source = "auto") =>
    fetch(`/api/demo/zeb/parcels/search?q=${encodeURIComponent(q)}&source=${source}`).then(
      json<{ source: string; items: ParcelSummary[] }>,
    ),
  searchRedevelopment: (q: string) =>
    fetch(`/api/demo/zeb/redevelopment/search?q=${encodeURIComponent(q)}`).then(json<{ items: Redevelopment[] }>),
  feasibility: (body: unknown) =>
    fetch("/api/demo/zeb/feasibility", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<Feasibility>),
};

/** URL 쿼리 ↔ 요청 본문. 같은 URL 이면 같은 계산(calc_id)이 나오도록 모든 입력을 URL 에 둔다. */
export function requestFromParams(p: URLSearchParams) {
  const num = (k: string) => (p.get(k) ? Number(p.get(k)) : null);
  const base = {
    building_use: p.get("use") ?? "공동주택",
    height_limit_m: num("h"),
    floor_height_m: num("fh"),
    is_public: p.get("pub") === "1",
    apply_zeb_incentive_grade: p.get("inc") || null,
  };
  if (p.get("pnu")) return { ...base, pnu: p.get("pnu"), source: p.get("source") ?? "auto" };
  return {
    ...base,
    manual: {
      site_area_m2: num("area") ?? 0,
      zone: p.get("zone") ?? "",
      jurisdiction: p.get("juris") || null,
      address: p.get("addr") || null,
    },
  };
}
