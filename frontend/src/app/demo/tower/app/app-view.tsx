"use client";

import { useMemo, useState } from "react";
import { INDUSTRIES, STORES, STORE_CATEGORIES, type Company, type Store } from "../_tower/data";
import { fmtTime, matches, useTower } from "../_tower/store";

type Tab = "companies" | "stores" | "mine";
type View = { kind: "list" } | { kind: "company"; id: string } | { kind: "store"; id: string };

function Logo({ name, color, size = 44 }: { name: string; color: string; size?: number }) {
  return <span className="tw-logo" style={{ background: color, width: size, height: size, fontSize: size * 0.42 }} aria-hidden="true">{name.slice(0, 1)}</span>;
}
function Heart({ on }: { on: boolean }) {
  return <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2Z" fill={on ? "#e5484d" : "none"} stroke={on ? "#e5484d" : "#8a94a6"} strokeWidth="1.8" /></svg>;
}

export default function AppView() {
  const { state, actions } = useTower();
  const [tab, setTab] = useState<Tab>("companies");
  const [view, setView] = useState<View>({ kind: "list" });
  const [q, setQ] = useState("");
  const [industry, setIndustry] = useState("전체");
  const [onlyFav, setOnlyFav] = useState(false);
  const [category, setCategory] = useState("전체");
  const [toast, setToast] = useState("");
  const [redeeming, setRedeeming] = useState<string | null>(null);

  const say = (text: string) => { setToast(text); window.setTimeout(() => setToast(""), 2200); };
  const go = (t: Tab) => { setTab(t); setView({ kind: "list" }); };

  const companies = useMemo(() => state.companies
    .filter(c => c.status === "approved" && c.visible)
    .filter(c => industry === "전체" || c.industry === industry)
    .filter(c => !onlyFav || state.favorites.includes(c.id))
    .filter(c => matches(c, q)), [state.companies, state.favorites, industry, onlyFav, q]);

  const company = view.kind === "company" ? state.companies.find(c => c.id === view.id) : undefined;
  const store = view.kind === "store" ? STORES.find(s => s.id === view.id) : undefined;
  const title = company ? "기업 상세" : store ? store.name : tab === "companies" ? "입주기업" : tab === "stores" ? "상가 혜택" : "내 쿠폰";

  return <div className="tw-app">
    <header className="tw-bar">
      {view.kind !== "list"
        ? <button className="tw-back" onClick={() => setView({ kind: "list" })} aria-label="뒤로">‹</button>
        : <span className="tw-brand">스마트타워</span>}
      <strong>{title}</strong>
      <span className="tw-sample">샘플</span>
    </header>

    <main className="tw-body">
      {company && <CompanyDetail co={company} fav={state.favorites.includes(company.id)} onFav={() => actions.toggleFavorite(company.id)} say={say} />}
      {store && <StoreDetail store={store} say={say} />}

      {view.kind === "list" && tab === "companies" && <>
        <div className="tw-search"><input value={q} onChange={e => setQ(e.target.value)} placeholder="기업명, 업종, 기술 검색 (초성도 가능)" aria-label="입주기업 검색" /></div>
        <div className="tw-chips" role="tablist" aria-label="업종">
          {["전체", ...INDUSTRIES].map(i => <button key={i} role="tab" aria-selected={industry === i} className={industry === i ? "on" : ""} onClick={() => setIndustry(i)}>{i}</button>)}
        </div>
        <div className="tw-row-between"><span className="tw-count">입주기업 {companies.length}곳</span>
          <label className="tw-fav-toggle"><input type="checkbox" checked={onlyFav} onChange={e => setOnlyFav(e.target.checked)} /> 즐겨찾기만</label></div>
        <ul className="tw-list">
          {companies.map(c => <li key={c.id} className="tw-card" onClick={() => setView({ kind: "company", id: c.id })}>
            <Logo name={c.name} color={c.color} />
            <div className="tw-card-main">
              <strong>{c.name}</strong>
              <span className="tw-sub">{c.industry} · {c.room}</span>
              <p>{c.intro}</p>
              <div className="tw-tags">{c.techs.slice(0, 3).map(t => <span key={t}>{t}</span>)}</div>
            </div>
            <button className="tw-heart" aria-label={state.favorites.includes(c.id) ? "즐겨찾기 해제" : "즐겨찾기"} onClick={e => { e.stopPropagation(); actions.toggleFavorite(c.id); }}><Heart on={state.favorites.includes(c.id)} /></button>
          </li>)}
          {companies.length === 0 && <li className="tw-empty">검색 결과가 없습니다.</li>}
        </ul>
      </>}

      {view.kind === "list" && tab === "stores" && <>
        <div className="tw-banner"><strong>입주사 임직원 전용 혜택</strong><span>단지 안 상가 쿠폰을 받아 매장에서 바로 쓰세요.</span></div>
        <div className="tw-chips" role="tablist" aria-label="업종">
          {["전체", ...STORE_CATEGORIES].map(i => <button key={i} role="tab" aria-selected={category === i} className={category === i ? "on" : ""} onClick={() => setCategory(i)}>{i}</button>)}
        </div>
        <ul className="tw-list">
          {STORES.filter(s => category === "전체" || s.category === category).map(s => {
            const live = state.coupons.filter(k => k.storeId === s.id && k.active);
            return <li key={s.id} className="tw-card" onClick={() => setView({ kind: "store", id: s.id })}>
              <Logo name={s.name} color={s.color} />
              <div className="tw-card-main"><strong>{s.name}</strong><span className="tw-sub">{s.category} · {s.room}</span><p>{s.intro}</p>
                {live[0] && <span className="tw-coupon-pill">{live[0].title}</span>}</div>
            </li>;
          })}
        </ul>
      </>}

      {view.kind === "list" && tab === "mine" && <>
        {state.mine.length === 0 && <div className="tw-empty-box"><p>받은 쿠폰이 없습니다.</p><button className="tw-btn" onClick={() => go("stores")}>상가 혜택 보러 가기</button></div>}
        <ul className="tw-list">
          {state.mine.map(m => {
            const k = state.coupons.find(x => x.id === m.couponId)!; const s = STORES.find(x => x.id === k.storeId)!;
            return <li key={m.id} className={"tw-ticket" + (m.status === "used" ? " used" : "")}>
              <div className="tw-ticket-left" style={{ background: s.color }}><span>{k.benefit}</span></div>
              <div className="tw-ticket-main"><span className="tw-sub">{s.name}</span><strong>{k.title}</strong><span className="tw-sub">~ {k.to.slice(5).replace("-", "/")}까지</span>
                {m.status === "used"
                  ? <span className="tw-used">사용 완료 · {fmtTime(m.usedAt!)}</span>
                  : <button className="tw-btn small" onClick={() => setRedeeming(m.id)}>사용하기</button>}
              </div>
            </li>;
          })}
        </ul>
      </>}
    </main>

    <nav className="tw-tabs" aria-label="메뉴">
      {([["companies", "입주기업", "M4 20V6l8-3 8 3v14M9 20v-4h6v4M8 9h.01M12 9h.01M16 9h.01M8 13h.01M12 13h.01M16 13h.01"], ["stores", "상가 혜택", "M4 9l1-4h14l1 4M4 9v11h16V9M4 9h16M9 20v-6h6v6"], ["mine", "내 쿠폰", "M3 8h18v3a2 2 0 0 0 0 4v3H3v-3a2 2 0 0 0 0-4V8Zm6 0v10"]] as [Tab, string, string][]).map(([id, label, d]) =>
        <button key={id} className={tab === id ? "on" : ""} onClick={() => go(id)} aria-current={tab === id ? "page" : undefined}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
          {label}{id === "mine" && state.mine.some(m => m.status === "issued") && <i className="tw-dot" />}
        </button>)}
    </nav>

    {redeeming && <RedeemSheet myId={redeeming} onClose={() => setRedeeming(null)} say={say} />}
    {toast && <div className="tw-toast" role="status">{toast}</div>}
  </div>;
}

function CompanyDetail({ co, fav, onFav, say }: { co: Company; fav: boolean; onFav: () => void; say: (t: string) => void }) {
  return <article className="tw-detail">
    <div className="tw-detail-head" style={{ background: `linear-gradient(135deg, ${co.color}, ${co.color}cc)` }}>
      <Logo name={co.name} color="rgba(255,255,255,.18)" size={56} />
      <h1>{co.name}</h1><span>{co.industry} · {co.room}</span>
    </div>
    <div className="tw-actions">
      <button className="tw-btn" onClick={() => say("샘플에서는 전화·메일로 연결되지 않습니다.")}>문의하기</button>
      <button className={"tw-btn ghost" + (fav ? " fav" : "")} onClick={onFav}><Heart on={fav} /> {fav ? "즐겨찾기됨" : "즐겨찾기"}</button>
    </div>
    <section><h2>기업 소개</h2><p>{co.intro}</p></section>
    <section><h2>보유 기술</h2><div className="tw-tags big">{co.techs.map(t => <span key={t}>{t}</span>)}</div></section>
    <section><h2>주요 서비스</h2><ul className="tw-bullets">{co.services.map(s => <li key={s}>{s}</li>)}</ul></section>
    {co.portfolio.length > 0 && <section><h2>포트폴리오</h2>{co.portfolio.map(p => <div key={p.title} className="tw-pf"><strong>{p.title}</strong><span>{p.desc}</span></div>)}</section>}
    <section><h2>연락처</h2><dl className="tw-dl"><dt>대표</dt><dd>{co.ceo}</dd><dt>전화</dt><dd>{co.phone}</dd><dt>메일</dt><dd>{co.email}</dd><dt>홈페이지</dt><dd>{co.site}</dd></dl></section>
  </article>;
}

function StoreDetail({ store, say }: { store: Store; say: (t: string) => void }) {
  const { state, actions } = useTower();
  const list = state.coupons.filter(k => k.storeId === store.id);
  return <article className="tw-detail">
    <div className="tw-detail-head" style={{ background: `linear-gradient(135deg, ${store.color}, ${store.color}cc)` }}>
      <Logo name={store.name} color="rgba(255,255,255,.18)" size={56} />
      <h1>{store.name}</h1><span>{store.category} · {store.room}</span>
    </div>
    <section><h2>쿠폰</h2>
      {list.map(k => {
        const got = state.mine.some(m => m.couponId === k.id); const left = k.total - k.issued;
        return <div key={k.id} className={"tw-coupon" + (!k.active ? " off" : "")}>
          <div><strong>{k.title}</strong><span className="tw-sub">{k.from.slice(5).replace("-", "/")} ~ {k.to.slice(5).replace("-", "/")} · 남은 수량 {Math.max(left, 0)}장</span></div>
          <button className="tw-btn small" disabled={!k.active || got || left <= 0}
            onClick={() => { const err = actions.claim(k.id); say(err ?? "쿠폰을 받았습니다. '내 쿠폰'에서 확인하세요."); }}>
            {!k.active ? "종료" : got ? "받음" : left <= 0 ? "소진" : "받기"}</button>
        </div>;
      })}
    </section>
    <section><h2>매장 소개</h2><p>{store.intro}</p></section>
    <section><h2>메뉴·가격</h2><ul className="tw-bullets">{store.menu.map(m => <li key={m}>{m}</li>)}</ul></section>
    <section><h2>운영 시간</h2><p>{store.hours}</p></section>
  </article>;
}

function RedeemSheet({ myId, onClose, say }: { myId: string; onClose: () => void; say: (t: string) => void }) {
  const { state, actions } = useTower();
  const [pin, setPin] = useState(""); const [err, setErr] = useState("");
  const m = state.mine.find(x => x.id === myId)!; const k = state.coupons.find(x => x.id === m.couponId)!; const s = STORES.find(x => x.id === k.storeId)!;
  const submit = () => { const e = actions.redeem(myId, pin, s.pin, s.name); if (e) { setErr(e); setPin(""); } else { onClose(); say("사용 완료되었습니다."); } };
  return <div className="tw-sheet-bg" onClick={onClose}>
    <div className="tw-sheet" role="dialog" aria-modal="true" aria-label="쿠폰 사용" onClick={e => e.stopPropagation()}>
      <span className="tw-sub">{s.name}</span><h2>{k.title}</h2>
      <p className="tw-sheet-note">매장 직원에게 이 화면을 보여 주세요.<br />직원이 매장 PIN 4자리를 입력하면 사용 완료됩니다.</p>
      <div className="tw-pin" aria-label="입력한 PIN">{[0, 1, 2, 3].map(i => <span key={i} className={pin.length > i ? "on" : ""} />)}</div>
      {err && <p className="tw-err" role="alert">{err}</p>}
      <div className="tw-keypad">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"].map((d, i) => d === "" ? <span key={i} /> :
          <button key={i} onClick={() => { setErr(""); setPin(p => d === "⌫" ? p.slice(0, -1) : (p + d).slice(0, 4)); }}>{d}</button>)}
      </div>
      <button className="tw-btn block" disabled={pin.length !== 4} onClick={submit}>사용 완료 처리</button>
      <p className="tw-hint">샘플 매장 PIN: 1234</p>
    </div>
  </div>;
}
