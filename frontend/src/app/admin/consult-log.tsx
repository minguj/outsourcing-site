"use client";

import { useCallback, useEffect, useState } from "react";
import { api, BRIEF_FIELDS, type Brief, type ChatMessage } from "../_site/api";

// 관리자: AI 상담 기록. 접수 여부와 관계없이 보관된 대화를 보고, 요청이 있으면 지운다.
type Row = { id: string; created_at: number; updated_at: number; lang: "ko" | "en"; user_turns: number; first: string; title: string; has_brief: boolean; inquiry_id: number | null };
type Stats = { days: number; total: number; briefs: number; submitted: number; avg_turns: number; retention_days: number };
type Record_ = { id: string; created_at: number; updated_at: number; lang: "ko" | "en"; messages: ChatMessage[]; brief: Brief; user_turns: number; inquiry_id: number | null };

const ADMIN = { "X-Admin-Client": "1" };
const when = (s: number) => new Intl.DateTimeFormat("ko-KR", { dateStyle: "short", timeStyle: "short" }).format(new Date(s * 1000));
const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}%` : "-");

export function ConsultLog({ onOpenInquiry }: { onOpenInquiry: (id: number) => void }) {
  const [days, setDays] = useState(30);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [detail, setDetail] = useState<Record_ | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const result = await api<{ consults: Row[]; stats: Stats }>(`/api/admin/consults?days=${days}&q=${encodeURIComponent(query)}`);
      setRows(result.consults); setStats(result.stats);
    } catch (err) { setError(err instanceof Error ? err.message : "불러오지 못했습니다."); }
  }, [days, query]);
  useEffect(() => { void load(); }, [load]);

  async function open(id: string) {
    setError("");
    try { setDetail(await api<Record_>(`/api/admin/consults/${id}`)); }
    catch (err) { setError(err instanceof Error ? err.message : "불러오지 못했습니다."); }
  }
  async function remove(id: string) {
    if (!window.confirm("이 상담 기록을 삭제할까요? 되돌릴 수 없습니다.")) return;
    try { await api(`/api/admin/consults/${id}`, { method: "DELETE", headers: ADMIN }); setDetail(null); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "삭제하지 못했습니다."); }
  }

  return <>
    <div className="st-consult-toolbar">
      <label>기간<select value={days} onChange={e => setDays(Number(e.target.value))}>{[7, 30, 90].map(d => <option key={d} value={d}>최근 {d}일</option>)}</select></label>
      <form onSubmit={e => { e.preventDefault(); setQuery(q); }} className="st-consult-search">
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="대화 내용 검색" aria-label="대화 내용 검색" />
        <button className="st-button st-button-ghost">검색</button>
        {query && <button type="button" className="st-text-link" style={{ marginTop: 0 }} onClick={() => { setQ(""); setQuery(""); }}>검색 해제</button>}
      </form>
    </div>
    {stats && <div className="st-consult-stats">
      <div><span>상담</span><strong>{stats.total}건</strong></div>
      <div><span>요약까지 진행</span><strong>{stats.briefs}건</strong><small>{pct(stats.briefs, stats.total)}</small></div>
      <div><span>접수로 이어짐</span><strong>{stats.submitted}건</strong><small>{pct(stats.submitted, stats.total)}</small></div>
      <div><span>평균 질문 수</span><strong>{stats.avg_turns}개</strong></div>
    </div>}
    {stats && <p className="st-consult-note">AI 상담 대화는 마지막 대화 후 {stats.retention_days}일이 지나면 자동으로 삭제됩니다. 자주 묻는 질문 버튼만 누르고 AI에게 묻지 않은 방문은 기록되지 않습니다.</p>}
    {error && <p className="st-error" role="alert">{error}</p>}
    <div className="st-admin-grid">
      <section className="st-doc" style={{ padding: 0, overflow: "auto" }}>
        <table className="st-table"><thead><tr><th>시각</th><th>첫 질문</th><th>결과</th></tr></thead>
          <tbody>
            {rows?.length === 0 && <tr><td colSpan={3}>{query ? "검색 결과가 없습니다." : "이 기간에 AI 상담 기록이 없습니다."}</td></tr>}
            {rows?.map(r => <tr key={r.id} onClick={() => void open(r.id)} style={{ cursor: "pointer", background: detail?.id === r.id ? "#eef2ec" : undefined }}>
              <td style={{ whiteSpace: "nowrap" }}><small>{when(r.updated_at)}</small><br /><small>질문 {r.user_turns}개</small></td>
              <td><strong className="st-consult-first">{r.title || r.first || "(질문 없음)"}</strong>{r.title && <><br /><small className="st-consult-first">{r.first}</small></>}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                {r.inquiry_id ? <span className="st-badge st-badge-ok">접수 #{r.inquiry_id}</span> : r.has_brief ? <span className="st-badge">요약</span> : <span className="st-badge st-badge-muted">대화만</span>}
                {r.lang === "en" && <span className="st-badge" style={{ marginLeft: 4 }}>EN</span>}</td>
            </tr>)}
          </tbody></table>
      </section>
      <section>
        {!detail && <p style={{ color: "var(--muted)" }}>왼쪽에서 상담 기록을 선택하세요.</p>}
        {detail && <article className="st-doc">
          <div className="st-doc-title"><h1 style={{ fontSize: 18, letterSpacing: 0 }}>{detail.brief.title || "AI 상담 기록"}{detail.lang === "en" && <span className="st-badge" style={{ marginLeft: 8, verticalAlign: "middle" }}>영문</span>}</h1>
            <button type="button" className="st-button st-button-ghost" onClick={() => void remove(detail.id)}>기록 삭제</button></div>
          <p style={{ fontSize: 13, color: "var(--muted)" }}>시작 {when(detail.created_at)} · 마지막 {when(detail.updated_at)} · 질문 {detail.user_turns}개
            {detail.inquiry_id && <> · <button type="button" className="st-text-link" style={{ marginTop: 0 }} onClick={() => onOpenInquiry(detail.inquiry_id!)}>접수 #{detail.inquiry_id} 보기</button></>}</p>
          {Object.keys(detail.brief).length > 0 && <dl style={{ display: "grid", gap: 8, margin: "14px 0" }}>{BRIEF_FIELDS.map(([key, label]) => {
            const value = detail.brief[key]; if (!value || (Array.isArray(value) && !value.length)) return null;
            return <div key={key} style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 10, borderTop: "1px dashed var(--rule)", paddingTop: 8 }}><dt style={{ color: "var(--muted)" }}>{label}</dt><dd style={{ margin: 0 }}>{Array.isArray(value) ? value.join(", ") : value}</dd></div>;
          })}</dl>}
          <div style={{ display: "grid", gap: 8, marginTop: 10 }}>{detail.messages.map((m, i) => <p key={i} className={"st-msg st-msg-" + m.role} style={{ maxWidth: "100%" }}>{m.content}</p>)}</div>
        </article>}
      </section>
    </div>
  </>;
}
