"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  EquipmentTable, FloorControl, HeightPlanHint, LandUsePlans, MassingSketch, MassingSummary, ScenarioChart, ScenarioTable, TracePanel, Warnings,
} from "../_zeb/results";
import { api, buildRequest, Feasibility, Meta } from "../_zeb/api";
import { area } from "../_zeb/format";

export default function PlanView() {
  return (
    <Suspense fallback={<div className="zb-empty">불러오는 중…</div>}>
      <Plan />
    </Suspense>
  );
}

function Plan() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [meta, setMeta] = useState<Meta | null>(null);
  // 마지막 응답을 요청 쿼리와 함께 보관한다. 새 쿼리를 계산하는 동안에는 이전 결과를 그대로 보여 준다.
  const [res, setRes] = useState<{ qs: string; r: Feasibility | null; err: string | null } | null>(null);
  const [traceTab, setTraceTab] = useState<"massing" | "energy" | "all">("massing");

  const qs = params.toString();

  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
  }, []);

  useEffect(() => {
    let alive = true;
    buildRequest(new URLSearchParams(qs))
      .then(api.feasibility)
      .then((r) => alive && setRes({ qs, r, err: null }))
      .catch((e) => alive && setRes((prev) => ({ qs, r: prev?.r ?? null, err: (e as Error).message })));
    return () => {
      alive = false;
    };
  }, [qs]);

  const r = res?.r ?? null;
  const err = res?.qs === qs ? res.err : null;
  const loading = res?.qs !== qs;

  const update = (k: string, v: string | null) => {
    const p = new URLSearchParams(qs);
    if (v === null || v === "") p.delete(k);
    else p.set(k, v);
    router.replace(`${pathname}?${p}`, { scroll: false });
  };

  if (err) {
    return (
      <div className="zb-card">
        <div className="zb-alert critical">{err}</div>
        <p><Link href="/demo/zeb">← 대상지 다시 고르기</Link></p>
      </div>
    );
  }
  if (!r) return <div className="zb-empty">계산 중…</div>;

  const massingKeys = new Set(["site_area", "bcr", "far", "far_effective", "incentive_rate", "max_building_area", "max_gfa", "floor_height", "floors_by_far", "floors_by_height", "floors_by_zone", "floors", "gfa", "building_area", "height"]);

  return (
    <>
      <div className="zb-card-head" style={{ marginBottom: 18 }}>
        <div>
          <Link href="/demo/zeb" className="zb-small">← 대상지 검색</Link>
          <h1 style={{ marginTop: 4 }}>{r.site.address ?? "직접 입력 대상지"}</h1>
          <div className="zb-small zb-muted">
            {r.site.zone} · 대지 {area(r.site.site_area_m2)}
            {r.site.land_category && <> · 지목 {r.site.land_category}</>}
            {r.site.pnu && <> · PNU <span className="zb-mono">{r.site.pnu}</span></>}{" "}
            <span className={`zb-pill ${r.site.data_source === "vworld" ? "ok" : "warn"}`}>
              {r.site.data_source === "vworld" ? "브이월드 실데이터" : r.site.data_source === "sample" ? "데모 샘플 필지" : "직접 입력"}
            </span>
          </div>
        </div>
        <Link className="zb-btn" href={`/demo/zeb/report?${qs}`}>보고서 출력</Link>
      </div>

      <div className="zb-layout">
        <aside className="zb-card" style={{ position: "sticky", top: 16 }}>
          <h2 style={{ marginBottom: 12 }}>계획 조건</h2>
          <label className="zb-field">
            <span>건축물 용도</span>
            <select value={params.get("use") ?? "공동주택"} onChange={(e) => update("use", e.target.value)}>
              {(meta?.building_uses ?? ["공동주택"]).map((u) => <option key={u}>{u}</option>)}
            </select>
          </label>
          <label className="zb-field">
            <span>높이 제한 (m) — 일조·사선 등 반영값</span>
            <DeferredInput key={`h:${params.get("h") ?? ""}`} value={params.get("h") ?? ""} onCommit={(v) => update("h", v)} placeholder="없음" />
            <HeightPlanHint plans={r.height_plans ?? []} />
          </label>
          <label className="zb-field">
            <span>층고 (m)</span>
            <DeferredInput key={`fh:${params.get("fh") ?? ""}`} value={params.get("fh") ?? ""} onCommit={(v) => update("fh", v)} placeholder={`기본 ${r.massing.floor_height_m}`} />
          </label>
          <FloorControl key={`fl:${r.calc_id}`} r={r} onCommit={(v) => update("fl", v)} />
          <label className="zb-check">
            <input type="checkbox" checked={params.get("pub") === "1"} onChange={(e) => update("pub", e.target.checked ? "1" : null)} />
            공공 건축물
          </label>
          <label className="zb-field">
            <span>ZEB 인증 용적률 완화 가정</span>
            <select value={params.get("inc") ?? ""} onChange={(e) => update("inc", e.target.value || null)}>
              <option value="">반영 안 함</option>
              {["5", "4", "3", "2", "1"].map((g) => <option key={g} value={g}>{g}등급 취득 가정</option>)}
            </select>
          </label>
          <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "14px 0" }} />
          <div className="zb-small zb-muted">
            계산 ID <span className="zb-mono">{r.calc_id}</span>
            <br />
            규칙 {r.rule_versions.fingerprint} · 엔진 v{r.engine_version}
            {loading && <div>다시 계산 중…</div>}
          </div>
        </aside>

        <div>
          <Warnings items={r.warnings} />

          <section className="zb-card" style={{ marginTop: r.warnings.length ? 16 : 0 }}>
            <div className="zb-card-head">
              <h2>핵심 판단</h2>
              {r.review_required.length > 0 && (
                <span className="zb-pill warn">미검증 규칙 {r.review_required.length}건 사용</span>
              )}
            </div>
            <ul className="zb-insights">
              {r.insights.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
          </section>

          <section className="zb-card">
            <div className="zb-card-head">
              <h2>1. 건축 규모</h2>
            </div>
            <div style={{ marginBottom: 12 }}><LandUsePlans site={r.site} /></div>
            <MassingSummary r={r} />
            <div style={{ marginTop: 12 }}><MassingSketch r={r} /></div>
          </section>

          <section className="zb-card">
            <div className="zb-card-head">
              <h2>2. ZEB 등급별 설비 시나리오</h2>
              <span className="zb-small zb-muted">
                연간 1차에너지 소요량 {r.energy.demand_kwh.toLocaleString()} kWh ({r.energy.demand_intensity} kWh/㎡·yr 가정)
              </span>
            </div>
            <ScenarioChart r={r} />
            <p className="zb-small zb-muted" style={{ margin: "4px 0 14px" }}>
              막대 = 달성 자립률, 가로선 = 등급 기준, 진한 막대 = 의무 등급. 단위 생산량당 비용이 낮은 설비부터 설치 한계까지 채운 최소비용 조합입니다.
            </p>
            <ScenarioTable scenarios={r.scenarios} />
          </section>

          <section className="zb-card">
            <h2 style={{ marginBottom: 12 }}>3. 설비 잠재량 (이 대지에 들어갈 수 있는 최대치)</h2>
            <EquipmentTable r={r} />
          </section>

          <section className="zb-card">
            <div className="zb-card-head">
              <h2>산출 근거</h2>
              <div className="zb-tabs" style={{ marginBottom: 0, borderBottom: 0 }}>
                {(["massing", "energy", "all"] as const).map((k) => (
                  <button key={k} className={`zb-tab ${traceTab === k ? "on" : ""}`} onClick={() => setTraceTab(k)}>
                    {k === "massing" ? "규모" : k === "energy" ? "에너지" : "전체"}
                  </button>
                ))}
              </div>
            </div>
            <TracePanel
              steps={r.trace}
              filter={traceTab === "all" ? undefined : traceTab === "massing" ? (s) => massingKeys.has(s.key) : (s) => !massingKeys.has(s.key)}
            />
          </section>
        </div>
      </div>
    </>
  );
}

/** 타이핑 중에는 재계산하지 않고, 포커스 아웃/엔터 시에만 반영 */
function DeferredInput({ value, onCommit, placeholder }: { value: string; onCommit: (v: string) => void; placeholder?: string }) {
  // 바깥 값이 바뀌면 호출부에서 key 로 새로 만든다 (effect 로 동기화하지 않음)
  const [v, setV] = useState(value);
  return (
    <input
      type="number"
      min={0}
      step="0.1"
      value={v}
      placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v !== value && onCommit(v)}
      onKeyDown={(e) => e.key === "Enter" && onCommit(v)}
    />
  );
}
