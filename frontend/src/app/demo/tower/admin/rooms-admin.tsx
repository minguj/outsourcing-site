"use client";

import { useState } from "react";
import { ROOMS } from "../_tower/data";
import {
  CLOSE, OPEN, addDays, canCancel, fmtDay, fmtDuration, fmtMin, localDate, nowMinutes, slotStarts, utilization, type Block, type Booking,
} from "../_tower/rooms";
import { fmtTime, useTower } from "../_tower/store";

type Seg = "timeline" | "pending" | "blocks";
const STATUS_LABEL: Record<Booking["status"], string> = { confirmed: "확정", pending: "승인 대기", rejected: "반려", cancelled: "취소" };
const STATUS_TONE: Record<Booking["status"], string> = { confirmed: "approved", pending: "pending", rejected: "rejected", cancelled: "rejected" };
const hours = (m: number) => fmtDuration(m).trim() || "0시간";
const pct = (m: number) => `${((m - OPEN) / (CLOSE - OPEN)) * 100}%`;
const HOUR_MARKS = Array.from({ length: (CLOSE - OPEN) / 60 + 1 }, (_, i) => OPEN + i * 60);

export function RoomsAdmin() {
  const { state } = useTower();
  const today = localDate();
  const [date, setDate] = useState(today);
  const [seg, setSeg] = useState<Seg>("timeline");
  const [openId, setOpenId] = useState<string | null>(null);
  const [blockId, setBlockId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const companyName = (id: string) => state.companies.find(c => c.id === id)?.name ?? "";

  const dayBookings = state.bookings.filter(b => b.date === date && (b.status === "confirmed" || b.status === "pending"));
  const pending = state.bookings.filter(b => b.status === "pending" && canCancel(b, today, nowMinutes()));
  const month = date.slice(0, 7);
  const paidMonth = state.bookings.filter(b => b.date.startsWith(month) && b.status === "confirmed").reduce((a, b) => a + b.paidMinutes, 0);
  const open = state.bookings.find(b => b.id === openId);
  const block = state.blocks.find(k => k.id === blockId);

  return <>
    <div className="tw-h1-row"><h1 className="tw-h1">회의실</h1>
      <button className="tw-btn" onClick={() => setAdding(a => !a)}>{adding ? "닫기" : "+ 사용 막기"}</button></div>
    {adding && <BlockForm date={date} onDone={() => setAdding(false)} />}

    <div className="tw-kpis four">
      <div className="tw-kpi"><span>{fmtDay(date, today)} 예약</span><strong>{dayBookings.length}건</strong><small>확정 {dayBookings.filter(b => b.status === "confirmed").length} · 승인 대기 {dayBookings.filter(b => b.status === "pending").length}</small></div>
      <div className="tw-kpi"><span>{fmtDay(date, today)} 가동률</span><strong>{utilization(date, ROOMS, state.bookings)}%</strong><small>운영 09:00~21:00 · 확정 기준</small></div>
      <button className={"tw-kpi" + (pending.length ? " warn" : "")} onClick={() => setSeg("pending")}><span>승인 대기 (세미나실)</span><strong>{pending.length}건</strong><small>{pending.length ? "검토하러 가기 →" : "처리할 신청 없음"}</small></button>
      <div className="tw-kpi"><span>{Number(month.slice(5))}월 유료 이용</span><strong>{hours(paidMonth)}</strong><small>무료 시간(월 8시간) 초과분</small></div>
    </div>

    <div className="tw-toolbar">
      <div className="tw-seg" role="tablist">
        {([["timeline", "일간 타임라인"], ["pending", "승인 대기"], ["blocks", "사용 막기"]] as [Seg, string][]).map(([id, label]) =>
          <button key={id} role="tab" aria-selected={seg === id} className={seg === id ? "on" : ""} onClick={() => setSeg(id)}>{label}
            {id === "pending" && <b>{pending.length}</b>}{id === "blocks" && <b>{state.blocks.filter(k => k.date >= today).length}</b>}</button>)}
      </div>
      {seg === "timeline" && <div className="tw-datenav">
        <button className="tw-btn small ghost" onClick={() => setDate(d => addDays(d, -1))} aria-label="이전 날짜">‹</button>
        <input className="tw-input date" type="date" value={date} onChange={e => e.target.value && setDate(e.target.value)} aria-label="날짜 선택" />
        <button className="tw-btn small ghost" onClick={() => setDate(d => addDays(d, 1))} aria-label="다음 날짜">›</button>
        <button className="tw-btn small ghost" disabled={date === today} onClick={() => setDate(today)}>오늘</button>
      </div>}
    </div>

    {seg === "timeline" && <Timeline date={date} onBooking={setOpenId} onBlock={setBlockId} />}

    {seg === "pending" && <div className="tw-table-wrap"><table className="tw-table">
      <thead><tr><th>신청 시각</th><th>회의실</th><th>사용 일시</th><th>입주기업</th><th>목적</th><th className="num">인원</th><th>상태</th></tr></thead>
      <tbody>{pending.sort((a, b) => a.date.localeCompare(b.date) || a.start - b.start).map(b => <tr key={b.id} onClick={() => setOpenId(b.id)} className={openId === b.id ? "sel" : ""}>
        <td>{b.seed ? "—" : fmtTime(b.createdAt)}</td><td><strong>{ROOMS.find(r => r.id === b.roomId)?.name}</strong></td>
        <td>{fmtDay(b.date, today)} {fmtMin(b.start)}~{fmtMin(b.end)}</td><td>{companyName(b.companyId)}</td><td>{b.title}</td><td className="num">{b.attendees}명</td>
        <td><span className="tw-status pending">승인 대기</span></td></tr>)}
        {pending.length === 0 && <tr><td colSpan={7} className="tw-empty">승인을 기다리는 신청이 없습니다.</td></tr>}</tbody>
    </table></div>}

    {seg === "blocks" && <div className="tw-table-wrap"><table className="tw-table">
      <thead><tr><th>회의실</th><th>날짜</th><th>시간</th><th>사유</th><th /></tr></thead>
      <tbody>{[...state.blocks].filter(k => k.date >= today).sort((a, b) => a.date.localeCompare(b.date) || a.start - b.start).map(k => <tr key={k.id} onClick={() => setBlockId(k.id)}>
        <td><strong>{ROOMS.find(r => r.id === k.roomId)?.name}</strong></td><td>{fmtDay(k.date, today)}</td><td>{fmtMin(k.start)}~{fmtMin(k.end)}</td><td>{k.reason}</td><td className="num">해제 ›</td></tr>)}
        {state.blocks.filter(k => k.date >= today).length === 0 && <tr><td colSpan={5} className="tw-empty">막아 둔 시간이 없습니다.</td></tr>}</tbody>
    </table></div>}

    {open && <BookingDrawer b={open} companyName={companyName(open.companyId)} onClose={() => setOpenId(null)} />}
    {block && <BlockDrawer k={block} onClose={() => setBlockId(null)} />}
  </>;
}

/** 회의실 × 시간 표. 예약은 칸 위에 시간 비율로 올린다. */
function Timeline({ date, onBooking, onBlock }: { date: string; onBooking: (id: string) => void; onBlock: (id: string) => void }) {
  const { state } = useTower();
  const today = localDate(); const now = nowMinutes();
  const companyName = (id: string) => state.companies.find(c => c.id === id)?.name ?? "";
  const showNow = date === today && now >= OPEN && now <= CLOSE;
  return <div className="tw-panel tw-timeline-wrap">
    <div className="tw-timeline">
      <div className="tw-tl-row head"><div className="tw-tl-room" />
        <div className="tw-tl-track">{HOUR_MARKS.map(m => <span key={m} className="tw-tl-hour" style={{ left: pct(m) }}>{fmtMin(m).slice(0, 2)}</span>)}</div></div>
      {ROOMS.map(r => <div key={r.id} className="tw-tl-row">
        <div className="tw-tl-room"><i style={{ background: r.color }} /><strong>{r.name}</strong><span>{r.capacity}명{r.needsApproval ? " · 승인제" : ""}</span></div>
        <div className="tw-tl-track">
          {slotStarts().map(t => <span key={t} className={"tw-tl-cell" + (t % 60 === 0 ? " hour" : "") + (date < today || (date === today && t + 30 <= now) ? " past" : "")} />)}
          {state.blocks.filter(k => k.roomId === r.id && k.date === date).map(k =>
            <button key={k.id} className="tw-tl-item block" style={{ left: pct(k.start), width: `calc(${pct(k.end)} - ${pct(k.start)})` }} onClick={() => onBlock(k.id)} title={k.reason}>
              <b>사용 불가</b><span>{k.reason}</span></button>)}
          {state.bookings.filter(b => b.roomId === r.id && b.date === date && (b.status === "confirmed" || b.status === "pending")).map(b =>
            <button key={b.id} className={"tw-tl-item " + b.status + (b.seed ? "" : " fresh")} style={{ left: pct(b.start), width: `calc(${pct(b.end)} - ${pct(b.start)})`, borderColor: r.color }}
              onClick={() => onBooking(b.id)} title={`${fmtMin(b.start)}~${fmtMin(b.end)} ${companyName(b.companyId)} · ${b.title}`}>
              <b>{companyName(b.companyId)}</b><span>{fmtMin(b.start)}~{fmtMin(b.end)} · {b.title}</span></button>)}
          {showNow && <i className="tw-tl-now" style={{ left: pct(now) }} />}
        </div>
      </div>)}
    </div>
    <div className="tw-tl-legend"><span><i className="confirmed" />확정</span><span><i className="pending" />승인 대기</span><span><i className="block" />사용 불가</span><span><i className="fresh" />앱에서 새로 들어온 예약</span></div>
  </div>;
}

function BookingDrawer({ b, companyName, onClose }: { b: Booking; companyName: string; onClose: () => void }) {
  const { actions } = useTower();
  const [mode, setMode] = useState<"" | "reject" | "cancel">("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const room = ROOMS.find(r => r.id === b.roomId)!;
  const active = canCancel(b, localDate(), nowMinutes());
  const done = (e: string | null) => { if (e) setErr(e); else { setMode(""); setReason(""); setErr(""); } };
  return <div className="tw-drawer-bg" onClick={onClose}>
    <aside className="tw-drawer" role="dialog" aria-modal="true" aria-label="예약 상세" onClick={e => e.stopPropagation()}>
      <div className="tw-drawer-head"><div><h2>{room.name} 예약</h2><span className={"tw-status " + STATUS_TONE[b.status]}>{STATUS_LABEL[b.status]}</span></div><button onClick={onClose} aria-label="닫기">✕</button></div>
      <dl className="tw-dl">
        <dt>일시</dt><dd>{fmtDay(b.date, localDate())} {fmtMin(b.start)}~{fmtMin(b.end)} ({hours(b.end - b.start)})</dd>
        <dt>입주기업</dt><dd>{companyName}</dd><dt>목적</dt><dd>{b.title}</dd><dt>인원</dt><dd>{b.attendees}명 / 최대 {room.capacity}명</dd>
        <dt>요금</dt><dd>{b.paidMinutes ? `유료 ${hours(b.paidMinutes)} · ${(room.pricePerHour * b.paidMinutes / 60).toLocaleString()}원 (관리비 합산)` : "무료 시간 안"}</dd>
        <dt>신청</dt><dd>{b.seed ? "샘플 예약" : `${fmtTime(b.createdAt)} · 앱에서 신청`}</dd>
        {b.reason && <><dt>사유</dt><dd>{b.reason}</dd></>}
      </dl>
      {err && <p className="tw-warnline">{err}</p>}
      {active && b.status === "pending" && !mode && <div className="tw-drawer-actions">
        <button className="tw-btn" onClick={() => done(actions.approveBooking(b.id))}>승인</button>
        <button className="tw-btn ghost danger" onClick={() => setMode("reject")}>반려</button></div>}
      {active && b.status === "confirmed" && !mode && <div className="tw-drawer-actions">
        <button className="tw-btn ghost danger" onClick={() => setMode("cancel")}>예약 취소</button></div>}
      {!active && (b.status === "pending" || b.status === "confirmed") && <p className="tw-sub">시작 시간이 지난 예약은 바꿀 수 없습니다.</p>}
      {mode && <div className="tw-reject">
        <label>{mode === "reject" ? "반려 사유" : "취소 사유"} (입주기업에 알림으로 전달)
          <textarea rows={3} value={reason} onChange={e => setReason(e.target.value)} placeholder={mode === "reject" ? "예: 같은 날 단지 행사로 세미나실을 사용할 수 없습니다." : "예: 설비 고장으로 사용할 수 없습니다."} /></label>
        <div className="tw-drawer-actions">
          <button className="tw-btn danger" disabled={!reason.trim()} onClick={() => {
            if (mode === "reject") { actions.rejectBooking(b.id, reason.trim()); done(null); } else done(actions.cancelBooking(b.id, reason.trim()));
          }}>{mode === "reject" ? "반려하기" : "취소하기"}</button>
          <button className="tw-btn ghost" onClick={() => { setMode(""); setReason(""); }}>닫기</button></div>
      </div>}
    </aside>
  </div>;
}

function BlockDrawer({ k, onClose }: { k: Block; onClose: () => void }) {
  const { actions } = useTower();
  const room = ROOMS.find(r => r.id === k.roomId)!;
  return <div className="tw-drawer-bg" onClick={onClose}>
    <aside className="tw-drawer" role="dialog" aria-modal="true" aria-label="사용 막기 상세" onClick={e => e.stopPropagation()}>
      <div className="tw-drawer-head"><div><h2>{room.name} 사용 불가</h2></div><button onClick={onClose} aria-label="닫기">✕</button></div>
      <dl className="tw-dl"><dt>일시</dt><dd>{fmtDay(k.date, localDate())} {fmtMin(k.start)}~{fmtMin(k.end)}</dd><dt>사유</dt><dd>{k.reason}</dd></dl>
      <div className="tw-drawer-actions"><button className="tw-btn ghost" onClick={() => { actions.removeBlock(k.id); onClose(); }}>막기 해제</button></div>
    </aside>
  </div>;
}

function BlockForm({ date, onDone }: { date: string; onDone: () => void }) {
  const { actions } = useTower();
  const times = [...slotStarts(), CLOSE];
  const [f, setF] = useState({ roomId: ROOMS[0].id, date, start: 13 * 60, end: 15 * 60, reason: "" });
  const [err, setErr] = useState("");
  return <section className="tw-panel tw-form-inline">
    <label>회의실<select value={f.roomId} onChange={e => setF({ ...f, roomId: e.target.value })}>{ROOMS.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
    <label>날짜<input type="date" value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></label>
    <label>시작<select value={f.start} onChange={e => setF({ ...f, start: Number(e.target.value) })}>{times.slice(0, -1).map(t => <option key={t} value={t}>{fmtMin(t)}</option>)}</select></label>
    <label>종료<select value={f.end} onChange={e => setF({ ...f, end: Number(e.target.value) })}>{times.slice(1).map(t => <option key={t} value={t}>{fmtMin(t)}</option>)}</select></label>
    <label className="wide">사유<input value={f.reason} onChange={e => setF({ ...f, reason: e.target.value })} placeholder="예: 빔프로젝터 점검" /></label>
    <button className="tw-btn" onClick={() => { const e = actions.addBlock(f); if (e) setErr(e); else { setErr(""); onDone(); } }}>막기</button>
    {err && <p className="tw-warnline wide-line">{err}</p>}
  </section>;
}
