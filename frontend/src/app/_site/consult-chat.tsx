"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, briefFields, createDemoQuote, type Brief, type ChatMessage } from "./api";
import { COPY, type Lang } from "./i18n";
import { InquiryForm } from "./inquiry-form";
import { content } from "../site-content";

function BriefCard({ brief, lang }: { brief: Brief; lang: Lang }) {
  const t = COPY[lang].chat;
  return <section className="st-brief" aria-label={t.briefLabel}>
    <span className="st-stamp" aria-hidden="true">{t.stamp}</span>
    <h3>{brief.title || t.briefTitle}</h3>
    <dl>{briefFields(lang).map(([key, label]) => {
      const value = brief[key];
      if (!value || (Array.isArray(value) && value.length === 0)) return null;
      return <div key={key}><dt>{label}</dt><dd>{Array.isArray(value) ? value.join(", ") : value}</dd></div>;
    })}</dl>
  </section>;
}

export function ConsultChat({ onFallback, lang = "ko" }: { onFallback: () => void; lang?: Lang }) {
  const t = COPY[lang].chat;
  const FAQ = content(lang).FAQ;
  const [ready, setReady] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", content: t.greeting }]);
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
      const result = await api<{ reply: string; brief: Brief | null }>("/api/consult/chat", { method: "POST", body: JSON.stringify({ messages: next, lang }) }, lang);
      setMessages([...next, { role: "assistant", content: result.reply }]);
      if (result.brief) setBrief(result.brief);
    } catch (err) {
      const status = (err as { status?: number }).status;
      setError(err instanceof Error ? err.message : t.replyFailed);
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
    try { router.push(await createDemoQuote(brief?.title, lang)); } catch (err) { setError(err instanceof Error ? err.message : t.demoFailed); setBusy(false); }
  }
  const remaining = FAQ.filter(f => f.chip !== false && !asked.includes(f.q));
  const offline = ready === false;

  return <div className="st-chat" aria-busy={busy}>
    <div className="st-chat-head"><strong>{t.head}</strong><span>{brief ? t.done : offline ? t.faqMode : t.live}</span></div>
    <div className="st-chat-log" ref={log} role="log" aria-live="polite" aria-label={t.log}>
      {messages.map((m, i) => <p key={i} className={"st-msg st-msg-" + m.role}>{m.content}</p>)}
      {busy && <p className="st-msg st-msg-assistant st-typing" aria-label={t.typing}><span /><span /><span /></p>}
      {brief && <div ref={briefRef}><BriefCard brief={brief} lang={lang} /></div>}
      {brief && !submitted && <div className="st-chat-submit"><p>{t.confirm}</p><InquiryForm lang={lang} compact brief={brief} transcript={messages} onDone={() => setSubmitted(true)} /></div>}
      {submitted && <p className="st-msg st-msg-assistant">{t.submitted}</p>}
    </div>
    {!submitted && <div className="st-starters" aria-label={t.starters}>
      {remaining.map(f => <button key={f.q} type="button" disabled={busy} onClick={() => answer(f.q, f.a)}>{f.q}</button>)}
      <button type="button" className="st-starter-demo" disabled={busy} onClick={() => void demo()}>{t.demo}</button>
    </div>}
    {error && <p className="st-error st-chat-error" role="alert">{error}</p>}
    {!submitted && (offline
      ? <div className="st-chat-offline-note"><p>{t.offline}</p>
          <button className="st-button" onClick={onFallback}>{t.toForm}</button></div>
      : <form className="st-chat-input" onSubmit={e => { e.preventDefault(); void send(input); }}>
          <textarea aria-label={t.input} rows={2} maxLength={1500} value={input} disabled={busy || ready === null} placeholder={t.placeholder}
            onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(input); } }} />
          <button className="st-button" disabled={busy || !input.trim()}>{t.send}</button>
        </form>)}
  </div>;
}
