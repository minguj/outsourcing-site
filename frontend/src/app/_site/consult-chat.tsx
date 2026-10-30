"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, BRIEF_FIELDS, createDemoQuote, type Brief, type ChatMessage } from "./api";
import { InquiryForm } from "./inquiry-form";
import { FAQ } from "../site-content";

const GREETING: ChatMessage = { role: "assistant", content: "안녕하세요. 외주 개발 상담을 도와드려요. 자주 묻는 질문은 아래 버튼으로 바로 확인하실 수 있고, 만들고 싶은 것을 말씀해 주시면 담당자가 볼 수 있게 정리해 드릴게요." };

function BriefCard({ brief }: { brief: Brief }) {
  return <section className="st-brief" aria-label="정리된 의뢰 내용">
    <span className="st-stamp" aria-hidden="true">접수 준비</span>
    <h3>{brief.title || "의뢰 요약"}</h3>
    <dl>{BRIEF_FIELDS.map(([key, label]) => {
      const value = brief[key];
      if (!value || (Array.isArray(value) && value.length === 0)) return null;
      return <div key={key}><dt>{label}</dt><dd>{Array.isArray(value) ? value.join(", ") : value}</dd></div>;
    })}</dl>
  </section>;
}

export function ConsultChat({ onFallback }: { onFallback: () => void }) {
  const [ready, setReady] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [asked, setAsked] = useState<string[]>([]);
  const log = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    api<{ consult_ready: boolean }>("/api/site/config").then(c => setReady(c.consult_ready)).catch(() => setReady(false));
  }, []);
  const briefRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const box = log.current;
    if (!box) return;
    // When the summary arrives, bring its top (with the stamp) into view instead of jumping past it.
    const target = brief && briefRef.current ? briefRef.current.offsetTop - box.offsetTop - 12 : box.scrollHeight;
    box.scrollTo({ top: target, behavior: "smooth" });
  }, [messages, busy, brief]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next); setInput(""); setBusy(true); setError("");
    try {
      const result = await api<{ reply: string; brief: Brief | null }>("/api/consult/chat", { method: "POST", body: JSON.stringify({ messages: next }) });
      setMessages([...next, { role: "assistant", content: result.reply }]);
      if (result.brief) setBrief(result.brief);
    } catch (err) {
      const status = (err as { status?: number }).status;
      setError(err instanceof Error ? err.message : "답변을 받지 못했습니다.");
      if (status === 503) setReady(false);
      setMessages(messages); setInput(content);
    } finally { setBusy(false); }
  }

  // Frequently asked questions are answered from the page itself: instant, and no AI tokens are used.
  function answer(q: string, a: string) {
    if (busy) return;
    setMessages([...messages, { role: "user", content: q }, { role: "assistant", content: a }]);
    setAsked([...asked, q]);
  }
  async function demo() {
    setBusy(true); setError("");
    try { router.push(await createDemoQuote(brief?.title)); } catch (err) { setError(err instanceof Error ? err.message : "체험을 시작하지 못했습니다."); setBusy(false); }
  }
  const remaining = FAQ.filter(f => !asked.includes(f.q));
  const offline = ready === false;

  return <div className="st-chat" aria-busy={busy}>
    <div className="st-chat-head"><strong>상담 기록지</strong><span>{brief ? "정리 완료" : offline ? "자주 묻는 질문" : "AI 상담 중"}</span></div>
    <div className="st-chat-log" ref={log} role="log" aria-live="polite" aria-label="AI 상담 대화">
      {messages.map((m, i) => <p key={i} className={"st-msg st-msg-" + m.role}>{m.content}</p>)}
      {busy && <p className="st-msg st-msg-assistant st-typing" aria-label="답변 작성 중"><span /><span /><span /></p>}
      {brief && <div ref={briefRef}><BriefCard brief={brief} /></div>}
      {brief && !submitted && <div className="st-chat-submit"><p>위 내용이 맞으면 연락처를 남겨 주세요. 고칠 부분은 아래에 말씀하셔도 됩니다.</p><InquiryForm compact brief={brief} transcript={messages} onDone={() => setSubmitted(true)} /></div>}
      {submitted && <p className="st-msg st-msg-assistant">접수되었습니다. 담당자가 검토 후 이메일로 연락드릴게요. 감사합니다.</p>}
    </div>
    {!submitted && <div className="st-starters" aria-label="자주 묻는 질문">
      {remaining.map(f => <button key={f.q} type="button" disabled={busy} onClick={() => answer(f.q, f.a)}>{f.q}</button>)}
      <button type="button" className="st-starter-demo" disabled={busy} onClick={() => void demo()}>견적·결제 흐름 체험</button>
    </div>}
    {error && <p className="st-error st-chat-error" role="alert">{error}</p>}
    {!submitted && (offline
      ? <div className="st-chat-offline-note"><p>AI 자유 상담을 준비하고 있어요. 위 질문을 눌러 보시거나, 문의 양식으로 남겨 주시면 담당자가 정리해 연락드립니다.</p>
          <button className="st-button" onClick={onFallback}>문의 양식으로 이동</button></div>
      : <form className="st-chat-input" onSubmit={e => { e.preventDefault(); void send(input); }}>
          <textarea aria-label="상담 내용 입력" rows={2} maxLength={1500} value={input} disabled={busy || ready === null} placeholder="예: 쇼핑몰 문의에 답하는 상담사와 관리자 페이지가 필요해요"
            onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(input); } }} />
          <button className="st-button" disabled={busy || !input.trim()}>보내기</button>
        </form>)}
  </div>;
}
