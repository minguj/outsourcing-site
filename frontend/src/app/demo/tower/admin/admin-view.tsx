"use client";

import { useMemo, useState } from "react";
import { INDUSTRIES, MEMBER_BASE, STORES, WEEKLY, type Company, type CompanyStatus } from "../_tower/data";
import { nowMinutes, canCancel, utilization } from "../_tower/rooms";
import { ROOMS } from "../_tower/data";
import { fmtTime, matches, useTower } from "../_tower/store";
import { RoomsAdmin } from "./rooms-admin";

type Menu = "dashboard" | "companies" | "coupons" | "rooms";
const STATUS_LABEL: Record<CompanyStatus, string> = { pending: "승인 대기", approved: "승인", rejected: "반려" };
const storeName = (id: string) => STORES.find(s => s.id === id)?.name ?? "";

export default function AdminView() {
  const { state, actions } = useTower();
  const [menu, setMenu] = useState<Menu>("dashboard");
  const pending = state.companies.filter(c => c.status === "pending").length;
  // 오늘 날짜는 브라우저에서 채운 roomsSeededOn을 쓴다. 서버 렌더링(프리렌더) 중에는 빈 값이라 new Date()를 부르지 않는다.
  const today = state.roomsSeededOn;
  const roomPending = today ? state.bookings.filter(b => b.status === "pending" && canCancel(b, today, nowMinutes())).length : 0;

  return <div className="tw-admin">
    <aside className="tw-side">
      <div className="tw-side-brand">스마트타워 <span>관리자</span></div>
      <nav aria-label="관리 메뉴">
        {([["dashboard", "대시보드"], ["companies", "입주기업"], ["coupons", "상가 쿠폰"], ["rooms", "회의실"]] as [Menu, string][]).map(([id, label]) =>
          <button key={id} className={menu === id ? "on" : ""} onClick={() => setMenu(id)} aria-current={menu === id ? "page" : undefined}>
            {label}{id === "companies" && pending > 0 && <span className="tw-badge">{pending}</span>}{id === "rooms" && roomPending > 0 && <span className="tw-badge">{roomPending}</span>}</button>)}
      </nav>
      <div className="tw-side-foot">
        <a href="/demo/tower/app" target="_blank" rel="noreferrer">앱 화면 새 탭으로 열기 ↗</a>
        <button onClick={() => { if (window.confirm("샘플 데이터를 처음 상태로 되돌릴까요?")) actions.reset(); }}>샘플 데이터 초기화</button>
      </div>
    </aside>
    <main className="tw-main">
      <div className="tw-sample-note">샘플 화면입니다. 가상 데이터이며, 이 브라우저 안에서만 저장됩니다.</div>
      {menu === "dashboard" && <Dashboard goCompanies={() => setMenu("companies")} goRooms={() => setMenu("rooms")} />}
      {menu === "companies" && <Companies />}
      {menu === "coupons" && <Coupons />}
      {menu === "rooms" && <RoomsAdmin />}
    </main>
  </div>;
}

/* ---------- 대시보드 ---------- */
function Dashboard({ goCompanies, goRooms }: { goCompanies: () => void; goRooms: () => void }) {
  const { state } = useTower();
  const approved = state.companies.filter(c => c.status === "approved").length;
  const pending = state.companies.filter(c => c.status === "pending").length;
  const issued = state.coupons.reduce((a, k) => a + k.issued, 0);
  const used = state.coupons.reduce((a, k) => a + k.used, 0);
  const byStore = STORES.map(s => ({ label: s.name, value: state.coupons.filter(k => k.storeId === s.id).reduce((a, k) => a + k.used, 0) })).sort((a, b) => b.value - a.value);
  // 샘플 예약과 오늘 날짜(roomsSeededOn)는 브라우저에서 채워진다. 서버 렌더링 때는 0건으로 보였다가 바로 바뀐다.
  const today = state.roomsSeededOn;
  const todayRooms = state.bookings.filter(b => b.date === today && (b.status === "confirmed" || b.status === "pending")).length;
  const roomWaiting = today ? state.bookings.filter(b => b.status === "pending" && canCancel(b, today, nowMinutes())).length : 0;
  const byIndustry = INDUSTRIES.map(i => ({ label: i, value: state.companies.filter(c => c.status === "approved" && c.industry === i).length }));

  return <>
    <h1 className="tw-h1">대시보드</h1>
    <div className="tw-kpis">
      <Kpi label="전체 회원" value={(MEMBER_BASE + state.mine.length).toLocaleString()} sub={`이번 주 신규 ${WEEKLY.signups.at(-1)}명`} />
      <Kpi label="주간 활성 사용자" value={WEEKLY.active.at(-1)!.toLocaleString()} sub={`지난주보다 +${WEEKLY.active.at(-1)! - WEEKLY.active.at(-2)!}`} />
      <Kpi label="입주기업 (승인)" value={`${approved}곳`} sub={`업종 ${INDUSTRIES.length}개`} />
      <Kpi label="승인 대기" value={`${pending}건`} sub="처리하러 가기 →" onClick={goCompanies} warn={pending > 0} />
      <Kpi label="오늘 회의실 예약" value={`${todayRooms}건`} sub={`가동률 ${today ? utilization(today, ROOMS, state.bookings) : 0}%${roomWaiting ? ` · 승인 대기 ${roomWaiting}` : ""} →`} onClick={goRooms} warn={roomWaiting > 0} />
      <Kpi label="쿠폰 사용률" value={`${Math.round((used / Math.max(issued, 1)) * 100)}%`} sub={`발급 ${issued.toLocaleString()} · 사용 ${used.toLocaleString()}`} />
    </div>
    <div className="tw-grid2">
      <section className="tw-panel"><h2>주간 신규 가입자 <small>최근 12주</small></h2><LineChart labels={WEEKLY.labels} values={WEEKLY.signups} unit="명" /></section>
      <section className="tw-panel"><h2>상가별 쿠폰 사용 <small>누적</small></h2><Bars data={byStore} unit="건" /></section>
      <section className="tw-panel"><h2>업종별 입주기업</h2><Bars data={byIndustry} unit="곳" /></section>
      <section className="tw-panel"><h2>최근 활동</h2>
        <ul className="tw-activity">{state.activity.slice(0, 7).map(a => <li key={a.id}><time>{fmtTime(a.at)}</time><span>{a.text}</span></li>)}</ul>
      </section>
    </div>
  </>;
}
function Kpi({ label, value, sub, onClick, warn }: { label: string; value: string; sub: string; onClick?: () => void; warn?: boolean }) {
  const Tag = onClick ? "button" : "div";
  return <Tag className={"tw-kpi" + (warn ? " warn" : "")} onClick={onClick}><span>{label}</span><strong>{value}</strong><small>{sub}</small></Tag>;
}
function LineChart({ labels, values, unit }: { labels: string[]; values: number[]; unit: string }) {
  const W = 520, H = 200, P = { l: 34, r: 12, t: 16, b: 26 };
  const max = Math.ceil(Math.max(...values) / 50) * 50;
  const x = (i: number) => P.l + (i * (W - P.l - P.r)) / (values.length - 1);
  const y = (v: number) => H - P.b - (v / max) * (H - P.t - P.b);
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
  return <svg viewBox={`0 0 ${W} ${H}`} className="tw-chart" role="img" aria-label={`주간 신규 가입자, 마지막 주 ${values.at(-1)}${unit}`}>
    {[0, 0.5, 1].map(f => <g key={f}><line x1={P.l} x2={W - P.r} y1={y(max * f)} y2={y(max * f)} className="grid" /><text x={P.l - 6} y={y(max * f) + 4} textAnchor="end">{max * f}</text></g>)}
    <path d={`${path} L${x(values.length - 1)},${H - P.b} L${x(0)},${H - P.b} Z`} className="area" />
    <path d={path} className="line" />
    {values.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={i === values.length - 1 ? 4 : 2.5} className="dot"><title>{`${labels[i]} 주: ${v}${unit}`}</title></circle>)}
    <text x={x(values.length - 1)} y={y(values.at(-1)!) - 9} textAnchor="end" className="val">{values.at(-1)}{unit}</text>
    {labels.map((l, i) => i % 2 === 1 && <text key={l} x={x(i)} y={H - 8} textAnchor="middle">{l}</text>)}
  </svg>;
}
function Bars({ data, unit }: { data: { label: string; value: number }[]; unit: string }) {
  const max = Math.max(...data.map(d => d.value), 1);
  return <ul className="tw-bars">{data.map(d => <li key={d.label}><span>{d.label}</span><div><i style={{ width: `${(d.value / max) * 100}%` }} /></div><b>{d.value}{unit}</b></li>)}</ul>;
}

/* ---------- 입주기업 ---------- */
function Companies() {
  const { state, actions, newId } = useTower();
  const [filter, setFilter] = useState<CompanyStatus | "all">("pending");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Company | null>(null);
  const counts = { all: state.companies.length, pending: 0, approved: 0, rejected: 0 } as Record<string, number>;
  state.companies.forEach(c => counts[c.status]++);
  const rows = useMemo(() => state.companies.filter(c => (filter === "all" || c.status === filter) && matches(c, q))
    .sort((a, b) => b.appliedAt.localeCompare(a.appliedAt)), [state.companies, filter, q]);
  const open = state.companies.find(c => c.id === openId);

  const blank = (): Company => ({ id: newId(), name: "", industry: INDUSTRIES[0], room: "", ceo: "", bizNo: "", intro: "", techs: [], services: [], portfolio: [],
    phone: "", email: "", site: "", color: "#3b5bdb", status: "approved", visible: true, appliedAt: new Date().toISOString().slice(0, 10) });

  return <>
    <div className="tw-h1-row"><h1 className="tw-h1">입주기업</h1>
      <button className="tw-btn" onClick={() => setEditing(blank())}>+ 기업 직접 등록</button></div>
    <div className="tw-toolbar">
      <div className="tw-seg" role="tablist">{(["pending", "approved", "rejected", "all"] as const).map(f =>
        <button key={f} role="tab" aria-selected={filter === f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>{f === "all" ? "전체" : STATUS_LABEL[f]} <b>{counts[f]}</b></button>)}</div>
      <input className="tw-input" value={q} onChange={e => setQ(e.target.value)} placeholder="기업명·업종·기술 검색" aria-label="입주기업 검색" />
    </div>
    <div className="tw-table-wrap"><table className="tw-table">
      <thead><tr><th>기업명</th><th>업종</th><th>호실</th><th>사업자번호</th><th>국세청 조회</th><th>신청일</th><th>상태</th><th>앱 노출</th></tr></thead>
      <tbody>{rows.map(c => <tr key={c.id} onClick={() => setOpenId(c.id)} className={openId === c.id ? "sel" : ""}>
        <td><strong>{c.name}</strong></td><td>{c.industry}</td><td>{c.room}</td><td className="mono">{c.bizNo}</td>
        <td><NtsBadge bizNo={c.bizNo} /></td><td>{c.appliedAt.slice(5).replace("-", "/")}</td>
        <td><span className={"tw-status " + c.status}>{STATUS_LABEL[c.status]}</span></td>
        <td onClick={e => e.stopPropagation()}>{c.status === "approved"
          ? <label className="tw-switch"><input type="checkbox" checked={c.visible} onChange={e => actions.setVisible(c.id, e.target.checked)} aria-label={`${c.name} 앱 노출`} /><span /></label> : "—"}</td>
      </tr>)}
      {rows.length === 0 && <tr><td colSpan={8} className="tw-empty">해당하는 기업이 없습니다.</td></tr>}</tbody>
    </table></div>

    {open && <Drawer co={open} onClose={() => setOpenId(null)} onEdit={() => setEditing(open)} />}
    {editing && <EditCompany initial={editing} onClose={() => setEditing(null)} onSave={co => { actions.saveCompany(co); setEditing(null); setOpenId(co.id); }} />}
  </>;
}
/** 국세청 사업자 상태조회 결과(샘플): 실제 연동 시 공공데이터포털 API로 바뀐다. */
function NtsBadge({ bizNo }: { bizNo: string }) {
  const closed = bizNo === "123-45-67890";
  return <span className={"tw-nts " + (closed ? "bad" : "ok")}>{closed ? "휴업·폐업" : "계속사업자"}</span>;
}
function Drawer({ co, onClose, onEdit }: { co: Company; onClose: () => void; onEdit: () => void }) {
  const { actions } = useTower();
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  return <div className="tw-drawer-bg" onClick={onClose}>
    <aside className="tw-drawer" role="dialog" aria-modal="true" aria-label={`${co.name} 상세`} onClick={e => e.stopPropagation()}>
      <div className="tw-drawer-head"><div><h2>{co.name}</h2><span className={"tw-status " + co.status}>{STATUS_LABEL[co.status]}</span></div><button onClick={onClose} aria-label="닫기">✕</button></div>
      <h3>입주 인증 서류</h3>
      <BizDoc co={co} />
      <dl className="tw-dl"><dt>사업자번호</dt><dd className="mono">{co.bizNo} <NtsBadge bizNo={co.bizNo} /></dd><dt>대표자</dt><dd>{co.ceo}</dd><dt>호실</dt><dd>{co.room}</dd><dt>신청일</dt><dd>{co.appliedAt}</dd>
        {co.reason && <><dt>반려 사유</dt><dd>{co.reason}</dd></>}</dl>
      {co.bizNo === "123-45-67890" && co.status === "pending" && <p className="tw-warnline">국세청 조회 결과 휴업·폐업 상태입니다. 서류를 다시 확인하고 반려를 검토하세요.</p>}
      {co.status === "pending" && !rejecting && <div className="tw-drawer-actions">
        <button className="tw-btn" onClick={() => actions.approve(co.id)}>승인</button>
        <button className="tw-btn ghost danger" onClick={() => setRejecting(true)}>반려</button></div>}
      {rejecting && <div className="tw-reject">
        <label>반려 사유 (신청자에게 알림으로 전달)<textarea value={reason} onChange={e => setReason(e.target.value)} rows={3} placeholder="예: 사업자등록증의 주소가 입주 호실과 다릅니다." /></label>
        <div className="tw-drawer-actions"><button className="tw-btn danger" disabled={!reason.trim()} onClick={() => { actions.reject(co.id, reason.trim()); setRejecting(false); }}>반려하기</button><button className="tw-btn ghost" onClick={() => setRejecting(false)}>취소</button></div></div>}
      <h3>기업 프로필</h3>
      <dl className="tw-dl"><dt>업종</dt><dd>{co.industry}</dd><dt>소개</dt><dd>{co.intro}</dd><dt>보유 기술</dt><dd>{co.techs.join(", ")}</dd><dt>주요 서비스</dt><dd>{co.services.join(", ")}</dd><dt>연락처</dt><dd>{co.phone} · {co.email}</dd></dl>
      <button className="tw-btn ghost" onClick={onEdit}>정보 수정</button>
    </aside>
  </div>;
}
function BizDoc({ co }: { co: Company }) {
  return <div className="tw-bizdoc" aria-label="사업자등록증 샘플 이미지">
    <strong>사 업 자 등 록 증</strong><span className="tw-bizdoc-sub">(샘플 이미지)</span>
    <dl><dt>등록번호</dt><dd>{co.bizNo}</dd><dt>상호</dt><dd>{co.name}</dd><dt>대표자</dt><dd>{co.ceo}</dd><dt>사업장 소재지</dt><dd>경기도 ○○시 ○○로 00, {co.room}</dd><dt>업태·종목</dt><dd>{co.industry}</dd></dl>
  </div>;
}
function EditCompany({ initial, onClose, onSave }: { initial: Company; onClose: () => void; onSave: (c: Company) => void }) {
  const [f, setF] = useState({ ...initial, techsText: initial.techs.join(", "), servicesText: initial.services.join(", ") });
  const set = (k: string, v: string) => setF(p => ({ ...p, [k]: v }));
  const ok = f.name.trim() && f.room.trim();
  return <div className="tw-drawer-bg" onClick={onClose}>
    <aside className="tw-drawer" role="dialog" aria-modal="true" aria-label="기업 정보 편집" onClick={e => e.stopPropagation()}>
      <div className="tw-drawer-head"><h2>{initial.name ? "기업 정보 수정" : "기업 직접 등록"}</h2><button onClick={onClose} aria-label="닫기">✕</button></div>
      <div className="tw-form">
        <label>기업명<input value={f.name} onChange={e => set("name", e.target.value)} /></label>
        <label>업종<select value={f.industry} onChange={e => set("industry", e.target.value)}>{INDUSTRIES.map(i => <option key={i}>{i}</option>)}</select></label>
        <label>호실<input value={f.room} onChange={e => set("room", e.target.value)} placeholder="A동 1203호" /></label>
        <label>사업자번호<input value={f.bizNo} onChange={e => set("bizNo", e.target.value)} placeholder="000-00-00000" /></label>
        <label>대표자<input value={f.ceo} onChange={e => set("ceo", e.target.value)} /></label>
        <label className="wide">소개<textarea rows={2} value={f.intro} onChange={e => set("intro", e.target.value)} /></label>
        <label className="wide">보유 기술 (쉼표로 구분)<input value={f.techsText} onChange={e => set("techsText", e.target.value)} /></label>
        <label className="wide">주요 서비스 (쉼표로 구분)<input value={f.servicesText} onChange={e => set("servicesText", e.target.value)} /></label>
        <label>전화<input value={f.phone} onChange={e => set("phone", e.target.value)} /></label>
        <label>메일<input value={f.email} onChange={e => set("email", e.target.value)} /></label>
      </div>
      <div className="tw-drawer-actions">
        <button className="tw-btn" disabled={!ok} onClick={() => { const { techsText, servicesText, ...rest } = f;
          onSave({ ...rest, techs: techsText.split(",").map(s => s.trim()).filter(Boolean), services: servicesText.split(",").map(s => s.trim()).filter(Boolean) }); }}>저장</button>
        <button className="tw-btn ghost" onClick={onClose}>취소</button></div>
    </aside>
  </div>;
}

/* ---------- 상가 쿠폰 ---------- */
function Coupons() {
  const { state, actions } = useTower();
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ storeId: STORES[0].id, title: "", benefit: "", from: "2026-11-04", to: "2026-11-30", total: "100" });
  const ok = form.title.trim() && form.benefit.trim() && Number(form.total) > 0 && form.from <= form.to;
  return <>
    <div className="tw-h1-row"><h1 className="tw-h1">상가 쿠폰</h1><button className="tw-btn" onClick={() => setAdding(a => !a)}>{adding ? "닫기" : "+ 쿠폰 발행"}</button></div>
    {adding && <section className="tw-panel tw-form-inline">
      <label>상가<select value={form.storeId} onChange={e => setForm({ ...form, storeId: e.target.value })}>{STORES.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label className="wide">쿠폰명<input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="예: 아메리카노 10% 할인" /></label>
      <label>혜택 표시<input value={form.benefit} onChange={e => setForm({ ...form, benefit: e.target.value })} placeholder="10%" /></label>
      <label>시작일<input type="date" value={form.from} onChange={e => setForm({ ...form, from: e.target.value })} /></label>
      <label>종료일<input type="date" value={form.to} onChange={e => setForm({ ...form, to: e.target.value })} /></label>
      <label>수량<input type="number" min={1} value={form.total} onChange={e => setForm({ ...form, total: e.target.value })} /></label>
      <button className="tw-btn" disabled={!ok} onClick={() => { actions.addCoupon({ ...form, total: Number(form.total) }); setAdding(false); setForm({ ...form, title: "", benefit: "" }); }}>발행</button>
    </section>}
    <div className="tw-table-wrap"><table className="tw-table">
      <thead><tr><th>상가</th><th>쿠폰명</th><th>기간</th><th className="num">발급 / 수량</th><th className="num">사용</th><th>사용률</th><th>상태</th></tr></thead>
      <tbody>{state.coupons.map(k => { const rate = Math.round((k.used / Math.max(k.issued, 1)) * 100);
        return <tr key={k.id}><td>{storeName(k.storeId)}</td><td><strong>{k.title}</strong></td><td>{k.from.slice(5).replace("-", "/")} ~ {k.to.slice(5).replace("-", "/")}</td>
          <td className="num">{k.issued} / {k.total}</td><td className="num">{k.used}</td>
          <td><div className="tw-rate"><i style={{ width: `${rate}%` }} /><span>{rate}%</span></div></td>
          <td><label className="tw-switch"><input type="checkbox" checked={k.active} onChange={e => actions.setCouponActive(k.id, e.target.checked)} aria-label={`${k.title} 진행`} /><span /></label> {k.active ? "진행 중" : "종료"}</td></tr>; })}</tbody>
    </table></div>
    <section className="tw-panel"><h2>최근 사용 내역 <small>매장 PIN 확인 기준</small></h2>
      <div className="tw-table-wrap"><table className="tw-table compact"><thead><tr><th>시간</th><th>상가</th><th>쿠폰</th><th>회원</th></tr></thead>
        <tbody>{[...state.usages].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 10).map(u => <tr key={u.id} className={u.member === "샘*용" ? "fresh" : ""}><td>{fmtTime(u.at)}</td><td>{storeName(u.storeId)}</td><td>{state.coupons.find(k => k.id === u.couponId)?.title}</td><td>{u.member}</td></tr>)}</tbody></table></div>
    </section>
  </>;
}
