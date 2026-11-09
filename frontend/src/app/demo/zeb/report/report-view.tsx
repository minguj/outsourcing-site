"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { EquipmentTable, LandUsePlans, ScenarioChart, ScenarioTable } from "../_zeb/results";
import { api, Feasibility, requestFromParams } from "../_zeb/api";
import { SOURCE_KIND, area, gradeLabel, krw, n } from "../_zeb/format";

export default function ReportView() {
  return (
    <Suspense fallback={<div className="zb-empty">불러오는 중…</div>}>
      <Report />
    </Suspense>
  );
}

function Report() {
  const params = useSearchParams();
  const qs = params.toString();
  const [r, setR] = useState<Feasibility | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.feasibility(requestFromParams(new URLSearchParams(qs))).then(setR).catch((e) => setErr(e.message));
  }, [qs]);

  if (err) return <div className="zb-alert critical">{err}</div>;
  if (!r) return <div className="zb-empty">보고서 생성 중…</div>;

  const m = r.massing;
  const mand = r.scenarios.find((s) => s.mandatory);
  const sources = new Map<string, Feasibility["trace"][number]["sources"][number]>();
  sources.set(r.grade_source.id, r.grade_source);
  r.trace.forEach((t) => t.sources.forEach((s) => s.kind !== "input" && sources.set(s.id.split(":")[0], s)));

  return (
    <>
      <div className="zb-no-print" style={{ display: "flex", gap: 8, justifyContent: "space-between", maxWidth: 860, margin: "0 auto 14px" }}>
        <Link href={`/demo/zeb/plan?${qs}`}>← 검토 화면으로</Link>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="zb-btn-ghost"
            onClick={() => {
              const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = `feasibility-${r.calc_id}.json`;
              a.click();
            }}
          >
            계산 스냅샷(JSON)
          </button>
          <button onClick={() => window.print()}>PDF로 저장 / 인쇄</button>
        </div>
      </div>

      <article className="zb-report">
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 16 }}>
          <div>
            <div className="zb-small zb-muted">초기 기획 검토 보고서</div>
            <h1>{r.site.address ?? "직접 입력 대상지"}</h1>
            <div className="zb-small zb-muted">
              {r.site.zone} · 대지 {area(r.site.site_area_m2)}
              {r.site.land_category ? ` · 지목 ${r.site.land_category}` : ""} · {r.options.building_use}
              {r.options.is_public ? " · 공공" : " · 민간"}
            </div>
          </div>
          <div className="zb-small zb-muted" style={{ textAlign: "right" }}>
            계산 ID <span className="zb-mono">{r.calc_id}</span>
            <br />
            {new Date(r.computed_at).toLocaleString("ko-KR")}
          </div>
        </header>

        {r.warnings.filter((w) => w.severity === "critical").map((w, i) => (
          <div key={i} className="zb-alert critical" style={{ marginTop: 14 }}>{w.message}</div>
        ))}

        <h2>요약</h2>
        <table className="zb-avoid-break">
          <tbody>
            <tr><th>계획 규모</th><td>지상 {m.floors}층, 연면적 {area(m.gfa_m2)}, 높이 약 {n(m.height_m, 1)}m (결정 조건: {m.binding_constraint})</td></tr>
            <tr><th>ZEB 의무 등급</th><td>{r.energy.mandatory_grade ? `${gradeLabel(r.energy.mandatory_grade)} 이상` : "의무 대상 아님 (연면적 기준)"}</td></tr>
            <tr><th>의무 등급 충족 설비비</th><td>{mand ? (mand.feasible ? `${krw(mand.total_cost_krw)} (㎡당 ${n(mand.cost_per_gfa_krw)}원)` : `충족 불가 — ${mand.note}`) : "—"}</td></tr>
            <tr><th>도달 가능 최고 등급</th><td>{gradeLabel(r.energy.max_grade)} (설치 가능 최대 자립률 {r.energy.max_self_sufficiency_pct}%)</td></tr>
          </tbody>
        </table>
        <ul className="zb-insights" style={{ marginTop: 10 }}>
          {r.insights.map((t, i) => <li key={i}>{t}</li>)}
        </ul>

        <h2>1. 대지 및 규모 검토</h2>
        <table className="zb-avoid-break">
          <thead><tr><th>항목</th><th className="num">값</th><th>산식 / 근거</th></tr></thead>
          <tbody>
            {["site_area", "bcr", "far", "far_effective", "max_building_area", "max_gfa", "floors", "gfa", "building_area", "height"].map((k) => {
              const s = r.trace.find((t) => t.key === k);
              if (!s) return null;
              return (
                <tr key={k}>
                  <td>{s.label}{s.needs_review && <span className="zb-pill warn" style={{ marginLeft: 4 }}>검토 필요</span>}</td>
                  <td className="num">{typeof s.value === "number" ? n(s.value, s.value % 1 ? 2 : 0) : s.value} {s.unit}</td>
                  <td className="zb-small">{s.formula}{s.sources.filter((x) => x.kind !== "input").map((x) => ` · ${x.title} ${x.ref ?? ""}`).join("")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div style={{ marginTop: 8 }}><LandUsePlans site={r.site} /></div>

        <h2>2. ZEB 등급별 신재생 설비 시나리오</h2>
        <p className="zb-small zb-muted" style={{ marginTop: 0 }}>
          연간 1차에너지 소요량 {n(r.energy.demand_kwh)} kWh (연면적 {area(m.gfa_m2)} × {r.energy.demand_intensity} kWh/㎡·yr 가정).
          등급 기준: {r.grade_source.title}.
        </p>
        <div className="zb-avoid-break"><ScenarioChart r={r} /></div>
        <ScenarioTable scenarios={r.scenarios} compact />

        <h2>3. 설비 잠재량 및 단가 가정</h2>
        <EquipmentTable r={r} />

        <h2>4. 근거 및 한계</h2>
        <table>
          <thead><tr><th>구분</th><th>근거</th><th>상태</th></tr></thead>
          <tbody>
            {[...sources.values()].map((s) => (
              <tr key={s.id}>
                <td>{SOURCE_KIND[s.kind]}</td>
                <td>{s.title}{s.ref && s.kind !== "assumption" ? ` · ${s.ref}` : ""}</td>
                <td>{s.kind === "assumption" ? "가정값" : s.verified ? "근거 확인" : "미검증"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="zb-small zb-muted" style={{ paddingLeft: 18 }}>
          <li>본 보고서는 설계 착수 전 의사결정을 돕는 초기 검토 결과이며, 인허가·인증 제출용 계산서가 아닙니다.</li>
          <li>에너지 소요량·설비 단가·발전량은 가정값입니다. 실설계 단계에서는 인증 평가 프로그램(ECO2 등) 결과와 실견적으로 대체해야 합니다.</li>
          <li>지구단위계획·정비계획 등 개별 계획이 결정된 구역은 해당 결정고시가 우선합니다.</li>
          <li>
            재현 정보: 엔진 v{r.engine_version} · 규칙 지문 {r.rule_versions.fingerprint} · 기준일 {r.rule_versions.as_of} ·
            데이터 {r.site.data_source}
          </li>
        </ul>
      </article>
    </>
  );
}
