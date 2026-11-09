"use client";

import { useState } from "react";
import { Feasibility, Scenario, TraceStep, Warning } from "./api";
import { SOURCE_KIND, area, gradeLabel, krw, n } from "./format";

export function Warnings({ items }: { items: Warning[] }) {
  if (!items.length) return null;
  const order = { critical: 0, warning: 1, info: 2 };
  return (
    <div>
      {[...items]
        .sort((a, b) => order[a.severity] - order[b.severity])
        .map((w, i) => (
          <div key={i} className={`zb-alert ${w.severity}`}>
            <strong>{w.severity === "critical" ? "확인 필요" : w.severity === "warning" ? "주의" : "참고"}</strong>
            <span>{w.message}</span>
          </div>
        ))}
    </div>
  );
}

export function MassingSummary({ r }: { r: Feasibility }) {
  const m = r.massing;
  return (
    <div className="zb-grid zb-grid-3">
      <Stat
        label="적용 건폐율 / 용적률"
        value={`${m.bcr_pct}% / ${m.far_effective_pct}%`}
        sub={`건폐율 ${m.bcr_used_pct}% 사용${m.far_effective_pct !== m.far_pct ? ` · 인센티브 전 용적률 ${m.far_pct}%` : ""}`}
      />
      <Stat label="계획 지상 연면적" value={area(m.gfa_m2)} sub={`최대 ${area(m.max_gfa_m2)} 중 ${m.far_utilization_pct}% 사용`} />
      <Stat label="규모" value={`지상 ${m.floors}층 · ${n(m.height_m, 1)}m`} sub={`기준층 ${area(m.building_area_m2)} · 결정 조건: ${m.binding_constraint}`} />
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="zb-stat">
      <div className="zb-stat-label">{label}</div>
      <div className="zb-stat-value">{value}</div>
      {sub && <div className="zb-stat-sub">{sub}</div>}
    </div>
  );
}

/** 대지·건축면적·층수를 단면으로 보여주는 단순 매스 다이어그램 */
export function MassingSketch({ r }: { r: Feasibility }) {
  const m = r.massing;
  const W = 520, H = 220, ground = 190;
  const siteW = 440;
  const bw = Math.max(24, siteW * Math.sqrt(m.building_area_m2 / r.site.site_area_m2));
  const maxH = Math.max(m.height_m, r.options.height_limit_m ?? 0, 12);
  const scale = Math.min(150 / maxH, 10);
  const floorPx = m.floor_height_m * scale;
  const x0 = (W - siteW) / 2;
  const bx = x0 + (siteW - bw) / 2;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: 560, display: "block", margin: "0 auto" }} role="img" aria-label={`지상 ${m.floors}층 매스 단면`}>
      <line x1={x0} y1={ground} x2={x0 + siteW} y2={ground} stroke="#7c8983" strokeWidth={1.5} />
      <text x={x0} y={ground + 18} fontSize={11} fill="#7c8983">대지 {area(r.site.site_area_m2)}</text>
      {Array.from({ length: m.floors }).map((_, i) => (
        <rect key={i} x={bx} y={ground - (i + 1) * floorPx} width={bw} height={floorPx} fill={i === m.floors - 1 ? "#9fe1cb" : "#e1f5ee"} stroke="#0f6e56" strokeWidth={0.6} />
      ))}
      <rect x={bx} y={ground - m.floors * floorPx - 4} width={bw} height={4} fill="#ef9f27" />
      <text x={bx + bw + 8} y={ground - m.floors * floorPx + 12} fontSize={11} fill="#854f0b">옥상 태양광</text>
      {r.options.height_limit_m && (
        <>
          <line x1={x0} x2={x0 + siteW} y1={ground - r.options.height_limit_m * scale} y2={ground - r.options.height_limit_m * scale} stroke="#a32d2d" strokeDasharray="4 4" />
          <text x={x0} y={ground - r.options.height_limit_m * scale - 6} fontSize={11} fill="#a32d2d">높이 제한 {r.options.height_limit_m}m</text>
        </>
      )}
      <text x={bx + bw / 2} y={ground - m.floors * floorPx - 10} fontSize={11} fill="#4b5852" textAnchor="middle">{m.floors}층 · {n(m.height_m, 1)}m</text>
    </svg>
  );
}

export function ScenarioChart({ r }: { r: Feasibility }) {
  const s = r.scenarios;
  const W = 640, H = 230, padL = 44, padB = 34, padT = 14;
  const maxPct = Math.max(130, ...s.map((x) => x.achieved_pct));
  const y = (p: number) => H - padB - ((H - padB - padT) * p) / maxPct;
  const bw = (W - padL - 10) / s.length;
  const potential = r.energy.max_self_sufficiency_pct;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="등급별 목표 대비 달성 자립률">
      {[0, 20, 40, 60, 80, 100, 120].map((p) => (
        <g key={p}>
          <line x1={padL} x2={W - 6} y1={y(p)} y2={y(p)} stroke="#e2e6e3" />
          <text x={padL - 6} y={y(p) + 4} fontSize={10.5} fill="#7c8983" textAnchor="end">{p}%</text>
        </g>
      ))}
      <line x1={padL} x2={W - 6} y1={y(potential)} y2={y(potential)} stroke="#a32d2d" strokeDasharray="5 4" />
      <text x={W - 8} y={y(potential) - 5} fontSize={11} fill="#a32d2d" textAnchor="end">설치 가능 최대 {potential}%</text>
      {s.map((sc, i) => {
        const x = padL + i * bw + bw * 0.2;
        const w = bw * 0.6;
        return (
          <g key={sc.target_grade}>
            <rect x={x} y={y(sc.achieved_pct)} width={w} height={y(0) - y(sc.achieved_pct)} rx={3} fill={sc.feasible ? (sc.mandatory ? "#0f6e56" : "#5dcaa5") : "#d3d1c7"} />
            <line x1={x - 4} x2={x + w + 4} y1={y(sc.required_pct)} y2={y(sc.required_pct)} stroke="#17201c" strokeWidth={1.5} />
            <text x={x + w / 2} y={H - padB + 16} fontSize={11.5} fill="#17201c" textAnchor="middle">{gradeLabel(sc.target_grade)}</text>
            <text x={x + w / 2} y={H - padB + 29} fontSize={10.5} fill="#7c8983" textAnchor="middle">{sc.feasible ? krw(sc.total_cost_krw) : "불가"}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function ScenarioTable({ scenarios, compact = false }: { scenarios: Scenario[]; compact?: boolean }) {
  return (
    <table>
      <thead>
        <tr>
          <th>목표</th>
          <th className="num">필요</th>
          <th className="num">달성</th>
          <th>설비 조합</th>
          <th className="num">도입비용</th>
          {!compact && <th className="num">㎡당</th>}
        </tr>
      </thead>
      <tbody>
        {scenarios.map((s) => (
          <tr key={s.target_grade} className={`${s.mandatory ? "mandatory" : ""} ${s.feasible ? "" : "infeasible"}`}>
            <td>
              <strong>{s.target_label}</strong> {s.mandatory && <span className="zb-pill ok">의무</span>}
              {!s.feasible && <span className="zb-pill crit" style={{ marginLeft: 4 }}>불가</span>}
            </td>
            <td className="num">{s.required_pct}%</td>
            <td className="num">{s.achieved_pct}%</td>
            <td>
              {s.picks.length === 0 ? "—" : s.picks.map((p) => (
                <div key={p.key} className="zb-small">
                  {p.name} {n(p.units)}{p.unit}
                  {p.utilization_pct >= 100 && <span className="zb-muted"> (한계까지)</span>}
                </div>
              ))}
              {s.note && <div className="zb-small" style={{ color: "var(--crit)" }}>{s.note}</div>}
            </td>
            <td className="num">{krw(s.total_cost_krw)}</td>
            {!compact && <td className="num">{n(s.cost_per_gfa_krw)}원</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function EquipmentTable({ r }: { r: Feasibility }) {
  return (
    <table>
      <thead>
        <tr>
          <th>설비</th>
          <th className="num">최대 설치량</th>
          <th className="num">단위 순생산량</th>
          <th className="num">kWh당 비용</th>
          <th>설치 한계</th>
        </tr>
      </thead>
      <tbody>
        {r.energy.options.map((o) => (
          <tr key={o.key}>
            <td>{o.name}</td>
            <td className="num">{n(o.max_units)} {o.unit}</td>
            <td className="num">{n(o.production_per_unit)} kWh/yr</td>
            <td className="num">{o.cost_per_kwh ? `${n(o.cost_per_kwh)}원` : "—"}</td>
            <td className="zb-small zb-muted">{o.limit_reason}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function TracePanel({ steps, filter }: { steps: TraceStep[]; filter?: (s: TraceStep) => boolean }) {
  const list = filter ? steps.filter(filter) : steps;
  return (
    <div>
      {list.map((s) => (
        <details key={s.key} className="zb-trace-item">
          <summary>
            <span>
              {s.label}{" "}
              {s.needs_review && <span className="zb-pill warn">검토 필요</span>}
            </span>
            <strong style={{ fontVariantNumeric: "tabular-nums" }}>
              {typeof s.value === "number" ? n(s.value, s.value % 1 ? 2 : 0) : s.value} {s.unit}
            </strong>
          </summary>
          <dl className="zb-kv">
            <dt>산식</dt>
            <dd>{s.formula}</dd>
            {Object.keys(s.inputs).length > 0 && (
              <>
                <dt>입력</dt>
                <dd>
                  {Object.entries(s.inputs).map(([k, v]) => (
                    <span key={k} className="zb-pill" style={{ marginRight: 4, marginBottom: 2 }}>
                      {k} {typeof v === "number" ? n(v, v % 1 ? 2 : 0) : v}
                    </span>
                  ))}
                </dd>
              </>
            )}
            {s.sources.map((src) => (
              <SourceRow key={src.id} src={src} />
            ))}
          </dl>
        </details>
      ))}
    </div>
  );
}

function SourceRow({ src }: { src: TraceStep["sources"][number] }) {
  return (
    <>
      <dt>{SOURCE_KIND[src.kind] ?? "근거"}</dt>
      <dd>
        {src.url ? <a href={src.url} target="_blank" rel="noreferrer">{src.title}</a> : src.title}
        {src.ref && <span className="zb-muted"> · {src.ref}</span>}{" "}
        {src.kind !== "input" && src.kind !== "assumption" && (
          <span className={`zb-pill ${src.verified ? "ok" : "warn"}`}>{src.verified ? "근거 확인" : "미검증"}</span>
        )}
        {src.note && <div className="zb-small zb-muted">{src.note}</div>}
      </dd>
    </>
  );
}

/** 토지이용계획을 관계별로 보여 준다. 접함(인접 필지)은 규제 판단에 쓰지 않으므로 흐리게 표시. */
export function LandUsePlans({ site }: { site: Feasibility["site"] }) {
  const groups: [string, string[], string][] = [
    ["포함", site.land_use_plans, ""],
    ["일부 걸침", site.partial_plans ?? [], ""],
    ["인접(규제 판단 제외)", site.adjacent_plans ?? [], "zb-muted"],
  ];
  return (
    <div className="zb-small">
      {groups
        .filter(([, items]) => items.length > 0)
        .map(([label, items, cls]) => (
          <div key={label} className={cls}>
            <strong>{label}</strong> {items.join(" · ")}
          </div>
        ))}
    </div>
  );
}

const CAP_LABEL: Record<string, string> = { 높이: "높이 제한", 층수: "용도지역 층수 제한" };

/** 층수 선택. 범위는 1층 ~ 제한에 따른 최대 층수. 드래그 중에는 계산하지 않고 놓을 때 반영한다. */
export function FloorControl({ r, onCommit }: { r: Feasibility; onCommit: (floors: string | null) => void }) {
  const m = r.massing;
  const max = m.floors_max ?? Math.max(60, m.floors_min_full_far * 3);
  const [v, setV] = useState(m.floors);
  const commit = (x: number) => x !== m.floors && onCommit(String(x));
  const capText =
    m.floors_max == null
      ? "높이 제한을 입력하면 최대 층수가 정해져요"
      : m.floors_max_reason === "높이"
        ? `최대 ${m.floors_max}층 (높이 제한 ${r.options.height_limit_m}m ÷ 층고 ${m.floor_height_m}m)`
        : `최대 ${m.floors_max}층 (${CAP_LABEL[m.floors_max_reason ?? ""] ?? m.floors_max_reason})`;
  return (
    <div className="zb-field" style={{ marginBottom: 16 }}>
      <span style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--ink-2)", marginBottom: 4 }}>
        <span>층수</span>
        <strong style={{ color: "var(--ink)" }}>
          {v}층 {v < m.floors_min_full_far && <span className="zb-pill warn">연면적 감소</span>}
        </strong>
      </span>
      <input
        type="range"
        min={1}
        max={max}
        value={Math.min(v, max)}
        aria-label="층수"
        onChange={(e) => setV(Number(e.target.value))}
        onPointerUp={() => commit(v)}
        onKeyUp={() => commit(v)}
        onBlur={() => commit(v)}
      />
      <div className="zb-small zb-muted">
        용적률을 다 쓰는 최소 {m.floors_min_full_far}층 · {capText}
      </div>
      {r.options.target_floors != null && (
        <button type="button" className="zb-btn-ghost zb-btn-small" onClick={() => onCommit(null)}>
          최소 층수로 되돌리기
        </button>
      )}
    </div>
  );
}

/** 높이를 제한하지만 높이값이 데이터에 없는 지역·지구에 포함된 경우 안내 */
export function HeightPlanHint({ plans }: { plans: string[] }) {
  if (!plans.length) return null;
  return (
    <div className="zb-small" style={{ color: "var(--warn)", marginTop: 4 }}>
      {plans.join(", ")}에 포함됩니다. 고시된 높이를 확인해 입력하세요.
    </div>
  );
}
