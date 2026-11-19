"use client";

import { useState } from "react";
import { MY_COMPANY_ID, ROOMS, type Room } from "../_tower/data";
import {
  FREE_MINUTES, bookingDays, canCancel, durationOptions, fmtDay, fmtDuration, fmtMin, isWeekend, localDate, nowMinutes,
  slotStarts, slotState, splitFree, usedMinutes, type Booking, type SlotState,
} from "../_tower/rooms";
import { useTower } from "../_tower/store";

export type RoomSeg = "book" | "mine";
const STATE_LABEL: Record<SlotState, string> = { free: "예약 가능", booked: "예약됨", pending: "승인 대기", blocked: "사용 불가", past: "지난 시간" };
const CAPS = [0, 4, 8, 16];
const won = (n: number) => n.toLocaleString() + "원";
const hours = (m: number) => fmtDuration(m).trim() || "0시간";

/** 회의실 아이콘: 테이블과 의자 */
function RoomIcon() {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="6" y="9" width="12" height="6" rx="1.5" /><path d="M8 5.5h2M14 5.5h2M8 18.5h2M14 18.5h2M3 12h1M20 12h1" /></svg>;
}

/** 무료 시간 안내 카드: 이번 달 회사 전체가 쓴 시간 기준 */
function Quota() {
  const { state } = useTower();
  const today = localDate();
  const used = usedMinutes(MY_COMPANY_ID, today.slice(0, 7), state.bookings);
  const left = Math.max(FREE_MINUTES - used, 0);
  const name = state.companies.find(c => c.id === MY_COMPANY_ID)?.name;
  return <div className="tw-quota">
    <div><span className="tw-sub">{name} · {Number(today.slice(5, 7))}월 무료 이용</span>
      <strong>{hours(left)} 남음 <small>/ {hours(FREE_MINUTES)}</small></strong></div>
    <div className="tw-quota-bar" aria-hidden="true"><i style={{ width: `${Math.min(used / FREE_MINUTES, 1) * 100}%` }} /></div>
    <span className="tw-sub">무료 시간을 넘기면 회의실별 시간당 요금으로 관리비에 함께 청구됩니다.</span>
  </div>;
}

function DayChips({ date, setDate }: { date: string; setDate: (d: string) => void }) {
  const today = localDate();
  return <div className="tw-chips tw-days" role="tablist" aria-label="날짜">
    {bookingDays(today).map(d => <button key={d} role="tab" aria-selected={date === d} className={(date === d ? "on tone-rooms" : "") + (isWeekend(d) ? " weekend" : "")} onClick={() => setDate(d)}>{fmtDay(d, today)}</button>)}
  </div>;
}

/** 회의실 탭 목록 화면: 예약하기(날짜·인원으로 회의실 고르기) / 내 예약 */
export function RoomsTab({ seg, setSeg, date, setDate, onOpen, say }: {
  seg: RoomSeg; setSeg: (s: RoomSeg) => void; date: string; setDate: (d: string) => void; onOpen: (id: string) => void; say: (t: string) => void;
}) {
  const { state } = useTower();
  const [cap, setCap] = useState(0);
  const today = localDate(); const now = nowMinutes();
  const mine = state.bookings.filter(b => b.companyId === MY_COMPANY_ID);
  const upcoming = mine.filter(b => canCancel(b, today, now)).length;

  return <>
    <Quota />
    <div className="tw-seg-app" role="tablist">
      <button role="tab" aria-selected={seg === "book"} className={seg === "book" ? "on" : ""} onClick={() => setSeg("book")}>예약하기</button>
      <button role="tab" aria-selected={seg === "mine"} className={seg === "mine" ? "on" : ""} onClick={() => setSeg("mine")}>내 예약{upcoming > 0 && <b>{upcoming}</b>}</button>
    </div>

    {seg === "book" && <>
      <DayChips date={date} setDate={setDate} />
      <div className="tw-chips" role="tablist" aria-label="인원">
        {CAPS.map(c => <button key={c} role="tab" aria-selected={cap === c} className={cap === c ? "on tone-rooms" : ""} onClick={() => setCap(c)}>{c ? `${c}명 이상` : "전체 인원"}</button>)}
      </div>
      <ul className="tw-list">
        {ROOMS.filter(r => r.capacity >= cap).map(r => {
          const states = slotStarts().map(t => slotState(r.id, date, t, state.bookings, state.blocks, today, now));
          const free = states.filter(s => s === "free").length;
          return <li key={r.id} className="tw-room-card" onClick={() => onOpen(r.id)}>
            <div className="tw-room-head">
              <span className="tw-room-icon" style={{ background: r.color }} aria-hidden="true"><RoomIcon /></span>
              <div><strong>{r.name}</strong><span className="tw-sub">{r.floor}</span></div>
              <div className="tw-room-badges"><span className="tw-cap">최대 {r.capacity}명</span>{r.needsApproval && <span className="tw-approval">승인 필요</span>}</div>
            </div>
            <div className="tw-tags">{r.equipment.map(e => <span key={e}>{e}</span>)}</div>
            <div className="tw-mini" aria-label={`${fmtDay(date, today)} 예약 가능 ${free}칸`}>{states.map((s, i) => <i key={i} className={s} />)}</div>
            <div className="tw-mini-scale" aria-hidden="true"><span>09</span><span>12</span><span>15</span><span>18</span><span>21</span></div>
            <span className="tw-sub">{free ? `예약 가능 ${hours(free * 30)}` : "예약 가능한 시간이 없습니다"}</span>
          </li>;
        })}
      </ul>
    </>}

    {seg === "mine" && <MyBookings say={say} goBook={() => setSeg("book")} />}
  </>;
}

const STATUS: Record<string, [string, string]> = {
  confirmed: ["확정", "ok"], pending: ["승인 대기", "wait"], rejected: ["반려", "bad"], cancelled: ["취소됨", "off"], done: ["이용 완료", "off"],
};
function MyBookings({ say, goBook }: { say: (t: string) => void; goBook: () => void }) {
  const { state, actions } = useTower();
  const [asking, setAsking] = useState<string | null>(null);
  const today = localDate(); const now = nowMinutes();
  const mine = state.bookings.filter(b => b.companyId === MY_COMPANY_ID);
  const active = (b: Booking) => canCancel(b, today, now);
  const asc = (a: Booking, b: Booking) => a.date.localeCompare(b.date) || a.start - b.start;
  // 다가오는 예약은 가까운 순, 지난·취소된 예약은 최근 순
  const list = [...mine.filter(active).sort(asc), ...mine.filter(b => !active(b)).sort((a, b) => asc(b, a))];
  if (!list.length) return <div className="tw-empty-box"><p>예약 내역이 없습니다.</p><button className="tw-btn" onClick={goBook}>회의실 예약하기</button></div>;
  return <ul className="tw-list">
    {list.map(b => {
      const room = ROOMS.find(r => r.id === b.roomId)!;
      const key = b.status === "confirmed" && !active(b) ? "done" : b.status;
      const [label, tone] = STATUS[key];
      return <li key={b.id} className={"tw-booking" + (tone === "off" || tone === "bad" ? " dim" : "")}>
        <span className="tw-booking-bar" style={{ background: room.color }} />
        <div className="tw-booking-main">
          <div className="tw-row-between tight"><strong>{room.name}</strong><span className={"tw-bstatus " + tone}>{label}</span></div>
          <span className="tw-booking-time">{fmtDay(b.date, today)} {fmtMin(b.start)}~{fmtMin(b.end)} <small>({hours(b.end - b.start)})</small></span>
          <span className="tw-sub">{b.title} · {b.attendees}명{b.paidMinutes > 0 && ` · 유료 ${hours(b.paidMinutes)} ${won(room.pricePerHour * b.paidMinutes / 60)}`}</span>
          {b.status === "pending" && <span className="tw-note">관리자 승인 후 확정됩니다. 승인되면 알림으로 알려 드립니다.</span>}
          {b.reason && <span className="tw-note bad">{b.status === "rejected" ? "반려 사유" : "취소 사유"}: {b.reason}</span>}
          {active(b) && (asking === b.id
            ? <div className="tw-inline-confirm"><span>이 예약을 취소할까요?</span>
                <button className="tw-btn small red" onClick={() => { const e = actions.cancelBooking(b.id); setAsking(null); say(e ?? "예약을 취소했습니다."); }}>취소하기</button>
                <button className="tw-btn small ghost" onClick={() => setAsking(null)}>아니요</button></div>
            : <button className="tw-btn small ghost" onClick={() => setAsking(b.id)}>예약 취소</button>)}
        </div>
      </li>;
    })}
  </ul>;
}

/** 회의실 상세: 날짜 → 시작 시각 → 사용 시간 → 확인 시트 */
export function RoomDetail({ room, date, setDate, say, onBooked }: { room: Room; date: string; setDate: (d: string) => void; say: (t: string) => void; onBooked: () => void }) {
  const { state } = useTower();
  const [start, setStart] = useState<number | null>(null);
  const [minutes, setMinutes] = useState(60);
  const [confirming, setConfirming] = useState(false);
  const today = localDate(); const now = nowMinutes();
  const options = start === null ? [] : durationOptions(room, date, start, state.bookings, state.blocks, today, now);
  const dur = options.includes(minutes) ? minutes : options[0] ?? 0;
  const pickDate = (d: string) => { setDate(d); setStart(null); };
  const pickStart = (t: number) => { setStart(t === start ? null : t); };

  return <article className="tw-detail">
    <div className="tw-room-hero" style={{ background: `linear-gradient(135deg, ${room.color}, ${room.color}cc 60%, #1f2937)` }}>
      <span className="tw-room-hero-cap">최대 {room.capacity}명</span>
      <h1>{room.name}</h1><span>{room.floor}</span>
    </div>
    <section>
      <div className="tw-tags big">{room.equipment.map(e => <span key={e}>{e}</span>)}</div>
      <ul className="tw-rules">
        <li>운영 09:00~21:00 · 30분 단위 · 한 번에 최대 {hours(room.maxMinutes)}</li>
        <li>무료 시간 초과 시 시간당 {won(room.pricePerHour)}</li>
        {room.needsApproval ? <li className="warn">관리자 승인 후 확정됩니다</li> : <li>예약 즉시 확정 · 시작 전까지 취소 가능</li>}
      </ul>
    </section>
    <section>
      <h2>날짜</h2>
      <DayChips date={date} setDate={pickDate} />
      <div className="tw-row-between tight"><h2>시작 시간</h2>
        <div className="tw-legend" aria-hidden="true"><span><i className="free" />가능</span><span><i className="booked" />예약됨</span><span><i className="blocked" />불가</span></div></div>
      <div className="tw-slots">
        {slotStarts().map(t => {
          const st = slotState(room.id, date, t, state.bookings, state.blocks, today, now);
          const inRange = start !== null && t >= start && t < start + dur;
          return <button key={t} disabled={st !== "free"} className={st + (inRange ? " sel" : "") + (t === start ? " start" : "")}
            onClick={() => pickStart(t)} aria-pressed={t === start} aria-label={`${fmtMin(t)} ${STATE_LABEL[st]}`}>{fmtMin(t)}</button>;
        })}
      </div>
      {start !== null && <>
        <h2>사용 시간</h2>
        <div className="tw-chips tw-durations">{options.map(m => <button key={m} className={dur === m ? "on tone-rooms" : ""} onClick={() => setMinutes(m)}>{hours(m)}</button>)}</div>
        {options.length < room.maxMinutes / 30 && <p className="tw-sub">다음 예약 또는 운영 종료 시간까지만 이어서 고를 수 있습니다.</p>}
      </>}
    </section>
    <div className="tw-book-bar">
      <div>{start === null ? <span className="tw-sub">시작 시간을 골라 주세요</span>
        : <><strong>{fmtDay(date, today)} {fmtMin(start)}~{fmtMin(start + dur)}</strong><span className="tw-sub">{hours(dur)}</span></>}</div>
      <button className="tw-btn teal" disabled={start === null || !dur} onClick={() => setConfirming(true)}>{room.needsApproval ? "예약 신청" : "예약하기"}</button>
    </div>
    {confirming && start !== null && <ConfirmSheet room={room} date={date} start={start} end={start + dur} onClose={() => setConfirming(false)}
      onDone={(msg) => { setConfirming(false); setStart(null); say(msg); onBooked(); }} onError={say} />}
  </article>;
}

function ConfirmSheet({ room, date, start, end, onClose, onDone, onError }: {
  room: Room; date: string; start: number; end: number; onClose: () => void; onDone: (msg: string) => void; onError: (msg: string) => void;
}) {
  const { state, actions } = useTower();
  const [title, setTitle] = useState("팀 회의");
  const [people, setPeople] = useState(Math.min(4, room.capacity));
  const [err, setErr] = useState("");
  const { free, paid } = splitFree(MY_COMPANY_ID, date, end - start, state.bookings);
  const submit = () => {
    const r = actions.book({ roomId: room.id, date, start, end, attendees: people, title });
    if ("error" in r) { setErr(r.error); onError(r.error); return; }
    onDone(r.booking.status === "pending" ? "예약을 신청했습니다. 관리자 승인 후 확정됩니다." : "예약이 확정되었습니다.");
  };
  return <div className="tw-sheet-bg" onClick={onClose}>
    <div className="tw-sheet left" role="dialog" aria-modal="true" aria-label="회의실 예약 확인" onClick={e => e.stopPropagation()}>
      <span className="tw-sub">{room.floor}</span><h2>{room.name}</h2>
      <p className="tw-booking-time">{fmtDay(date, localDate())} {fmtMin(start)}~{fmtMin(end)} · {hours(end - start)}</p>
      <label className="tw-field">회의 목적<input value={title} onChange={e => setTitle(e.target.value)} maxLength={30} /></label>
      <div className="tw-field">참석 인원 <span className="tw-sub">(최대 {room.capacity}명)</span>
        <div className="tw-stepper">
          <button onClick={() => setPeople(p => Math.max(1, p - 1))} aria-label="인원 줄이기">−</button>
          <b aria-live="polite">{people}명</b>
          <button onClick={() => setPeople(p => Math.min(room.capacity, p + 1))} aria-label="인원 늘리기">+</button>
        </div></div>
      <dl className="tw-cost">
        <dt>무료 시간 사용</dt><dd>{hours(free)}</dd>
        <dt>유료</dt><dd>{paid ? `${hours(paid)} · ${won(room.pricePerHour * paid / 60)}` : "없음"}</dd>
      </dl>
      {room.needsApproval && <p className="tw-note">세미나실은 관리자 승인 후 확정됩니다. 승인 전에도 이 시간은 다른 사람이 예약할 수 없습니다.</p>}
      {err && <p className="tw-err" role="alert">{err}</p>}
      <button className="tw-btn block teal" disabled={!title.trim()} onClick={submit}>{room.needsApproval ? "예약 신청하기" : "예약 확정"}</button>
      <button className="tw-btn block ghost" onClick={onClose}>닫기</button>
    </div>
  </div>;
}
