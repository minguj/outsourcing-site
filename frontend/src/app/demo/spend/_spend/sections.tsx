"use client";

import { useEffect, useState } from "react";
import { shortDate, WEEKDAYS, won, type Analysis, type Client, type Registry, type Series, type Tx } from "./api";

type CancelFn = (id: string, action: "request" | "confirm" | "undo") => void;

const SOURCE_CLASS: Record<Series["source"], string> = { dictionary: "src-dict", ai: "src-ai", rule: "src-rule" };

function amountText(s: Series) {
  if (s.amount_type === "variable") return `약 ${won(s.expected_amount)}`;
  if (s.amount_type === "fx") return `약 ${won(s.expected_amount)}`;
  return won(s.expected_amount);
}

function perText(s: Series) {
  if (s.cadence === "weekly") return `매주 · 월 ${won(s.monthly_equivalent)}`;
  if (s.cadence === "yearly") return `매년 · 월 ${won(s.monthly_equivalent)}`;
  return "매월";
}

// ---------- 구독·고정지출 목록 ----------

export function SeriesList({
  view,
  onReview,
  onCancel,
  onShowTransactions,
}: {
  view: Analysis;
  onReview: (id: string, decision: "confirm" | "reject" | "reset") => void;
  onCancel: CancelFn;
  onShowTransactions: (id: string) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const isDone = (s: Series) => s.cancel?.status === "done";
  const active = view.series.filter((s) => s.status === "active" && s.review !== "reject" && !isDone(s));
  const cancelled = view.series.filter((s) => s.status === "cancelled" && s.review !== "reject" && !isDone(s));
  const rejected = view.series.filter((s) => s.review === "reject" && !isDone(s));
  const done = view.series.filter(isDone);
  const row = (s: Series) => (
    <SeriesRow
      key={s.id}
      s={s}
      open={open === s.id}
      toggle={() => setOpen(open === s.id ? null : s.id)}
      onReview={onReview}
      onCancel={onCancel}
      onShowTransactions={onShowTransactions}
    />
  );
  return (
    <>
      <div className="sp-card-head">
        <h2>찾아낸 반복 결제 {active.length}건</h2>
        <span className="sp-small sp-muted">월 환산 금액이 큰 순서 · 항목을 누르면 근거를 볼 수 있어요</span>
      </div>
      <ul className="sp-series">{active.map(row)}</ul>
      {cancelled.length > 0 && (
        <>
          <h3 className="sp-h3">해지된 것으로 보이는 결제</h3>
          <ul className="sp-series is-dim">{cancelled.map(row)}</ul>
        </>
      )}
      {done.length > 0 && (
        <>
          <h3 className="sp-h3">해지 완료 (가상 처리 · 합계에서 제외)</h3>
          <ul className="sp-series is-dim">{done.map(row)}</ul>
        </>
      )}
      {rejected.length > 0 && (
        <>
          <h3 className="sp-h3">구독이 아니라고 표시한 항목 (합계에서 제외)</h3>
          <ul className="sp-series is-dim">{rejected.map(row)}</ul>
        </>
      )}
    </>
  );
}

function SeriesRow({
  s,
  open,
  toggle,
  onReview,
  onCancel,
  onShowTransactions,
}: {
  s: Series;
  open: boolean;
  toggle: () => void;
  onReview: (id: string, decision: "confirm" | "reject" | "reset") => void;
  onCancel: CancelFn;
  onShowTransactions: (id: string) => void;
}) {
  const signals = s.signals.filter((g) => g.type !== "likely_cancelled");
  return (
    <li className={`sp-item ${open ? "is-open" : ""}`}>
      <button className="sp-item-main" onClick={toggle} aria-expanded={open}>
        <span className="sp-item-name">
          <strong>{s.service}</strong>
          <span className="sp-tags">
            <span className="sp-tag">{s.category_label}</span>
            <span className={`sp-tag ${s.kind === "fixed" ? "kind-fixed" : "kind-sub"}`}>{s.kind_label}</span>
            {signals.map((g) => (
              <span key={g.type} className={`sp-tag sig-${g.type}`}>
                {g.label}
              </span>
            ))}
            {s.cancel && <span className={`sp-tag cancel-${s.cancel.status}`}>{s.cancel.status_label}</span>}
          </span>
        </span>
        <span className="sp-item-amount">
          <strong>{amountText(s)}</strong>
          <span className="sp-small sp-muted">{perText(s)}</span>
        </span>
        <span className="sp-item-next">
          {s.cancel?.status === "done" ? (
            <span className="sp-small sp-muted">해지 완료</span>
          ) : s.status === "active" ? (
            <>
              <span className="sp-small sp-muted">다음 결제</span>
              <span>{shortDate(s.next_date)}</span>
            </>
          ) : (
            <span className="sp-small sp-muted">마지막 {shortDate(s.last_date)}</span>
          )}
        </span>
      </button>
      {open && (
        <div className="sp-item-detail">
          <dl className="sp-facts">
            <div>
              <dt>거래내역에 찍힌 이름</dt>
              <dd>
                {s.aliases.join(" · ")}
                {s.aliases.length > 1 && <span className="sp-small sp-muted"> (표기가 달라도 같은 서비스로 묶음)</span>}
              </dd>
            </div>
            <div>
              <dt>서비스 정보</dt>
              <dd>
                <span className={`sp-tag ${SOURCE_CLASS[s.source]}`}>{s.source_label}</span>
                {s.reason && <span className="sp-small"> {s.reason}</span>}
              </dd>
            </div>
            <div>
              <dt>결제 기록</dt>
              <dd>
                {s.cadence_label} {s.count}회 ({s.first_date} ~ {s.last_date})
              </dd>
            </div>
            <div>
              <dt>금액</dt>
              <dd>
                {s.amount_label}
                {s.amount_type !== "fixed" && ` · 예상 ${won(s.expected_amount)} (최근 ${won(s.last_amount)})`}
              </dd>
            </div>
            <div>
              <dt>반복 결제일 확률</dt>
              <dd>
                <span className="sp-meter" aria-hidden>
                  <span style={{ width: `${s.confidence}%` }} />
                </span>{" "}
                {s.confidence}%{s.review === "confirm" && " · 직접 확인함"}
              </dd>
            </div>
          </dl>
          {s.signals.length > 0 && (
            <ul className="sp-signal-lines">
              {s.signals.map((g, i) => (
                <li key={i}>
                  <b>{g.label}</b> {g.detail}
                </li>
              ))}
            </ul>
          )}
          <CancelBox s={s} onCancel={onCancel} />
          <div className="sp-actions">
            <span className="sp-small sp-muted">맞게 찾았나요?</span>
            {s.review === null ? (
              <>
                <button className="sp-btn sp-btn-sm" onClick={() => onReview(s.id, "confirm")}>
                  맞아요
                </button>
                <button className="sp-btn sp-btn-sm sp-btn-ghost" onClick={() => onReview(s.id, "reject")}>
                  구독이 아니에요
                </button>
              </>
            ) : (
              <button className="sp-btn sp-btn-sm sp-btn-ghost" onClick={() => onReview(s.id, "reset")}>
                되돌리기
              </button>
            )}
            <button className="sp-link" onClick={() => onShowTransactions(s.id)}>
              묶인 거래 {s.transaction_ids.length}건 보기 →
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

function CancelBox({ s, onCancel }: { s: Series; onCancel: CancelFn }) {
  if (s.kind === "fixed") {
    return <p className="sp-small sp-muted sp-cancel-note">고정지출은 해지 대상이 아니에요. 요금제 변경은 각 회사에서 할 수 있어요.</p>;
  }
  if (!s.cancel) {
    if (s.status !== "active" || s.review === "reject") return null;
    return (
      <div className="sp-cancel">
        <div>
          <b>해지하기</b>{" "}
          <span className="sp-small sp-muted">
            {s.cancel_method === "easy" ? "간편해지 · 데모라 실제 해지는 일어나지 않아요" : "해지 방법을 안내해 드려요"}
          </span>
        </div>
        <button className="sp-btn sp-btn-sm" onClick={() => onCancel(s.id, "request")}>
          {s.cancel_method === "easy" ? "간편해지 요청" : "해지 방법 보기"}
        </button>
      </div>
    );
  }
  const c = s.cancel;
  return (
    <div className={`sp-cancel is-${c.status}`}>
      <div>
        <b>{c.status_label}</b>
        {c.method === "easy" && <span className="sp-small sp-muted"> {c.method_label}</span>}
        {c.status === "processing" && <div className="sp-small">서비스에 해지를 요청했어요. 잠시 뒤 결과가 반영돼요.</div>}
        {c.status === "done" && <div className="sp-small">{c.done_at?.replace("T", " ").slice(0, 16)} 완료 · 다음 결제부터 나가지 않아요.</div>}
        {c.status === "guide" && c.steps && (
          <ol className="sp-steps">
            {c.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        )}
      </div>
      <div className="sp-cancel-actions">
        {c.status === "guide" && (
          <button className="sp-btn sp-btn-sm" onClick={() => onCancel(s.id, "confirm")}>
            해지했어요
          </button>
        )}
        <button className="sp-btn sp-btn-sm sp-btn-ghost" onClick={() => onCancel(s.id, "undo")}>
          되돌리기
        </button>
      </div>
    </div>
  );
}

// ---------- 결제 예정 ----------

export function UpcomingList({ view }: { view: Analysis }) {
  const days = new Map<string, Analysis["upcoming"]>();
  for (const u of view.upcoming) days.set(u.date, [...(days.get(u.date) ?? []), u]);
  const total = view.upcoming.reduce((sum, u) => sum + u.amount, 0);
  return (
    <>
      <div className="sp-card-head">
        <h2>앞으로 30일 결제 예정</h2>
        <span className="sp-small sp-muted">
          {view.upcoming.length}건 · 약 {won(total)} · 기준일 {view.as_of} 다음 날부터
        </span>
      </div>
      {view.upcoming.length === 0 ? (
        <p className="sp-muted">30일 안에 예정된 반복 결제가 없어요.</p>
      ) : (
        <ol className="sp-days">
          {[...days.entries()].map(([d, items]) => {
            const [y, m, dd] = d.split("-").map(Number);
            const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, dd)).getUTCDay()];
            return (
              <li key={d} className="sp-day">
                <div className="sp-day-date">
                  <strong>{shortDate(d)}</strong>
                  <span>{weekday}</span>
                </div>
                <ul>
                  {items.map((u) => (
                    <li key={u.series_id + u.date}>
                      <span>{u.service}</span>
                      <span className="sp-tabnum">
                        {u.amount_type === "fixed" ? "" : "약 "}
                        {won(u.amount)}
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ol>
      )}
    </>
  );
}

// ---------- 원본 거래내역 ----------

type Filter = "all" | "linked" | "other";

export function TransactionsTable({ view, focus, onFocus }: { view: Analysis; focus: string | null; onFocus: (id: string | null) => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const names = new Map(view.series.map((s) => [s.id, s.service]));
  const accounts = new Map(view.persona.accounts.map((a) => [a.id, a.label]));
  const cancelledIds = new Set(view.transactions.filter((t) => t.type === "cancel").map((t) => t.approval_id));
  const rows = view.transactions.filter((t) => {
    if (focus) return t.series_id === focus;
    if (filter === "linked") return t.series_id !== null;
    if (filter === "other") return t.series_id === null;
    return true;
  });
  return (
    <>
      <div className="sp-card-head">
        <h2>원본 거래내역</h2>
        {focus ? (
          <button className="sp-btn sp-btn-sm sp-btn-ghost" onClick={() => onFocus(null)}>
            {names.get(focus)} 묶음만 보는 중 · 전체 보기
          </button>
        ) : (
          <div className="sp-seg" role="radiogroup">
            {(
              [
                ["all", `전체 ${view.transactions.length}건`],
                ["linked", "반복 결제로 묶인 거래"],
                ["other", "일반 소비"],
              ] as [Filter, string][]
            ).map(([key, label]) => (
              <button key={key} role="radio" aria-checked={filter === key} className={filter === key ? "is-on" : ""} onClick={() => setFilter(key)}>
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="sp-table-wrap">
        <table className="sp-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>거래내역에 찍힌 이름</th>
              <th className="num">금액</th>
              <th>결제 수단</th>
              <th>묶인 항목</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <TxRow key={t.id} t={t} name={t.series_id ? names.get(t.series_id) : undefined} account={accounts.get(t.account)} cancelled={cancelledIds.has(t.id)} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function TxRow({ t, name, account, cancelled }: { t: Tx; name?: string; account?: string; cancelled: boolean }) {
  const isCancel = t.type === "cancel";
  return (
    <tr className={isCancel || cancelled ? "is-dim" : ""}>
      <td className="sp-small">{t.date}</td>
      <td>
        {t.merchant_raw}
        {isCancel && <span className="sp-tag sig-likely_cancelled"> 승인취소</span>}
        {cancelled && <span className="sp-tag"> 취소됨</span>}
      </td>
      <td className="num sp-tabnum">
        {isCancel ? "-" : ""}
        {won(t.amount)}
        {t.orig_currency && (
          <div className="sp-small sp-muted">
            {t.orig_currency} {t.orig_amount}
          </div>
        )}
      </td>
      <td className="sp-small">
        {account}
        {t.method === "auto_transfer" && " · 자동이체"}
      </td>
      <td className="sp-small">{name ?? <span className="sp-muted">-</span>}</td>
    </tr>
  );
}

// ---------- 오른쪽: 절감 후보·신호 ----------

export function SavingsPanel({ view }: { view: Analysis }) {
  const best = view.savings_total;
  return (
    <section className="sp-card sp-side">
      <h2>줄일 수 있는 돈</h2>
      {view.savings.length === 0 ? (
        <p className="sp-muted sp-small">지금은 눈에 띄는 절감 후보가 없어요.</p>
      ) : (
        <>
          {best > 0 && (
            <p className="sp-save-total">
              정리하면 매달 최소 <strong>{won(best)}</strong>
              <span className="sp-small sp-muted"> · 1년 {won(best * 12)} (같은 구독은 한 번만 계산)</span>
            </p>
          )}
          <ul className="sp-savings">
            {view.savings.map((s, i) => (
              <li key={i} className={`save-${s.type}`}>
                <div className="sp-save-head">
                  <b>{s.title}</b>
                  <span className="sp-tabnum">{s.type === "price" ? `+${won(s.monthly)}/월` : `-${won(s.monthly)}/월`}</span>
                </div>
                <p className="sp-small">{s.detail}</p>
                {s.services.length > 1 && <p className="sp-small sp-muted">{s.services.join(" · ")}</p>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function SignalsPanel({ view }: { view: Analysis }) {
  const soon = view.alerts;
  const items = view.series
    .filter((s) => s.review !== "reject" && s.cancel?.status !== "done")
    .flatMap((s) => s.signals.filter((g) => g.type !== "duplicate" && g.type !== "fx").map((g) => ({ ...g, service: s.service })))
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
  return (
    <section className="sp-card sp-side">
      <h2>알림</h2>
      {soon.length > 0 && (
        <ul className="sp-soon">
          {soon.map((a) => (
            <li key={a.series_id + a.date}>
              <span className="sp-dday">D-{a.d_day}</span>
              <span>
                <b>{a.service}</b> {shortDate(a.date)} 결제 예정
              </span>
              <span className="sp-tabnum">
                {a.amount_type === "fixed" ? "" : "약 "}
                {won(a.amount)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {items.length === 0 ? (
        <p className="sp-muted sp-small">새로운 변화가 없어요.</p>
      ) : (
        <ul className="sp-alerts">
          {items.map((g, i) => (
            <li key={i} className={`sig-line sig-${g.type}`}>
              <span className={`sp-tag sig-${g.type}`}>{g.label}</span>
              <b>{g.service}</b>
              <p className="sp-small">{g.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------- 가맹점 사전 ----------

export function MerchantsTab({ api, version }: { api: Client; version: Analysis }) {
  const [data, setData] = useState<Registry | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .merchants()
      .then(setData)
      .catch(() => setError("가맹점 사전을 불러오지 못했습니다."));
  }, [api, version]);
  if (error) return <p className="sp-muted">{error}</p>;
  if (!data) return <p className="sp-muted">불러오는 중…</p>;
  const st = data.stats;
  return (
    <>
      <div className="sp-card-head">
        <h2>가맹점 사전</h2>
        <span className="sp-small sp-muted">가상 사용자 3명의 반복 결제 가맹점 전체</span>
      </div>
      <p className="sp-small sp-muted">
        거래내역의 가맹점명은 결제대행·법인 표기 때문에 제각각이라, 정리한 이름(key)과 서비스 사전으로 같은 서비스를 묶습니다. 사전에 없는 가맹점은 AI가 정리하고, 사용자
        확인(맞아요·구독 아님)은 제보로 쌓입니다. 제보는 사전을 바로 바꾸지 않고, &apos;구독 아님&apos;이 2건 이상이면 검수 대기로 표시합니다.
      </p>
      <div className="sp-intel-stats">
        <div>
          <strong>{st.coverage_pct}%</strong>
          <span>정리율 (사전 + AI)</span>
        </div>
        <div>
          <strong>{st.recurring_merchants}</strong>
          <span>반복 결제 가맹점</span>
        </div>
        <div>
          <strong>
            {st.dictionary} / {st.ai} / {st.rule}
          </strong>
          <span>사전 / AI / 미정리</span>
        </div>
        <div>
          <strong>{st.alias_merchants}</strong>
          <span>표기가 여러 개인 서비스</span>
        </div>
      </div>
      <div className="sp-table-wrap">
        <table className="sp-table">
          <thead>
            <tr>
              <th>서비스</th>
              <th>출처</th>
              <th>거래내역에 찍힌 표기</th>
              <th>사용자</th>
              <th className="sp-nowrap">제보 ✓·✕</th>
            </tr>
          </thead>
          <tbody>
            {data.merchants.map((m) => (
              <tr key={m.canonical}>
                <td>
                  <b>{m.service}</b>
                  <div className="sp-small sp-muted">{m.category_label}</div>
                </td>
                <td>
                  <span className={`sp-tag ${SOURCE_CLASS[m.source]}`}>{m.source_label}</span>
                  {m.reason && <div className="sp-small sp-muted">{m.reason}</div>}
                </td>
                <td className="sp-small">
                  {m.aliases.map((a) => (
                    <div key={a}>{a}</div>
                  ))}
                </td>
                <td className="sp-small sp-nowrap">
                  {m.personas.map((p) => (
                    <div key={p}>{p}</div>
                  ))}
                </td>
                <td className="sp-small sp-tabnum sp-nowrap" title="맞아요 / 구독 아님 제보 수">
                  ✓ {m.reports.confirm} · ✕ {m.reports.reject}
                  {m.needs_review && <div className="sp-tag sig-price_increase">검수 대기</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sp-small sp-muted">반복 결제가 아닌 일반 소비 가맹점 {st.general_merchants}곳(편의점·카페·마트 등)은 사전에 넣지 않습니다.</p>
    </>
  );
}
