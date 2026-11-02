"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, BRIEF_FIELDS, won, type Brief, type ChatMessage } from "../_site/api";
import { SITE } from "../site-config";

type Row = { id: number; created_at: number; status: string; name: string; company: string; email: string; brief: Brief; quote_status: string | null; file_count?: number; lang?: "ko" | "en" };
type QuoteRow = { id: number; token: string; title: string; total: number; deposit: number; status: string; created_at: number; paid_at: number | null; payment_method: string | null };
type Detail = Row & { phone: string; message: string; transcript: ChatMessage[]; admin_note: string; quotes: QuoteRow[]; files: { id: number; original_name: string; size: number }[] };
type Listing = { inquiries: Row[]; smtp: boolean; consult: boolean; payments: "toss" | "mock" | "off" };

const ADMIN = { "X-Admin-Client": "1" };
const STATUS: Record<string, string> = { new: "신규", contacted: "연락함", quoted: "견적 발송", deposit_paid: "착수금 결제", in_progress: "진행 중", closed: "종료" };
const when = (s: number) => new Intl.DateTimeFormat("ko-KR", { dateStyle: "short", timeStyle: "short" }).format(new Date(s * 1000));

function QuoteForm({ detail, onCreated }: { detail: Detail; onCreated: (d: Detail, path: string, emailed: boolean, requested: boolean) => void }) {
  const [title, setTitle] = useState(detail.brief.title ?? "");
  const [items, setItems] = useState([{ name: "", amount: "" }]);
  const [deposit, setDeposit] = useState("");
  const [schedule, setSchedule] = useState(detail.brief.timeline ?? "");
  const [note, setNote] = useState("잔금은 완료 보고 후 7일 이내에 지급합니다.");
  const [sendEmail, setSendEmail] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const total = items.reduce((sum, item) => sum + (Number(item.amount.replace(/,/g, "")) || 0), 0);
  async function create(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api<{ path: string; inquiry: Detail; emailed: boolean }>(`/api/admin/inquiries/${detail.id}/quotes`, { method: "POST", headers: ADMIN, body: JSON.stringify({
        title, items: items.filter(i => i.name.trim()).map(i => ({ name: i.name.trim(), amount: Number(i.amount.replace(/,/g, "")) || 0 })),
        deposit: Number(deposit.replace(/,/g, "")) || 0, schedule, note, send_email: sendEmail }) });
      onCreated(result.inquiry, result.path, result.emailed, sendEmail);
    } catch (err) { setError(err instanceof Error ? err.message : "견적을 만들지 못했습니다."); } finally { setBusy(false); }
  }
  return <form className="st-form" onSubmit={create}>
    <h3 style={{ fontSize: 16 }}>견적서 만들기</h3>
    {detail.lang === "en" && <p className="st-badge st-badge-test" style={{ whiteSpace: "normal" }}>영문 사이트 고객입니다. 견적서 화면과 메일이 영어로 나가니 제목·항목·일정·안내 문구를 영어로 적어 주세요. 금액은 원화(KRW)입니다.</p>}
    <label>제목<input required minLength={2} maxLength={120} value={title} onChange={e => setTitle(e.target.value)} /></label>
    {items.map((item, i) => <div key={i} className="st-form-grid">
      <label>항목 {i + 1}<input maxLength={120} value={item.name} onChange={e => setItems(items.map((it, j) => j === i ? { ...it, name: e.target.value } : it))} placeholder="예: 상담 에이전트 개발" /></label>
      <label>금액 (원)<input inputMode="numeric" value={item.amount} onChange={e => setItems(items.map((it, j) => j === i ? { ...it, amount: e.target.value } : it))} placeholder="3000000" /></label>
    </div>)}
    <button type="button" className="st-button st-button-ghost" onClick={() => setItems([...items, { name: "", amount: "" }])}>항목 추가</button>
    <p>합계 <strong>{won(total)}</strong></p>
    <div className="st-form-grid">
      <label>착수금 (원)<input required inputMode="numeric" value={deposit} onChange={e => setDeposit(e.target.value)} placeholder={String(Math.round(total * 0.3))} /></label>
      <label>일정<input maxLength={1000} value={schedule} onChange={e => setSchedule(e.target.value)} /></label>
    </div>
    <label>안내 문구<textarea rows={3} maxLength={3000} value={note} onChange={e => setNote(e.target.value)} /></label>
    {error && <p className="st-error" role="alert">{error}</p>}
    <label style={{ flexDirection: "row", alignItems: "center", gap: 8, fontWeight: 500 }}><input type="checkbox" checked={sendEmail} onChange={e => setSendEmail(e.target.checked)} style={{ width: 18, height: 18 }} /> 고객({detail.email})에게 견적서 링크를 메일로 보내기</label>
    <button className="st-button" disabled={busy || total <= 0}>{sendEmail ? "견적서 만들고 메일 보내기" : "견적서 링크만 만들기"}</button>
  </form>;
}

export default function AdminApp() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [listing, setListing] = useState<Listing | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [link, setLink] = useState("");
  const [emailed, setEmailed] = useState<"sent" | "failed" | "off">("off");
  const doneRef = useRef<HTMLElement>(null);
  // After a quote is created, bring the completion panel into view.
  useEffect(() => { if (link) doneRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }, [link]);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try { setListing(await api<Listing>("/api/admin/inquiries")); setAuthed(true); }
    catch (err) { if ((err as { status?: number }).status === 401) setAuthed(false); else setError(err instanceof Error ? err.message : "불러오지 못했습니다."); }
  }, []);
  const open = useCallback(async (id: number) => {
    setLink(""); setError("");
    try { const d = await api<Detail>(`/api/admin/inquiries/${id}`); setDetail(d); setNote(d.admin_note); window.history.replaceState(null, "", `/admin?inquiry=${id}`); }
    catch (err) { setError(err instanceof Error ? err.message : "불러오지 못했습니다."); }
  }, []);

  useEffect(() => {
    void (async () => {
      await load();
      const id = Number(new URLSearchParams(window.location.search).get("inquiry"));
      if (id) await open(id);
    })();
  }, [load, open]);

  async function login(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { await api("/api/admin/login", { method: "POST", headers: ADMIN, body: JSON.stringify({ password }) }); setPassword(""); await load();
      const id = Number(new URLSearchParams(window.location.search).get("inquiry")); if (id) await open(id); }
    catch (err) { setError(err instanceof Error ? err.message : "로그인하지 못했습니다."); }
  }
  async function downloadFile(id: number, name: string) {
    setError("");
    try {
      const response = await fetch(`/api/admin/files/${id}`);
      if (!response.ok) throw new Error(response.status === 401 ? "다시 로그인해 주세요." : "파일을 내려받지 못했습니다.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url; link.download = name; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(err instanceof Error ? err.message : "파일을 내려받지 못했습니다."); }
  }
  async function update(body: object) {
    if (!detail) return;
    try { setDetail(await api<Detail>(`/api/admin/inquiries/${detail.id}`, { method: "POST", headers: ADMIN, body: JSON.stringify(body) })); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "저장하지 못했습니다."); }
  }

  return <div className="st-doc-page"><div className="st-wrap">
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, gap: 12, flexWrap: "wrap" }}>
      <Link href="/" className="st-logo">{SITE.name}<small>관리</small></Link>
      {authed && <button className="st-button st-button-ghost" onClick={() => void api("/api/admin/logout", { method: "POST", headers: ADMIN }).then(() => { setAuthed(false); setDetail(null); })}>로그아웃</button>}
    </div>
    {error && <p className="st-error" role="alert" style={{ marginBottom: 14 }}>{error}</p>}
    {authed === null && !error && <p style={{ color: "var(--muted)" }}>관리 정보를 불러오는 중입니다. 계속 이 화면이면 백엔드 서버가 켜져 있는지 확인해 주세요.</p>}
    {authed === false && <form className="st-form" style={{ maxWidth: 380 }} onSubmit={login}>
      <h1 style={{ fontSize: 20 }}>관리자 로그인</h1>
      <label>비밀번호<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button className="st-button">로그인</button>
    </form>}
    {authed && listing && <>
      <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 14 }}>
        AI 상담 {listing.consult ? "켜짐" : "꺼짐 (ANTHROPIC_API_KEY 필요)"} / 이메일 알림 {listing.smtp ? "켜짐" : "꺼짐 (SMTP 설정 필요)"} / 온라인 결제 {listing.payments === "toss" ? "켜짐" : listing.payments === "mock" ? "모의 결제 (로컬 테스트)" : "꺼짐 (TOSS 키 필요)"}
      </p>
      <div className="st-admin-grid">
        <section className="st-doc" style={{ padding: 0, overflow: "auto" }}>
          <table className="st-table"><thead><tr><th>접수</th><th>의뢰</th><th>상태</th></tr></thead>
            <tbody>{listing.inquiries.length === 0 && <tr><td colSpan={3}>아직 접수된 상담이 없습니다.</td></tr>}
              {listing.inquiries.map(r => <tr key={r.id} onClick={() => void open(r.id)} style={{ cursor: "pointer", background: detail?.id === r.id ? "#eef2ec" : undefined }}>
                <td style={{ whiteSpace: "nowrap" }}>#{r.id}<br /><small>{when(r.created_at)}</small></td>
                <td><button type="button" onClick={() => void open(r.id)} style={{ all: "unset", cursor: "pointer" }}><strong>{r.brief.title || r.company || r.name}</strong></button>{r.lang === "en" && <span className="st-badge" style={{ marginLeft: 6 }}>EN</span>}<br /><small>{r.company} {r.name}{r.file_count ? ` · 첨부 ${r.file_count}개` : ""}</small></td>
                <td><span className="st-badge">{STATUS[r.status] ?? r.status}</span></td>
              </tr>)}</tbody></table>
        </section>
        <section>
          {!detail && <p style={{ color: "var(--muted)" }}>왼쪽에서 상담을 선택하세요.</p>}
          {detail && <div style={{ display: "grid", gap: 18 }}>
            <article className="st-doc">
              <div className="st-doc-title"><h1 style={{ fontSize: 20, letterSpacing: 0 }}>#{detail.id} {detail.brief.title || "상담"}{detail.lang === "en" && <span className="st-badge" style={{ marginLeft: 8, verticalAlign: "middle" }}>영문 고객</span>}</h1>
                <label style={{ flexDirection: "row", alignItems: "center", gap: 8, whiteSpace: "nowrap" }}>상태<select value={detail.status} onChange={e => void update({ status: e.target.value })}>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label></div>
              <p><strong>{detail.name}</strong> {detail.company && `(${detail.company})`}<br /><a href={`mailto:${detail.email}`}>{detail.email}</a> {detail.phone}</p>
              <dl style={{ display: "grid", gap: 8, marginTop: 14 }}>{BRIEF_FIELDS.map(([key, label]) => {
                const value = detail.brief[key]; if (!value || (Array.isArray(value) && !value.length)) return null;
                return <div key={key} style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 10, borderTop: "1px dashed var(--rule)", paddingTop: 8 }}><dt style={{ color: "var(--muted)" }}>{label}</dt><dd style={{ margin: 0 }}>{Array.isArray(value) ? value.join(", ") : value}</dd></div>;
              })}</dl>
              {detail.message && <p className="st-note"><strong>직접 남긴 내용</strong><br />{detail.message}</p>}
              {detail.files.length > 0 && <div className="st-note"><strong>첨부 파일</strong>
                <ul className="st-file-list">{detail.files.map(f => <li key={f.id}><span>{f.original_name}</span><small>{(f.size / 1024 / 1024).toFixed(1)}MB</small>
                  <button type="button" className="st-text-link" style={{ marginTop: 0 }} onClick={() => void downloadFile(f.id, f.original_name)}>내려받기</button></li>)}</ul></div>}
              {detail.transcript.length > 0 && <details style={{ marginTop: 14 }}><summary>AI 상담 대화 보기 ({detail.transcript.length})</summary>
                <div style={{ display: "grid", gap: 8, marginTop: 10 }}>{detail.transcript.map((m, i) => <p key={i} className={"st-msg st-msg-" + m.role} style={{ maxWidth: "100%" }}>{m.content}</p>)}</div></details>}
              <label style={{ marginTop: 16 }}>메모<textarea rows={3} value={note} onChange={e => setNote(e.target.value)} /></label>
              <button className="st-button st-button-ghost" style={{ marginTop: 8 }} onClick={() => void update({ admin_note: note })}>메모 저장</button>
            </article>
            {detail.quotes.length > 0 && <article className="st-doc"><h3 style={{ fontSize: 16, marginBottom: 10 }}>견적서</h3>
              <table className="st-table"><tbody>{detail.quotes.map(q => <tr key={q.id}><td><a href={`/quote?t=${q.token}`} target="_blank" rel="noreferrer">{q.title}</a><br /><small>{when(q.created_at)}</small><br /><small className="st-admin-docs">{[["/contract", "계약서(안)"], ["/contract/nda", "NDA"], ["/contract/completion", "완료 확인서"], ["/contract/maintenance", "유지보수 계약서"]].map(([href, label]) => <a key={href} href={`${href}?t=${q.token}`} target="_blank" rel="noreferrer">{label}</a>)}</small></td>
                <td className="st-num">{won(q.total)}<br /><small>착수금 {won(q.deposit)}</small></td><td><span className="st-badge">{q.status === "paid" ? `결제 완료${q.payment_method ? ` (${q.payment_method})` : ""}` : "발송"}</span></td></tr>)}</tbody></table></article>}
            {link ? <article className="st-doc st-quote-done" role="status" ref={doneRef}>
              <h3>{emailed === "sent" ? "견적서를 발송했습니다" : "견적서를 만들었습니다"}</h3>
              <p>{emailed === "sent" ? `고객(${detail.email})에게 견적서 링크를 메일로 보냈습니다.` : emailed === "failed" ? "메일 설정(SMTP)이 없어 메일은 보내지 못했습니다. 아래 링크를 고객에게 직접 보내 주세요." : "아래 링크를 고객에게 보내 주세요."}</p>
              <p className="st-quote-done-link"><a href={link} target="_blank" rel="noreferrer">{window.location.origin}{link}</a></p>
              <div className="st-quote-done-actions">
                <a href={link} target="_blank" rel="noreferrer" className="st-button">견적서 열기</a>
                <button type="button" className="st-button st-button-ghost" onClick={() => setLink("")}>새 견적서 만들기</button>
              </div>
            </article>
            : <QuoteForm key={detail.id} detail={detail} onCreated={(d, path, sent, requested) => { setDetail(d); setLink(path); setEmailed(sent ? "sent" : requested ? "failed" : "off"); void load(); }} />}
          </div>}
        </section>
      </div>
    </>}
  </div></div>;
}
