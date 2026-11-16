"use client";

// 3단계 탭: 민원(AI 분류), 출입 시스템 연동, 회계 마감
import { useState } from "react";
import { todayKst, won, type AccessEvent, type IntegrationView, type LedgerView, type ResidentRow, type Voc } from "./api";
import { errorText, Notice, useLoad, type TabProps } from "./tabs";

// ---------- 민원 ----------

const VOC_SAMPLES = [
  "엘리베이터가 2층과 3층 사이에서 멈춰서 어머니가 10분 넘게 갇혀 계셨어요. 지금은 나오셨는데 너무 놀라셨습니다.",
  "어제부터 방 온수가 미지근하게만 나와요. 수리 가능한 날짜 알려 주세요.",
  "이번 달 청구서에 셔틀 이용이 4회로 나왔는데 실제로는 2회만 탔어요.",
  "아버지가 저녁 약을 드셨는지 확인이 안 돼요. 담당 선생님 연락처 010-5521-8830 으로 연락 부탁드립니다.",
];

const VOC_ACTIONS: Record<string, string> = { in_progress: "처리 시작", done: "완료" };
const SOURCE_LABELS: Record<Voc["source"], string> = { ai: "AI 분류", rule: "규칙 분류", sample: "샘플" };

export function VocTab({ api, site, can }: TabProps) {
  const load = useLoad<Voc[]>(() => api.vocs(site.id));
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const move = (v: Voc, to: string) =>
    api
      .vocStatus(v.id, to)
      .then(() => load.reload())
      .catch((e) => setMsg(errorText(e)));
  return (
    <>
      <div className="pm-card-head">
        <h2>민원</h2>
        <span className="pm-muted pm-small">분류에 따라 담당 역할에 배정됩니다. 역할마다 보이는 민원이 다릅니다.</span>
      </div>
      {can("voc.write") && (
        <VocForm
          api={api}
          site={site}
          onDone={(v) => {
            setMsg(
              v.source === "ai"
                ? `AI가 '${v.category_label} · ${v.urgency_label}'(으)로 분류해 ${v.assignee_label}에게 배정했습니다.`
                : `AI를 쓸 수 없어 키워드 규칙으로 '${v.category_label} · ${v.urgency_label}' 분류했습니다.`,
            );
            setOpen(v.id);
            load.reload();
          }}
          onError={(e) => setMsg(e)}
        />
      )}
      <Notice error={load.error} />
      {msg && <p className="pm-msg">{msg}</p>}
      {load.data && load.data.length === 0 ? (
        <p className="pm-muted">이 역할에 배정된 민원이 없습니다.</p>
      ) : (
        <table className="pm-table">
          <thead>
            <tr>
              <th>긴급도</th>
              <th>분류</th>
              <th>요약</th>
              <th>호실</th>
              <th>담당</th>
              <th>상태</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(load.data ?? []).map((v) => (
              <VocRows key={v.id} v={v} open={open === v.id} toggle={() => setOpen(open === v.id ? null : v.id)} move={(to) => move(v, to)} />
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function VocRows({ v, open, toggle, move }: { v: Voc; open: boolean; toggle: () => void; move: (to: string) => void }) {
  return (
    <>
      <tr className={v.status === "done" ? "pm-dim" : ""}>
        <td>
          <span className={`pm-status u-${v.urgency}`}>{v.urgency_label}</span>
        </td>
        <td>{v.category_label}</td>
        <td>
          <button className="pm-link" onClick={toggle} aria-expanded={open}>
            {v.summary} {open ? "▴" : "▾"}
          </button>
        </td>
        <td>{v.unit_number}</td>
        <td>{v.assignee_label}</td>
        <td>
          <span className={`pm-status v-${v.status}`}>{v.status_label}</span>
        </td>
        <td>
          <div className="pm-actions">
            {v.next.map((to) => (
              <button key={to} className="pm-btn pm-btn-sm" onClick={() => move(to)}>
                {VOC_ACTIONS[to] ?? to}
              </button>
            ))}
          </div>
        </td>
      </tr>
      {open && (
        <tr className="pm-subrow">
          <td />
          <td colSpan={6}>
            <p className="pm-voc-text">“{v.text}”</p>
            <p className="pm-small pm-muted">
              {v.created_by_name} · {v.created_at.replace("T", " ").slice(0, 16)} · <span className="pm-tag">{SOURCE_LABELS[v.source]}</span>
              {v.reason && <> · 근거: {v.reason}</>}
              {v.masked && <> · 연락처 원문 권한이 없어 개인정보를 가린 문장으로 보여 줍니다</>}
            </p>
          </td>
        </tr>
      )}
    </>
  );
}

function VocForm({ api, site, onDone, onError }: { api: TabProps["api"]; site: TabProps["site"]; onDone: (v: Voc) => void; onError: (e: string) => void }) {
  const residents = useLoad<ResidentRow[]>(() => api.residents(site.id));
  const living = (residents.data ?? []).filter((r) => r.status === "resident");
  const [who, setWho] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const target = who || living[0]?.id || "";
  const submit = () => {
    if (!target || !text.trim()) return;
    setBusy(true);
    api
      .addVoc(target, text)
      .then((v) => {
        setText("");
        onDone(v);
      })
      .catch((e) => onError(errorText(e)))
      .finally(() => setBusy(false));
  };
  return (
    <div className="pm-voc-form">
      <div className="pm-toolbar-inline">
        <label className="pm-field">
          입주자
          <select value={target} onChange={(e) => setWho(e.target.value)}>
            {living.map((r) => (
              <option key={r.id} value={r.id}>
                {r.unit_number} {r.name}
              </option>
            ))}
          </select>
        </label>
        <span className="pm-small pm-muted">예시:</span>
        {VOC_SAMPLES.map((s, i) => (
          <button key={i} className="pm-btn pm-btn-ghost pm-btn-sm" onClick={() => setText(s)}>
            {i + 1}
          </button>
        ))}
      </div>
      <textarea value={text} maxLength={500} rows={3} placeholder="민원 내용을 적어 주세요 (가상 체험이니 실제 개인정보는 넣지 마세요)" onChange={(e) => setText(e.target.value)} />
      <div className="pm-toolbar-inline">
        <button className="pm-btn" onClick={submit} disabled={busy || !text.trim() || !target}>
          {busy ? "AI가 분류하는 중…" : "접수하고 AI로 분류"}
        </button>
        <span className="pm-small pm-muted">
          AI에는 이름·전화번호·이메일을 가린 문장만 보냅니다. AI를 쓸 수 없으면 키워드 규칙으로 분류합니다. ({text.length}/500)
        </span>
      </div>
    </div>
  );
}

// ---------- 출입 연동 ----------

const CARD_STATUS: Record<string, string> = { active: "사용 중", revoked: "회수됨", none: "없음" };

export function IntegrationTab({ api, site, can }: TabProps) {
  const load = useLoad<IntegrationView>(() => api.integration(site.id));
  const [asOf, setAsOf] = useState(todayKst());
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const write = can("integration.write");
  const process = () =>
    api
      .processIntegration(site.id, asOf)
      .then((r) => {
        const ok = r.sent.filter((s) => s.status === "delivered").length;
        setMsg(r.sent.length ? `이벤트 ${r.sent.length}건을 보냈습니다. 전달 ${ok}건, 실패 ${r.sent.length - ok}건.` : `${asOf}까지 보낼 이벤트가 없습니다.`);
        load.reload();
      })
      .catch((e) => setMsg(errorText(e)));
  const failNext = () =>
    api
      .failNext(1)
      .then(() => {
        setMsg("다음 전송 1건은 출입 시스템이 503으로 거절합니다. 계약 탭에서 해지하거나 아래 ‘처리’를 눌러 재시도를 확인해 보세요.");
        load.reload();
      })
      .catch((e) => setMsg(errorText(e)));
  const resend = (ev: AccessEvent) =>
    api
      .resend(ev.id)
      .then((r) => {
        setMsg(`같은 Idempotency-Key로 다시 보냈습니다 → ${r.code} ${r.message}`);
        load.reload();
      })
      .catch((e) => setMsg(errorText(e)));
  const data = load.data;
  return (
    <>
      <div className="pm-card-head">
        <h2>출입 시스템 연동</h2>
        {write && (
          <div className="pm-toolbar-inline">
            <label className="pm-field">
              기준일
              <input type="date" value={asOf} onChange={(e) => e.target.value && setAsOf(e.target.value)} />
            </label>
            <button className="pm-btn" onClick={process}>
              예약·재시도 처리
            </button>
            <button className="pm-btn pm-btn-ghost" onClick={failNext}>
              다음 전송 실패시키기{data?.fail_next ? ` (${data.fail_next})` : ""}
            </button>
          </div>
        )}
      </div>
      <p className="pm-small pm-muted">
        계약이 입주로 바뀌면 출입 권한 발급, 해지되면 퇴거일에 회수 이벤트를 보냅니다. 본문은 HMAC-SHA256으로 서명하고, 계약·종류마다 하나인 Idempotency-Key로
        중복 처리를 막습니다. 실패하면 1분·5분·30분 뒤 다시 보내고 4번째도 실패하면 수동 확인으로 넘깁니다(데모에서는 ‘처리’가 대기 시간을 건너뜁니다). 받는 쪽은
        가상 출입 시스템입니다.
      </p>
      <Notice error={load.error} />
      {msg && <p className="pm-msg">{msg}</p>}
      {data && (
        <div className="pm-grid-2">
          <div>
            <h3 className="pm-h3">출입카드</h3>
            <table className="pm-table">
              <thead>
                <tr>
                  <th>호실</th>
                  <th>입주자</th>
                  <th>카드</th>
                  <th>상태</th>
                </tr>
              </thead>
              <tbody>
                {data.credentials.map((c) => (
                  <tr key={c.resident_id}>
                    <td>{c.unit}</td>
                    <td>{c.resident_name}</td>
                    <td className="pm-small">{c.card}</td>
                    <td>
                      <span className={`pm-status k-${c.status}`}>{CARD_STATUS[c.status] ?? c.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h3 className="pm-h3">출입 시스템이 받은 요청</h3>
            {data.receiver_log.length === 0 ? (
              <p className="pm-muted pm-small">아직 이 체험에서 보낸 요청이 없습니다.</p>
            ) : (
              <table className="pm-table">
                <thead>
                  <tr>
                    <th>시각</th>
                    <th>Idempotency-Key</th>
                    <th>응답</th>
                  </tr>
                </thead>
                <tbody>
                  {data.receiver_log.map((l, i) => (
                    <tr key={i}>
                      <td className="pm-small">{l.at.slice(11, 19)}</td>
                      <td className="pm-small">{l.key}</td>
                      <td className="pm-small">
                        <b className={l.code < 300 ? "pm-ok" : "pm-bad"}>{l.code}</b> {l.message}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
      {data && (
        <>
          <h3 className="pm-h3">보낸 이벤트 (아웃박스)</h3>
          <table className="pm-table">
            <thead>
              <tr>
                <th>이벤트</th>
                <th>종류</th>
                <th>호실</th>
                <th>적용일</th>
                <th>상태</th>
                <th className="num">시도</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.events.map((ev) => (
                <EventRows key={ev.id} ev={ev} open={open === ev.id} toggle={() => setOpen(open === ev.id ? null : ev.id)} canResend={write} resend={() => resend(ev)} />
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

function EventRows({ ev, open, toggle, canResend, resend }: { ev: AccessEvent; open: boolean; toggle: () => void; canResend: boolean; resend: () => void }) {
  return (
    <>
      <tr>
        <td>
          <button className="pm-link" onClick={toggle} aria-expanded={open}>
            {ev.id} {open ? "▴" : "▾"}
          </button>
        </td>
        <td>{ev.kind_label}</td>
        <td>{ev.payload.unit}</td>
        <td>{ev.scheduled_for}</td>
        <td>
          <span className={`pm-status e-${ev.status}`}>{ev.status_label}</span>
        </td>
        <td className="num">{ev.attempts.length}</td>
        <td>
          <div className="pm-actions">
            {canResend && ev.status === "delivered" && (
              <button className="pm-btn pm-btn-ghost pm-btn-sm" onClick={resend} title="같은 키로 다시 보내 중복 무시를 확인합니다">
                다시 보내기
              </button>
            )}
          </div>
        </td>
      </tr>
      {open && (
        <tr className="pm-subrow">
          <td />
          <td colSpan={6}>
            <div className="pm-small">
              <b>Idempotency-Key</b> {ev.idempotency_key}
            </div>
            <pre className="pm-code">{JSON.stringify(ev.payload, null, 2)}</pre>
            {ev.attempts.map((a, i) => (
              <div key={i} className="pm-attempt pm-small">
                <span>
                  {i + 1}차 {a.at.replace("T", " ").slice(0, 19)}
                </span>
                <span className={a.code < 300 ? "pm-ok" : "pm-bad"}>{a.code}</span>
                <span>{a.message}</span>
              </div>
            ))}
            {ev.next_attempt_at && <div className="pm-small pm-muted">다음 재시도 예정 {ev.next_attempt_at.replace("T", " ").slice(0, 19)}</div>}
          </td>
        </tr>
      )}
    </>
  );
}

// ---------- 회계 마감 ----------

export function LedgerTab({ api, site, can, month, setMonth }: TabProps) {
  const load = useLoad<LedgerView>(() => api.ledger(site.id, month));
  const [msg, setMsg] = useState<string | null>(null);
  const data = load.data;
  const download = () =>
    api
      .ledgerCsv(site.id, month)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `분개-${site.name}-${month}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((e) => setMsg(errorText(e)));
  const close = () => {
    if (!window.confirm(`${site.name} ${month}을(를) 마감할까요? 마감한 달은 청구 실행·수납·서비스 기록을 바꿀 수 없습니다.`)) return;
    api
      .closeMonth(site.id, month)
      .then(() => {
        setMsg(`${month} 마감을 완료했습니다. 이제 이 달의 청구·수납·서비스 기록은 바뀌지 않습니다.`);
        load.reload();
      })
      .catch((e) => setMsg(errorText(e)));
  };
  return (
    <>
      <div className="pm-card-head">
        <h2>회계 마감</h2>
        <div className="pm-toolbar-inline">
          <label className="pm-field">
            월
            <input
              type="month"
              value={month}
              onChange={(e) => {
                if (!e.target.value) return;
                setMonth(e.target.value);
                setMsg(null);
                setTimeout(load.reload, 0);
              }}
            />
          </label>
          <button className="pm-btn pm-btn-ghost" onClick={download} disabled={!data?.rows.length}>
            분개 CSV 내려받기
          </button>
          {can("ledger.close") && (
            <button className="pm-btn" onClick={close} disabled={!!data?.closed || !data?.rows.length}>
              {month} 마감
            </button>
          )}
        </div>
      </div>
      <p className="pm-small pm-muted">
        청구서와 수납을 회계 프로그램에 올릴 분개로 바꿉니다. 청구는 말일자로 매출채권/이용료·서비스수익, 수납은 받은 날짜로 보통예금/매출채권입니다. 연체료는 아직
        청구하지 않았으므로 넣지 않습니다. 차변과 대변 합계가 같아야 내보내고 마감할 수 있습니다.
      </p>
      <Notice error={load.error} />
      {msg && <p className="pm-msg">{msg}</p>}
      {data?.closed && (
        <p className="pm-locked">
          🔒 {data.month} 마감 완료 · {data.closed.by} · {data.closed.at.replace("T", " ").slice(0, 16)}
        </p>
      )}
      {data && data.rows.length === 0 ? (
        <p className="pm-muted">{month} 청구·수납이 없습니다. 청구·수납 탭에서 월 청구를 먼저 실행해 보세요.</p>
      ) : (
        data && (
          <table className="pm-table">
            <thead>
              <tr>
                <th>전표일자</th>
                <th>전표번호</th>
                <th>계정과목</th>
                <th className="num">차변</th>
                <th className="num">대변</th>
                <th>적요</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i}>
                  <td className="pm-small">{r.date}</td>
                  <td className="pm-small">{r.no}</td>
                  <td>{r.account}</td>
                  <td className="num">{r.debit ? won(r.debit) : ""}</td>
                  <td className="num">{r.credit ? won(r.credit) : ""}</td>
                  <td className="pm-small">{r.memo}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}>합계 {data.totals.balanced ? "· 차대 일치" : "· 차대 불일치"}</td>
                <td className="num">{won(data.totals.debit)}</td>
                <td className="num">{won(data.totals.credit)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        )
      )}
    </>
  );
}
