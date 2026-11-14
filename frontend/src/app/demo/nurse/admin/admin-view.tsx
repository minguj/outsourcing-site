"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Pic } from "../_nurse/art";
import { CENTER, type FaqItem, type ImageItem, type Inquiry, type Mail, type Post } from "../_nurse/data";
import { PUBLIC_ORIGIN, SITE_BASE, excerpt, fmtBytes, fmtDate, fmtTime, postJsonLd, postUrl, slugify, uid, useNurse } from "../_nurse/store";
import { Body } from "../site/site-view";

type Menu = "dashboard" | "inquiries" | "posts" | "images" | "account" | "mails";
const MENUS: [Menu, string][] = [["dashboard", "대시보드"], ["inquiries", "상담 신청"], ["posts", "블로그"], ["images", "이미지"], ["account", "계정 설정"], ["mails", "보낸 메일 (데모)"]];

export default function AdminView() {
  const { state, actions } = useNurse();
  const [menu, setMenu] = useState<Menu>("dashboard");
  const [editing, setEditing] = useState<string | null>(null);
  const fresh = state.inquiries.filter(q => q.status === "new").length;
  if (!state.loggedIn) return <AuthScreen />;

  const go = (m: Menu) => { setMenu(m); setEditing(null); };
  return <div className="nc-admin">
    <aside className="nc-side">
      <div className="nc-side-brand">{CENTER.short} <span>관리자</span></div>
      <nav aria-label="관리 메뉴">{MENUS.map(([id, label]) =>
        <button key={id} className={menu === id ? "on" : ""} aria-current={menu === id ? "page" : undefined} onClick={() => go(id)}>
          {label}{id === "inquiries" && fresh > 0 && <span className="nc-badge">{fresh}</span>}</button>)}
      </nav>
      <div className="nc-side-foot">
        <span className="nc-side-user">{state.account.email}</span>
        <a href={SITE_BASE} target="_blank" rel="noreferrer">홈페이지 새 탭으로 열기 ↗</a>
        <button onClick={actions.logout}>로그아웃</button>
        <button onClick={() => { if (window.confirm("샘플 데이터를 처음 상태로 되돌릴까요? (계정 정보도 초기화됩니다)")) actions.reset(); }}>샘플 데이터 초기화</button>
      </div>
    </aside>
    <main className="nc-main">
      <div className="nc-sample-note">샘플 화면입니다. 가상 데이터이며 이 브라우저 안에서만 저장됩니다. 메일은 실제로 보내지 않고 ‘보낸 메일’에 기록됩니다.</div>
      {menu === "dashboard" && <Dashboard go={go} edit={id => { setMenu("posts"); setEditing(id); }} />}
      {menu === "inquiries" && <Inquiries />}
      {menu === "posts" && (editing ? <Editor id={editing} close={() => setEditing(null)} /> : <Posts edit={setEditing} />)}
      {menu === "images" && <Images />}
      {menu === "account" && <Account />}
      {menu === "mails" && <Mails />}
    </main>
  </div>;
}

/* ---------- 로그인 · 비밀번호 찾기 ---------- */
function AuthScreen() {
  const { state, actions } = useNurse();
  const [mode, setMode] = useState<"login" | "reset" | "code" | "done">("login");
  const [email, setEmail] = useState(state.account.email);
  const [pw, setPw] = useState("demo1234");
  const [code, setCode] = useState("");
  const [newPw, setNewPw] = useState("");
  const [err, setErr] = useState("");
  const run = (fn: () => string | null, next?: typeof mode) => (e: FormEvent) => { e.preventDefault(); const r = fn(); setErr(r ?? ""); if (!r && next) setMode(next); };

  return <div className="nc-auth">
    <div className="nc-auth-card">
      <div className="nc-auth-brand"><span className="nc-mark" aria-hidden="true" />{CENTER.name} <small>관리자</small></div>
      {mode === "login" && <form onSubmit={run(() => actions.login(email, pw))} className="nc-form">
        <h1>로그인</h1>
        <label>이메일<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="username" /></label>
        <label>비밀번호<input type="password" value={pw} onChange={e => setPw(e.target.value)} autoComplete="current-password" /></label>
        {err && <p className="nc-err" role="alert">{err}</p>}
        <button className="nc-btn block">로그인</button>
        <button type="button" className="nc-link" onClick={() => { setErr(""); setMode("reset"); }}>비밀번호를 잊으셨나요?</button>
        <p className="nc-hint">데모 계정이 채워져 있습니다. 비밀번호를 틀리게 입력해 오류 안내도 확인해 보세요.</p>
      </form>}
      {mode === "reset" && <form onSubmit={run(() => actions.requestReset(email), "code")} className="nc-form">
        <h1>비밀번호 찾기</h1>
        <p className="nc-hint">관리자 이메일로 6자리 인증코드를 보내 드립니다. 코드는 10분 동안 유효합니다.</p>
        <label>관리자 이메일<input type="email" value={email} onChange={e => setEmail(e.target.value)} /></label>
        {err && <p className="nc-err" role="alert">{err}</p>}
        <button className="nc-btn block">인증코드 받기</button>
        <button type="button" className="nc-link" onClick={() => { setErr(""); setMode("login"); }}>로그인으로 돌아가기</button>
      </form>}
      {mode === "code" && <form onSubmit={run(() => actions.verifyCode("reset", code, newPw), "done")} className="nc-form">
        <h1>새 비밀번호 설정</h1>
        <label>인증코드<input inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ""))} placeholder="6자리 숫자" /></label>
        <label>새 비밀번호 (8자 이상)<input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} autoComplete="new-password" /></label>
        {err && <p className="nc-err" role="alert">{err}</p>}
        <button className="nc-btn block">비밀번호 변경</button>
        <div className="nc-row-links">
          <button type="button" className="nc-link" onClick={() => { const r = actions.requestReset(state.account.email); setErr(r ?? ""); }}>인증코드 다시 받기</button>
          <button type="button" className="nc-link muted" onClick={actions.expireCode}>(데모) 코드 만료시키기</button>
        </div>
      </form>}
      {mode === "done" && <div className="nc-form">
        <h1>비밀번호가 변경되었습니다</h1>
        <p className="nc-hint">새 비밀번호로 로그인해 주세요.</p>
        <button className="nc-btn block" onClick={() => { setPw(""); setMode("login"); }}>로그인하기</button>
      </div>}
    </div>
    {(mode === "code" || mode === "done") && <MailPreview mail={state.mails[0]} />}
    <a className="nc-auth-back" href="/demo/nurse">샘플 소개로 돌아가기</a>
  </div>;
}
function MailPreview({ mail }: { mail: Mail | undefined }) {
  if (!mail) return null;
  return <aside className="nc-mail-preview" aria-label="데모 메일함">
    <p className="nc-kicker">데모 메일함 · 실제로는 관리자 메일로 도착합니다</p>
    <strong>{mail.subject}</strong><span>받는 사람 {mail.to}</span>
    <pre>{mail.body}</pre>
  </aside>;
}

/* ---------- 대시보드 ---------- */
function Dashboard({ go, edit }: { go: (m: Menu) => void; edit: (id: string) => void }) {
  const { state } = useNurse();
  const fresh = state.inquiries.filter(q => q.status === "new");
  const failed = state.inquiries.filter(q => q.mail === "failed").length;
  const pub = state.posts.filter(p => p.status === "published").length;
  const drafts = state.posts.filter(p => p.status === "draft");
  return <>
    <h1 className="nc-h1">대시보드</h1>
    <div className="nc-kpis">
      <Kpi label="새 상담 신청" value={`${fresh.length}건`} sub="확인하러 가기 →" warn={fresh.length > 0} onClick={() => go("inquiries")} />
      <Kpi label="알림 메일 미발송" value={`${failed}건`} sub={failed ? "다시 보내기 필요" : "모두 발송됨"} warn={failed > 0} onClick={() => go("inquiries")} />
      <Kpi label="발행된 글" value={`${pub}개`} sub="블로그 관리 →" onClick={() => go("posts")} />
      <Kpi label="이미지" value={`${state.images.length}장`} sub="이미지 관리 →" onClick={() => go("images")} />
    </div>
    <div className="nc-grid2">
      <section className="nc-panel"><h2>최근 상담 신청</h2>
        <ul className="nc-list">{state.inquiries.slice(0, 5).map(q => <li key={q.id}><time>{fmtTime(q.at)}</time><span><b>{q.name}</b> · {q.area} — {q.message.slice(0, 34)}{q.message.length > 34 ? "…" : ""}</span>{q.status === "new" && <em className="nc-tag warn">새 신청</em>}</li>)}</ul>
      </section>
      <section className="nc-panel"><h2>작성 중인 글</h2>
        {drafts.length ? <ul className="nc-list">{drafts.map(p => <li key={p.id}><time>{fmtTime(p.updatedAt)}</time><button className="nc-link" onClick={() => edit(p.id)}>{p.title}</button></li>)}</ul> : <p className="nc-hint">임시저장된 글이 없습니다.</p>}
      </section>
    </div>
  </>;
}
function Kpi({ label, value, sub, warn, onClick }: { label: string; value: string; sub: string; warn?: boolean; onClick?: () => void }) {
  return <button className={"nc-kpi" + (warn ? " warn" : "")} onClick={onClick}><span>{label}</span><strong>{value}</strong><small>{sub}</small></button>;
}

/* ---------- 상담 신청 ---------- */
function Inquiries() {
  const { state, actions } = useNurse();
  const [sel, setSel] = useState<string | null>(state.inquiries[0]?.id ?? null);
  const [filter, setFilter] = useState<"all" | "new" | "done">("all");
  const list = state.inquiries.filter(q => filter === "all" || q.status === filter);
  const q = state.inquiries.find(x => x.id === sel);
  return <>
    <h1 className="nc-h1">상담 신청</h1>
    <div className="nc-toolbar">
      <div className="nc-tabs">{([["all", "전체"], ["new", "새 신청"], ["done", "처리 완료"]] as const).map(([id, l]) =>
        <button key={id} className={filter === id ? "on" : ""} onClick={() => setFilter(id)}>{l} <b>{state.inquiries.filter(x => id === "all" || x.status === id).length}</b></button>)}</div>
      <p className="nc-hint">홈페이지에서 접수하면 이 목록에 저장되고, 관리자 이메일로 알림이 갑니다.</p>
    </div>
    <div className="nc-split">
      <div className="nc-table-wrap"><table className="nc-atable">
        <thead><tr><th>접수</th><th>성함</th><th>지역</th><th>등급</th><th>알림 메일</th><th>상태</th></tr></thead>
        <tbody>{list.map(x => <tr key={x.id} className={x.id === sel ? "sel" : ""} onClick={() => setSel(x.id)}>
          <td>{fmtTime(x.at)}</td><td>{x.name}</td><td>{x.area || "-"}</td><td>{x.grade}</td>
          <td>{x.mail === "sent" ? <span className="nc-tag ok">발송</span> : <span className="nc-tag bad">실패</span>}</td>
          <td>{x.status === "new" ? <span className="nc-tag warn">새 신청</span> : <span className="nc-tag">완료</span>}</td>
        </tr>)}</tbody>
      </table>{!list.length && <p className="nc-hint pad">해당하는 신청이 없습니다.</p>}</div>
      {q && <InquiryDetail q={q} done={() => actions.setInquiryStatus(q.id, q.status === "new" ? "done" : "new")} resend={() => actions.resendInquiry(q.id)} />}
    </div>
  </>;
}
function InquiryDetail({ q, done, resend }: { q: Inquiry; done: () => void; resend: () => void }) {
  return <section className="nc-panel nc-detail-panel">
    <h2>{q.name} <small>{fmtTime(q.at)}</small></h2>
    <dl className="nc-adl"><dt>연락처</dt><dd>{q.phone}</dd><dt>관계</dt><dd>{q.relation}</dd><dt>지역</dt><dd>{q.area || "-"}</dd><dt>장기요양 등급</dt><dd>{q.grade}</dd><dt>연락 시간</dt><dd>{q.time}</dd></dl>
    <p className="nc-msg">{q.message || "(문의 내용 없음)"}</p>
    {q.mail === "failed" && <p className="nc-err">관리자 알림 메일 발송에 실패했습니다. 접수 내용은 안전하게 저장되어 있습니다.</p>}
    <div className="nc-actions">
      <button className="nc-abtn" onClick={done}>{q.status === "new" ? "처리 완료로 표시" : "새 신청으로 되돌리기"}</button>
      {q.mail === "failed" && <button className="nc-abtn ghost" onClick={resend}>알림 메일 다시 보내기</button>}
    </div>
  </section>;
}

/* ---------- 블로그 목록 ---------- */
function Posts({ edit }: { edit: (id: string) => void }) {
  const { state, actions } = useNurse();
  const create = () => {
    const id = uid();
    actions.savePost({ id, slug: `new-post-${id}`, title: "새 글", body: "", cover: null, status: "draft", publishedAt: null, updatedAt: "", seoTitle: "", seoDesc: "", faq: [] });
    edit(id);
  };
  const posts = [...state.posts].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return <>
    <div className="nc-h1-row"><h1 className="nc-h1">블로그</h1><button className="nc-abtn" onClick={create}>새 글 쓰기</button></div>
    <div className="nc-table-wrap"><table className="nc-atable">
      <thead><tr><th>제목</th><th>상태</th><th>발행일</th><th>최근 수정</th><th>검색 설정</th><th /></tr></thead>
      <tbody>{posts.map(p => <tr key={p.id} onClick={() => edit(p.id)}>
        <td className="wrap"><b>{p.title}</b><small className="nc-url">/blog/{p.slug}</small></td>
        <td>{p.status === "published" ? <span className="nc-tag ok">발행</span> : <span className="nc-tag">임시저장</span>}</td>
        <td>{fmtDate(p.publishedAt) || "-"}</td><td>{fmtTime(p.updatedAt || new Date().toISOString())}</td>
        <td>{p.seoTitle && p.seoDesc ? <span className="nc-tag ok">완료</span> : <span className="nc-tag warn">미입력</span>}</td>
        <td>{p.status === "published" && <a className="nc-link" href={postUrl(p.slug)} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>보기 ↗</a>}</td>
      </tr>)}</tbody>
    </table></div>
  </>;
}

/* ---------- 블로그 편집 ---------- */
function Editor({ id, close }: { id: string; close: () => void }) {
  const { state, actions } = useNurse();
  const original = state.posts.find(p => p.id === id);
  const [p, setP] = useState<Post | null>(original ?? null);
  const [slugTouched, setSlugTouched] = useState(!!original && !original.slug.startsWith("new-post-"));
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [picker, setPicker] = useState<null | "cover" | "insert">(null);
  const [tab, setTab] = useState<"write" | "preview">("write");
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  if (!p) return <p className="nc-hint">글을 찾을 수 없습니다. <button className="nc-link" onClick={close}>목록으로</button></p>;

  const set = (patch: Partial<Post>) => setP({ ...p, ...patch });
  const save = (status: Post["status"]) => {
    const next: Post = { ...p, status, publishedAt: status === "published" ? (p.publishedAt ?? new Date().toISOString()) : p.publishedAt };
    const r = actions.savePost(next);
    if (r) return setMsg({ ok: false, text: r });
    setP(next);
    setMsg({ ok: true, text: status === "published" ? "발행했습니다. 홈페이지 블로그에 바로 보입니다." : p.status === "published" ? "발행을 취소하고 임시저장했습니다." : "임시저장했습니다." });
  };
  const insertImage = (img: ImageItem) => {
    const el = bodyRef.current; const token = `\n[이미지:${img.id}]\n`;
    const at = el ? el.selectionStart : p.body.length;
    set({ body: p.body.slice(0, at) + token + p.body.slice(at) });
  };
  const setFaq = (i: number, patch: Partial<FaqItem>) => set({ faq: p.faq.map((f, j) => j === i ? { ...f, ...patch } : f) });
  const cover = state.images.find(i => i.id === p.cover);
  const title = p.seoTitle || p.title; const desc = p.seoDesc || excerpt(p.body, 120);

  return <>
    <div className="nc-h1-row">
      <h1 className="nc-h1"><button className="nc-link" onClick={close}>블로그</button> / {original?.status === "published" ? "글 수정" : "글 쓰기"}</h1>
      <div className="nc-actions">
        {p.status === "published" && <a className="nc-abtn ghost" href={postUrl(p.slug)} target="_blank" rel="noreferrer">홈페이지에서 보기 ↗</a>}
        <button className="nc-abtn ghost" onClick={() => save("draft")}>{p.status === "published" ? "발행 취소" : "임시저장"}</button>
        <button className="nc-abtn" onClick={() => save("published")}>{p.status === "published" ? "수정 내용 발행" : "발행하기"}</button>
      </div>
    </div>
    {msg && <p className={msg.ok ? "nc-ok" : "nc-err"} role="status">{msg.text}</p>}
    <div className="nc-editor">
      <div className="nc-editor-main">
        <section className="nc-panel nc-form">
          <label>제목<input className="big" value={p.title} onChange={e => set({ title: e.target.value, ...(slugTouched ? {} : { slug: slugify(e.target.value) || p.slug }) })} /></label>
          <div className="nc-tabs small"><button className={tab === "write" ? "on" : ""} onClick={() => setTab("write")}>작성</button><button className={tab === "preview" ? "on" : ""} onClick={() => setTab("preview")}>미리보기</button></div>
          {tab === "write" ? <>
            <div className="nc-toolbar-row">
              <button type="button" onClick={() => set({ body: p.body + "\n## 소제목\n" })}>소제목</button>
              <button type="button" onClick={() => set({ body: p.body + "\n- 목록 항목\n" })}>목록</button>
              <button type="button" onClick={() => setPicker("insert")}>이미지 넣기</button>
              <span className="nc-hint">‘## ’로 시작하면 소제목, ‘- ’로 시작하면 목록이 됩니다.</span>
            </div>
            <textarea ref={bodyRef} className="nc-body-input" rows={18} value={p.body} onChange={e => set({ body: e.target.value })} />
          </> : <div className="nc-preview"><h1>{p.title}</h1>{cover && <Pic img={cover} className="nc-cover" />}<Body text={p.body} images={state.images} /></div>}
        </section>
      </div>

      <div className="nc-editor-side">
        <section className="nc-panel">
          <h2>대표 이미지</h2>
          <div className="nc-cover-pick"><Pic img={cover} className="thumb" fallback="home" />{!cover && <span className="nc-hint">선택 안 함 (목록에 기본 이미지)</span>}</div>
          <div className="nc-actions"><button className="nc-abtn ghost small" onClick={() => setPicker("cover")}>{cover ? "변경" : "선택"}</button>{cover && <button className="nc-abtn ghost small" onClick={() => set({ cover: null })}>빼기</button>}</div>
        </section>

        <section className="nc-panel nc-form">
          <h2>검색 노출 설정 <small>SEO</small></h2>
          <label>주소(URL)<div className="nc-prefix"><span>/blog/</span><input value={p.slug} onChange={e => { setSlugTouched(true); set({ slug: e.target.value.toLowerCase().replace(/\s+/g, "-") }); }} /></div></label>
          <label>검색 제목 <Counter n={p.seoTitle.length} max={40} /><input value={p.seoTitle} placeholder={`${p.title} | ${CENTER.name}`} onChange={e => set({ seoTitle: e.target.value })} /></label>
          <label>검색 설명 <Counter n={p.seoDesc.length} max={80} /><textarea rows={3} value={p.seoDesc} placeholder="비워 두면 본문 첫 문단으로 채워집니다." onChange={e => set({ seoDesc: e.target.value })} /></label>
          <div className="nc-serp" aria-label="검색 결과 미리보기">
            <span className="nc-serp-url">{PUBLIC_ORIGIN.replace("https://", "")} › blog › {p.slug}</span>
            <strong>{title.length > 40 ? title.slice(0, 39) + "…" : title}</strong>
            <p>{desc.length > 80 ? desc.slice(0, 79) + "…" : desc}</p>
          </div>
        </section>

        <section className="nc-panel nc-form">
          <h2>자주 묻는 질문 <small>GEO</small></h2>
          <p className="nc-hint">질문과 답을 따로 적어 두면 글 아래에 표시되고, 구조화 데이터로도 들어가 AI 검색이 답변을 인용하기 쉬워집니다.</p>
          {p.faq.map((f, i) => <div key={i} className="nc-faq-edit">
            <input value={f.q} placeholder="질문" onChange={e => setFaq(i, { q: e.target.value })} />
            <textarea rows={2} value={f.a} placeholder="답변" onChange={e => setFaq(i, { a: e.target.value })} />
            <button className="nc-link muted" onClick={() => set({ faq: p.faq.filter((_, j) => j !== i) })}>삭제</button>
          </div>)}
          <button className="nc-abtn ghost small" onClick={() => set({ faq: [...p.faq, { q: "", a: "" }] })}>질문 추가</button>
          <details className="nc-jsonld"><summary>자동 생성되는 구조화 데이터 보기 (JSON-LD)</summary><pre>{JSON.stringify(postJsonLd({ ...p, faq: p.faq.filter(f => f.q && f.a) }, state.images), null, 2)}</pre></details>
        </section>

        <button className="nc-link danger" onClick={() => { if (window.confirm("이 글을 삭제할까요? 되돌릴 수 없습니다.")) { actions.deletePost(p.id); close(); } }}>글 삭제</button>
      </div>
    </div>
    {picker && <ImagePicker onClose={() => setPicker(null)} onPick={img => { if (picker === "cover") set({ cover: img.id }); else insertImage(img); setPicker(null); }} />}
  </>;
}
function Counter({ n, max }: { n: number; max: number }) {
  return <span className={"nc-counter" + (n > max ? " over" : "")}>{n}/{max}자 권장</span>;
}
function ImagePicker({ onPick, onClose }: { onPick: (i: ImageItem) => void; onClose: () => void }) {
  const { state } = useNurse();
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [onClose]);
  return <div className="nc-modal-bg" onClick={onClose}>
    <div className="nc-modal" role="dialog" aria-modal="true" aria-label="이미지 선택" onClick={e => e.stopPropagation()}>
      <div className="nc-h1-row"><h2>이미지 선택</h2><button className="nc-link" onClick={onClose}>닫기</button></div>
      <ul className="nc-img-grid">{state.images.map(i => <li key={i.id}><button onClick={() => onPick(i)}><Pic img={i} /><span>{i.name}</span></button></li>)}</ul>
      <p className="nc-hint">새 사진은 ‘이미지’ 메뉴에서 올린 뒤 선택할 수 있습니다.</p>
    </div>
  </div>;
}

/* ---------- 이미지 ---------- */
const MAX_INPUT = 10 * 1024 * 1024;
const MAX_EDGE = 1280;
/** 올린 사진을 긴 변 1280px, WebP(미지원 시 JPEG)로 줄인다. 실제 구축에서는 서버에서 같은 규칙으로 변환한다. */
function optimize(file: File): Promise<{ src: string; width: number; height: number; bytes: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height));
      const w = Math.round(img.width * scale), h = Math.round(img.height * scale);
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      const ctx = c.getContext("2d"); if (!ctx) { URL.revokeObjectURL(url); return reject(new Error("이미지를 처리할 수 없습니다.")); }
      ctx.drawImage(img, 0, 0, w, h);
      let src = c.toDataURL("image/webp", 0.8);
      if (!src.startsWith("data:image/webp")) src = c.toDataURL("image/jpeg", 0.82);
      URL.revokeObjectURL(url);
      resolve({ src, width: w, height: h, bytes: Math.round((src.length - src.indexOf(",") - 1) * 3 / 4) });
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("이미지를 읽을 수 없습니다.")); };
    img.src = url;
  });
}
function Images() {
  const { state, actions } = useNurse();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const up = useRef<HTMLInputElement>(null);
  const rep = useRef<HTMLInputElement>(null);
  const cur = state.images.find(i => i.id === sel);
  const usedIn = (id: string) => state.posts.filter(p => p.cover === id || p.body.includes(`[이미지:${id}]`));

  async function handle(file: File | undefined, replaceId?: string) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) return setMsg({ ok: false, text: "JPG, PNG, WebP 파일만 올릴 수 있습니다." });
    if (file.size > MAX_INPUT) return setMsg({ ok: false, text: "10MB 이하 사진만 올릴 수 있습니다." });
    setBusy(true);
    try {
      const o = await optimize(file);
      const r = replaceId
        ? actions.replaceImage(replaceId, { ...o, originalBytes: file.size })
        : actions.addImage({ id: uid(), name: file.name.replace(/\.[^.]+$/, ""), alt: "", ...o, originalBytes: file.size, createdAt: new Date().toISOString() });
      setMsg(r ? { ok: false, text: r } : { ok: true, text: `${replaceId ? "교체" : "등록"}했습니다. ${fmtBytes(file.size)} → ${fmtBytes(o.bytes)} (${o.width}×${o.height}px)` });
    } catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : "이미지를 처리하지 못했습니다." }); }
    setBusy(false);
  }

  return <>
    <div className="nc-h1-row"><h1 className="nc-h1">이미지</h1>
      <button className="nc-abtn" disabled={busy} onClick={() => up.current?.click()}>{busy ? "처리 중…" : "사진 올리기"}</button>
      <input ref={up} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e => { void handle(e.target.files?.[0]); e.target.value = ""; }} />
      <input ref={rep} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e => { void handle(e.target.files?.[0], sel ?? undefined); e.target.value = ""; }} />
    </div>
    <p className="nc-hint">JPG·PNG·WebP, 10MB까지. 올리면 긴 변 1280px의 WebP로 자동 변환해 페이지가 빨리 열리게 합니다.</p>
    {msg && <p className={msg.ok ? "nc-ok" : "nc-err"} role="status">{msg.text}</p>}
    <div className="nc-split wide">
      <ul className="nc-img-grid">{state.images.map(i => <li key={i.id}><button className={sel === i.id ? "on" : ""} onClick={() => setSel(i.id)}><Pic img={i} /><span>{i.name}</span></button></li>)}</ul>
      {cur ? <section className="nc-panel nc-form nc-detail-panel">
        <Pic img={cur} className="nc-img-big" />
        <label>이름<input value={cur.name} onChange={e => actions.replaceImage(cur.id, { name: e.target.value })} /></label>
        <label>대체 텍스트 (검색·접근성)<input value={cur.alt} placeholder="사진을 설명하는 짧은 문장" onChange={e => actions.replaceImage(cur.id, { alt: e.target.value })} /></label>
        <dl className="nc-adl"><dt>크기</dt><dd>{cur.width}×{cur.height}px</dd><dt>용량</dt><dd>{cur.bytes ? fmtBytes(cur.bytes) : "기본 일러스트"}{cur.originalBytes ? ` (원본 ${fmtBytes(cur.originalBytes)})` : ""}</dd><dt>사용 중</dt><dd>{usedIn(cur.id).map(p => p.title).join(", ") || "없음"}</dd></dl>
        <div className="nc-actions">
          <button className="nc-abtn ghost" onClick={() => rep.current?.click()}>다른 사진으로 교체</button>
          <button className="nc-abtn ghost danger" onClick={() => {
            const n = usedIn(cur.id).length;
            if (window.confirm(n ? `${n}개 글에서 쓰는 사진입니다. 삭제하면 해당 글에서 빠집니다. 삭제할까요?` : "이 사진을 삭제할까요?")) { actions.deleteImage(cur.id); setSel(null); }
          }}>삭제</button>
        </div>
      </section> : <p className="nc-hint">사진을 고르면 이름·대체 텍스트를 고치고, 교체하거나 삭제할 수 있습니다.</p>}
    </div>
  </>;
}

/* ---------- 계정 ---------- */
function Account() {
  const { state, actions } = useNurse();
  const [step, setStep] = useState<"form" | "code" | "done">("form");
  const [newEmail, setNewEmail] = useState("");
  const [pw, setPw] = useState("");
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [cur, setCur] = useState(""); const [next, setNext] = useState(""); const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  return <>
    <h1 className="nc-h1">계정 설정</h1>
    <div className="nc-grid2">
      <section className="nc-panel nc-form">
        <h2>관리자 이메일 변경</h2>
        <p className="nc-hint">현재 이메일: <b>{state.account.email}</b></p>
        {step === "form" && <form className="nc-form" onSubmit={e => { e.preventDefault(); const r = actions.requestEmailChange(newEmail, pw); setErr(r ?? ""); if (!r) setStep("code"); }}>
          <label>새 이메일<input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} placeholder="new@example.com" /></label>
          <label>현재 비밀번호<input type="password" value={pw} onChange={e => setPw(e.target.value)} autoComplete="current-password" /></label>
          {err && <p className="nc-err" role="alert">{err}</p>}
          <button className="nc-abtn">새 이메일로 인증코드 받기</button>
        </form>}
        {step === "code" && <form className="nc-form" onSubmit={e => { e.preventDefault(); const r = actions.verifyCode("email", code); setErr(r ?? ""); if (!r) setStep("done"); }}>
          <p className="nc-hint"><b>{newEmail}</b>(으)로 보낸 6자리 코드를 입력해 주세요. 10분 동안 유효합니다.</p>
          <label>인증코드<input inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ""))} /></label>
          {err && <p className="nc-err" role="alert">{err}</p>}
          <div className="nc-actions"><button className="nc-abtn">확인</button><button type="button" className="nc-abtn ghost" onClick={() => { setStep("form"); setCode(""); setErr(""); }}>취소</button></div>
          <button type="button" className="nc-link muted" onClick={actions.expireCode}>(데모) 코드 만료시키기</button>
          <MailPreview mail={state.mails[0]} />
        </form>}
        {step === "done" && <div className="nc-form"><p className="nc-ok">관리자 이메일이 변경되었습니다. 다음 로그인부터 새 이메일을 사용합니다. 이전 이메일로도 변경 알림을 보냈습니다.</p>
          <button className="nc-abtn ghost" onClick={() => { setStep("form"); setNewEmail(""); setPw(""); setCode(""); }}>확인</button></div>}
      </section>

      <section className="nc-panel">
        <form className="nc-form" onSubmit={e => { e.preventDefault(); const r = actions.changePassword(cur, next); setPwMsg(r ? { ok: false, text: r } : { ok: true, text: "비밀번호를 변경했습니다." }); if (!r) { setCur(""); setNext(""); } }}>
          <h2>비밀번호 변경</h2>
          <label>현재 비밀번호<input type="password" value={cur} onChange={e => setCur(e.target.value)} autoComplete="current-password" /></label>
          <label>새 비밀번호 (8자 이상)<input type="password" value={next} onChange={e => setNext(e.target.value)} autoComplete="new-password" /></label>
          {pwMsg && <p className={pwMsg.ok ? "nc-ok" : "nc-err"} role="status">{pwMsg.text}</p>}
          <button className="nc-abtn">변경</button>
        </form>
        <hr />
        <h2>데모 설정</h2>
        <label className="nc-switch-row"><span><b>메일 발송 실패 상황 재현</b><small>켜고 홈페이지에서 상담을 신청하면, 접수는 저장되고 ‘알림 메일 미발송’으로 표시됩니다.</small></span>
          <input type="checkbox" checked={state.mailFail} onChange={e => actions.setMailFail(e.target.checked)} /></label>
      </section>
    </div>
  </>;
}

/* ---------- 보낸 메일 ---------- */
function Mails() {
  const { state } = useNurse();
  const [open, setOpen] = useState<string | null>(state.mails[0]?.id ?? null);
  return <>
    <h1 className="nc-h1">보낸 메일 <small className="nc-hint">데모 전용 · 실제로는 메일함으로 발송됩니다</small></h1>
    <ul className="nc-mails">{state.mails.map(m => <MailRow key={m.id} m={m} open={open === m.id} toggle={() => setOpen(open === m.id ? null : m.id)} />)}</ul>
  </>;
}
function MailRow({ m, open, toggle }: { m: Mail; open: boolean; toggle: () => void }): ReactNode {
  return <li className={open ? "open" : ""}>
    <button onClick={toggle}><time>{fmtTime(m.at)}</time><b>{m.subject}</b><span>{m.to}</span>{m.ok ? <span className="nc-tag ok">발송</span> : <span className="nc-tag bad">실패</span>}</button>
    {open && <pre>{m.body}</pre>}
  </li>;
}
