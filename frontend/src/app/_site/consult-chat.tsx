"use client";

import { useEffect, useRef, useState } from "react";
import { api, BRIEF_FIELDS, type Brief, type ChatMessage } from "./api";
import { InquiryForm } from "./inquiry-form";

const GREETING: ChatMessage = { role: "assistant", content: "안녕하세요. 어떤 일을 자동화하거나 만들고 싶으신지 편하게 말씀해 주세요. 몇 가지만 여쭤보고 담당자가 볼 수 있게 정리해 드릴게요." };
const STARTERS = ["고객 문의에 답하는 AI 상담사가 필요해요", "거래처 엑셀을 우리 양식으로 바꾸고 싶어요", "쇼핑몰 주문을 ERP에 자동으로 넣고 싶어요"];
const EXAMPLE: ChatMessage[] = [
  { role: "user", content: "거래처마다 발주서 엑셀 양식이 달라서 매일 손으로 옮겨 적어요." },
  { role: "assistant", content: "하루에 몇 건 정도, 거래처는 몇 곳인가요? 옮겨 적은 결과는 어디에 쓰시나요(거래명세서, ERP 등)?" },
  { role: "user", content: "거래처 8곳, 하루 30건쯤이고 거래명세서로 나가요." },
];

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
  const log = useRef<HTMLDivElement>(null);

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

  if (ready === false) {
    return <div className="st-chat st-chat-offline">
      <div className="st-chat-head"><strong>상담 기록지</strong><span>예시 대화</span></div>
      <div className="st-chat-log" aria-label="AI 상담 예시 대화">{[GREETING, ...EXAMPLE].map((m, i) => <p key={i} className={"st-msg st-msg-" + m.role}>{m.content}</p>)}</div>
      <div className="st-chat-offline-note"><p>AI 상담을 준비하고 있어요. 지금은 문의 양식으로 남겨 주시면 담당자가 같은 방식으로 정리해 연락드립니다.</p>
        <button className="st-button" onClick={onFallback}>문의 양식으로 이동</button></div>
    </div>;
  }

  return <div className="st-chat" aria-busy={busy}>
    <div className="st-chat-head"><strong>상담 기록지</strong><span>{brief ? "정리 완료" : "AI 상담 중"}</span></div>
    <div className="st-chat-log" ref={log} role="log" aria-live="polite" aria-label="AI 상담 대화">
      {messages.map((m, i) => <p key={i} className={"st-msg st-msg-" + m.role}>{m.content}</p>)}
      {busy && <p className="st-msg st-msg-assistant st-typing" aria-label="답변 작성 중"><span /><span /><span /></p>}
      {brief && <div ref={briefRef}><BriefCard brief={brief} /></div>}
      {brief && !submitted && <div className="st-chat-submit"><p>위 내용이 맞으면 연락처를 남겨 주세요. 고칠 부분은 아래에 말씀하셔도 됩니다.</p><InquiryForm compact brief={brief} transcript={messages} onDone={() => setSubmitted(true)} /></div>}
      {submitted && <p className="st-msg st-msg-assistant">접수되었습니다. 담당자가 검토 후 이메일로 연락드릴게요. 감사합니다.</p>}
    </div>
    {messages.length === 1 && <div className="st-starters">{STARTERS.map(s => <button key={s} type="button" disabled={busy || ready === null} onClick={() => void send(s)}>{s}</button>)}</div>}
    {error && <p className="st-error st-chat-error" role="alert">{error}</p>}
    {!submitted && <form className="st-chat-input" onSubmit={e => { e.preventDefault(); void send(input); }}>
      <textarea aria-label="상담 내용 입력" rows={2} maxLength={1500} value={input} disabled={busy} placeholder="예: 쇼핑몰 문의에 답하는 상담사를 만들고 싶어요"
        onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(input); } }} />
      <button className="st-button" disabled={busy || !input.trim()}>보내기</button>
    </form>}
  </div>;
}
