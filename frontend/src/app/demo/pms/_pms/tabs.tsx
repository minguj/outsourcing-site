"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  CONTRACT_ACTIONS,
  INVOICE_STATUS,
  todayKst,
  won,
  type AuditEntry,
  type Client,
  type Contract,
  type Invoice,
  type Resident,
  type ResidentRow,
  type Site,
  type Unit,
} from "./api";

export type TabProps = {
  api: Client;
  site: Site;
  sites: Site[];
  can: (perm: string) => boolean;
  month: string;
  setMonth: (m: string) => void;
  changed: () => void;
};

type Load<T> = { data: T | null; error: string | null; reload: () => void };

function useLoad<T>(fetcher: () => Promise<T>): Load<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    fetcher()
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
    // fetcher 는 탭이 다시 그려질 때마다 새로 만들어지므로 tick 으로만 다시 부른다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);
  return { data, error, reload: useCallback(() => setTick((t) => t + 1), []) };
}

function Notice({ error }: { error: string | null }) {
  return error ? <p className="pm-error">{error}</p> : null;
}

function errorText(e: unknown) {
  if (e instanceof ApiError) return `${e.message} (${e.status})`;
  return e instanceof Error ? e.message : "요청을 처리하지 못했습니다.";
}

// ---------- 운영 현황 ----------

type SiteSummary = { site: Site; units: Unit[] | null; invoices: Invoice[] | null };

export function OverviewTab({ api, sites, can, month }: TabProps) {
  const today = todayKst();
  const load = useLoad<SiteSummary[]>(() =>
    Promise.all(
      sites.map(async (site) => ({
        site,
        units: can("unit.read") ? await api.units(site.id) : null,
        invoices: can("billing.read") ? await api.invoices(site.id, month, today) : null,
      })),
    ),
  );
  return (
    <>
      <div className="pm-card-head">
        <h2>운영 현황</h2>
        <span className="pm-muted pm-small">볼 수 있는 사업장 {sites.length}곳 · {month} 청구 기준</span>
      </div>
      <Notice error={load.error} />
      <div className="pm-grid-2">
        {(load.data ?? []).map(({ site, units, invoices }) => {
          const occupied = units?.filter((u) => u.status === "occupied").length ?? 0;
          const usable = units?.filter((u) => u.status !== "maintenance").length ?? 0;
          const billed = invoices?.reduce((s, i) => s + i.total, 0) ?? 0;
          const left = invoices?.reduce((s, i) => s + i.outstanding, 0) ?? 0;
          return (
            <div key={site.id} className="pm-site">
              <div className="pm-site-head">
                <b>{site.name}</b>
                <span className="pm-tag">{site.asset_label}</span>
              </div>
              <div className="pm-stats">
                <Stat label="입주율" value={units ? `${usable ? Math.round((occupied / usable) * 100) : 0}%` : "권한 없음"} sub={units ? `${occupied}/${usable}실 (정비 제외)` : undefined} />
                <Stat label={`${month} 청구`} value={invoices ? won(billed) : "권한 없음"} sub={invoices ? `${invoices.length}건` : undefined} />
                <Stat label="미수금" value={invoices ? won(left) : "권한 없음"} sub={invoices && !invoices.length ? "청구 실행 전" : undefined} />
              </div>
            </div>
          );
        })}
      </div>
      <p className="pm-small pm-muted">
        모든 사업장이 같은 데이터 구조를 쓰고, 요금표·납부일·연체 이율만 사업장별로 다릅니다. 자산 유형이 늘어도 같은 코드로 동작합니다.
      </p>
    </>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="pm-stat">
      <span className="pm-stat-label">{label}</span>
      <span className="pm-stat-value">{value}</span>
      {sub && <span className="pm-stat-sub">{sub}</span>}
    </div>
  );
}

// ---------- 호실 현황판 ----------

export function UnitsTab({ api, site }: TabProps) {
  const load = useLoad(() => api.units(site.id));
  const floors = Array.from(new Set((load.data ?? []).map((u) => u.floor))).sort((a, b) => b - a);
  return (
    <>
      <div className="pm-card-head">
        <h2>호실 현황판</h2>
        <div className="pm-legend">
          {(["occupied", "reserved", "vacant", "maintenance"] as const).map((s) => (
            <span key={s} className={`pm-dot ${s}`}>{{ occupied: "입주", reserved: "입주 예정", vacant: "공실", maintenance: "정비" }[s]}</span>
          ))}
        </div>
      </div>
      <Notice error={load.error} />
      {floors.map((floor) => (
        <div key={floor} className="pm-floor">
          <span className="pm-floor-no">{floor}층</span>
          <div className="pm-floor-units">
            {load.data!
              .filter((u) => u.floor === floor)
              .map((u) => (
                <div key={u.id} className={`pm-unit ${u.status}`}>
                  <b>{u.building}{u.number}</b>
                  <span>{u.type}</span>
                  <span>{u.area_m2}㎡ · {u.status_label}</span>
                </div>
              ))}
          </div>
        </div>
      ))}
    </>
  );
}

// ---------- 입주자 ----------

export function ResidentsTab({ api, site, can }: TabProps) {
  const list = useLoad(() => api.residents(site.id));
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <>
      <div className="pm-card-head">
        <h2>입주자</h2>
        <span className="pm-muted pm-small">목록에는 이름·호실만 보이고, 상세에서 권한에 따라 연락처·건강정보가 열립니다.</span>
      </div>
      <Notice error={list.error} />
      <div className="pm-split">
        <ul className="pm-list">
          {(list.data ?? []).map((r: ResidentRow) => (
            <li key={r.id}>
              <button className={selected === r.id ? "on" : ""} onClick={() => setSelected(r.id)}>
                <b>{r.name}</b>
                <span className="pm-muted pm-small">{r.unit_number} · {r.status_label}</span>
              </button>
            </li>
          ))}
        </ul>
        <div>{selected ? <ResidentDetail key={selected} api={api} site={site} id={selected} canWrite={can("service.write")} /> : <p className="pm-muted">왼쪽에서 입주자를 고르세요.</p>}</div>
      </div>
    </>
  );
}

function ResidentDetail({ api, site, id, canWrite }: { api: Client; site: Site; id: string; canWrite: boolean }) {
  const load = useLoad<Resident>(() => api.resident(id));
  const r = load.data;
  if (load.error) return <Notice error={load.error} />;
  if (!r) return <p className="pm-muted">불러오는 중…</p>;
  return (
    <div className="pm-detail">
      <h3>
        {r.name} <span className="pm-muted pm-small">{r.birth_year}년생</span>
      </h3>
      <dl className="pm-dl">
        <dt>연락처</dt>
        <dd>{r.phone}</dd>
        <dt>보호자</dt>
        <dd>
          {r.guardian.name} ({r.guardian.relation}) · {r.guardian.phone}
        </dd>
        <dt>건강·돌봄</dt>
        <dd>
          {r.care ? (
            <>
              {r.care.level}
              {r.care.notes && <> · {r.care.notes}</>}
              {r.care.allergies.length > 0 && <> · 알레르기: {r.care.allergies.join(", ")}</>}
            </>
          ) : (
            <span className="pm-muted">이 역할에는 열람 권한이 없습니다</span>
          )}
        </dd>
      </dl>
      <p className="pm-small pm-muted">연락처·건강정보를 원문으로 보여 줄 때마다 서버가 감사 기록을 남깁니다.</p>
      {canWrite && r.status === "resident" && <UsageForm api={api} site={site} id={id} />}
    </div>
  );
}

function UsageForm({ api, site, id }: { api: Client; site: Site; id: string }) {
  const services = Object.entries(site.prices);
  const [service, setService] = useState(services[0]?.[0] ?? "");
  const [quantity, setQuantity] = useState(1);
  const [date, setDate] = useState(todayKst());
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <form
      className="pm-inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        api
          .addUsage(id, { service, quantity, date })
          .then(() => setMsg(`기록했습니다. ${date.slice(0, 7)} 청구에 포함됩니다.`))
          .catch((err) => setMsg(errorText(err)));
      }}
    >
      <b className="pm-small">서비스 이용 기록</b>
      <select value={service} onChange={(e) => setService(e.target.value)}>
        {services.map(([code, item]) => (
          <option key={code} value={code}>
            {item.label} {won(item.price)}
          </option>
        ))}
      </select>
      <input type="number" min={1} max={100} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} aria-label="수량" />
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="이용일" />
      <button className="pm-btn">기록</button>
      {msg && <span className="pm-small">{msg}</span>}
    </form>
  );
}

// ---------- 계약 ----------

const ORDER = ["signed", "active", "terminated", "cancelled"];

export function ContractsTab({ api, site, can }: TabProps) {
  const load = useLoad(() => api.contracts(site.id));
  const [msg, setMsg] = useState<string | null>(null);
  const act = (c: Contract, to: string) => {
    const date = to === "terminated" || to === "active" ? window.prompt(`${CONTRACT_ACTIONS[to]} 날짜 (YYYY-MM-DD)`, to === "active" ? c.start_date : todayKst()) : undefined;
    if (date === null) return;
    api
      .transition(c.id, to, date || undefined)
      .then((r) => {
        setMsg(`${r.resident_name} 계약을 '${r.status_label}'(으)로 바꿨습니다.`);
        load.reload();
      })
      .catch((e) => setMsg(errorText(e)));
  };
  return (
    <>
      <div className="pm-card-head">
        <h2>계약</h2>
        <span className="pm-muted pm-small">작성 중 → 체결 → 입주 → 해지 · 정비 중이거나 진행 중인 계약이 있는 호실은 막힙니다</span>
      </div>
      <Notice error={load.error} />
      {msg && <p className="pm-msg">{msg}</p>}
      <table className="pm-table">
        <thead>
          <tr>
            <th>호실</th>
            <th>입주자</th>
            <th>기간</th>
            <th className="num">보증금</th>
            <th className="num">월 이용료</th>
            <th>상태</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {(load.data ?? []).map((c) => (
            <tr key={c.id}>
              <td>{c.unit_number}</td>
              <td>{c.resident_name}</td>
              <td className="pm-small">
                {c.start_date} ~ {c.end_date ?? ""}
              </td>
              <td className="num">{won(c.deposit)}</td>
              <td className="num">{won(c.monthly_fee)}</td>
              <td>
                <span className={`pm-status c-${c.status}`}>{c.status_label}</span>
              </td>
              <td>
                <div className="pm-actions">
                {can("contract.write")
                  ? ORDER.filter((to) => c.next.includes(to)).map((to) => (
                      <button key={to} className="pm-btn pm-btn-sm" onClick={() => act(c, to)}>
                        {CONTRACT_ACTIONS[to]}
                      </button>
                    ))
                  : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!can("contract.write") && <p className="pm-small pm-muted">이 역할은 계약을 조회만 할 수 있습니다.</p>}
    </>
  );
}

// ---------- 청구·수납 ----------

export function BillingTab({ api, site, can, month, setMonth }: TabProps) {
  const [asOf, setAsOf] = useState(todayKst());
  const load = useLoad(() => api.invoices(site.id, month, asOf));
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const { reload } = load;
  useEffect(() => {
    reload();
  }, [month, asOf, reload]);
  const run = () =>
    api
      .runBilling(site.id, month)
      .then((r) => {
        setMsg(`청구서 ${r.created.length}건을 만들었습니다.${r.skipped.length ? ` 이미 만든 ${r.skipped.length}건은 건너뛰었습니다.` : ""}`);
        reload();
      })
      .catch((e) => setMsg(errorText(e)));
  const pay = (inv: Invoice) => {
    const raw = window.prompt(`받은 금액 (남은 금액 ${won(inv.outstanding)})`, String(inv.outstanding));
    if (!raw) return;
    api
      .pay(inv.id, Number(raw.replace(/[^\d]/g, "")), asOf, asOf)
      .then(() => {
        setMsg(`${inv.resident_name} 청구서에 수납을 기록했습니다.`);
        reload();
      })
      .catch((e) => setMsg(errorText(e)));
  };
  const total = (load.data ?? []).reduce((s, i) => s + i.total, 0);
  const left = (load.data ?? []).reduce((s, i) => s + i.outstanding, 0);
  const late = (load.data ?? []).reduce((s, i) => s + i.late_fee, 0);
  return (
    <>
      <div className="pm-card-head">
        <h2>청구·수납</h2>
        <div className="pm-toolbar-inline">
          <label className="pm-field">
            청구 월
            <input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </label>
          <label className="pm-field">
            기준일
            <input type="date" value={asOf} onChange={(e) => e.target.value && setAsOf(e.target.value)} />
          </label>
          {can("billing.write") && (
            <button className="pm-btn" onClick={run}>
              {month} 월 청구 실행
            </button>
          )}
        </div>
      </div>
      <p className="pm-small pm-muted">
        월 이용료는 그 달에 계약이 유효한 날수만큼 일할 계산하고, 서비스 이용료를 더합니다. 기준일을 납부 기한 뒤로 옮기면 연체료가 계산됩니다. 같은 달을 다시
        실행해도 청구서는 한 번만 만들어집니다.
      </p>
      <Notice error={load.error} />
      {msg && <p className="pm-msg">{msg}</p>}
      {load.data && load.data.length === 0 ? (
        <p className="pm-muted">{month} 청구서가 없습니다.{can("billing.write") ? " ‘월 청구 실행’을 눌러 보세요." : ""}</p>
      ) : (
        <table className="pm-table">
          <thead>
            <tr>
              <th>호실</th>
              <th>입주자</th>
              <th className="num">청구액</th>
              <th className="num">납부</th>
              <th className="num">미수금</th>
              <th className="num">연체료</th>
              <th>납부 기한</th>
              <th>상태</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(load.data ?? []).map((inv) => (
              <InvoiceRows key={inv.id} inv={inv} open={open === inv.id} toggle={() => setOpen(open === inv.id ? null : inv.id)} canPay={can("billing.write")} pay={() => pay(inv)} />
            ))}
          </tbody>
          {load.data && load.data.length > 0 && (
            <tfoot>
              <tr>
                <td colSpan={2}>합계</td>
                <td className="num">{won(total)}</td>
                <td className="num">{won(total - left)}</td>
                <td className="num">{won(left)}</td>
                <td className="num">{won(late)}</td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          )}
        </table>
      )}
    </>
  );
}

function InvoiceRows({ inv, open, toggle, canPay, pay }: { inv: Invoice; open: boolean; toggle: () => void; canPay: boolean; pay: () => void }) {
  return (
    <>
      <tr>
        <td>{inv.unit_number}</td>
        <td>
          <button className="pm-link" onClick={toggle} aria-expanded={open}>
            {inv.resident_name} {open ? "▴" : "▾"}
          </button>
        </td>
        <td className="num">{won(inv.total)}</td>
        <td className="num">{won(inv.paid)}</td>
        <td className="num">{won(inv.outstanding)}</td>
        <td className="num">{inv.late_fee ? won(inv.late_fee) : "-"}</td>
        <td>{inv.due_date}</td>
        <td>
          <span className={`pm-status i-${inv.status}`}>{INVOICE_STATUS[inv.status]}</span>
        </td>
        <td>
          <div className="pm-actions">
            {canPay && inv.outstanding > 0 && (
              <button className="pm-btn pm-btn-sm" onClick={pay}>
                수납
              </button>
            )}
          </div>
        </td>
      </tr>
      {open && (
        <tr className="pm-subrow">
          <td />
          <td colSpan={8}>
            {inv.lines.map((l) => (
              <div key={l.code} className="pm-line">
                <span>{l.label}</span>
                <span className="pm-muted">
                  {l.quantity} × {won(l.unit_price)}
                </span>
                <b>{won(l.amount)}</b>
              </div>
            ))}
            {inv.payments.map((p) => (
              <div key={p.id} className="pm-line pm-muted">
                <span>수납 {p.paid_on}</span>
                <span />
                <span>-{won(p.amount)}</span>
              </div>
            ))}
          </td>
        </tr>
      )}
    </>
  );
}

// ---------- 감사 기록 ----------

const FIELD_LABELS: Record<string, string> = { phone: "연락처", care: "건강·돌봄 정보" };

export function AuditTab({ api }: TabProps) {
  const load = useLoad<AuditEntry[]>(() => api.audit());
  return (
    <>
      <div className="pm-card-head">
        <h2>감사 기록</h2>
        <span className="pm-muted pm-small">누가 언제 어떤 입주자의 민감 정보를 원문으로 봤는지 남깁니다 (볼 수 있는 사업장 범위만)</span>
      </div>
      <Notice error={load.error} />
      {load.data && load.data.length === 0 ? (
        <p className="pm-muted">아직 기록이 없습니다. 다른 역할로 입주자 상세를 열어 본 뒤 돌아와 보세요.</p>
      ) : (
        <table className="pm-table">
          <thead>
            <tr>
              <th>시각</th>
              <th>사용자</th>
              <th>대상</th>
              <th>열람 항목</th>
            </tr>
          </thead>
          <tbody>
            {(load.data ?? [])
              .slice()
              .reverse()
              .map((e, i) => (
                <tr key={i}>
                  <td className="pm-small">{e.at.replace("T", " ").slice(0, 19)}</td>
                  <td>{e.user_name}</td>
                  <td>{e.target_name}</td>
                  <td>{e.fields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}</td>
                </tr>
              ))}
          </tbody>
        </table>
      )}
    </>
  );
}
