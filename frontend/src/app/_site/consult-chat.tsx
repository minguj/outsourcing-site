"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, briefFields, createDemoQuote, type Brief, type ChatMessage } from "./api";
import { COPY, type Lang } from "./i18n";
import { InquiryForm } from "./inquiry-form";
import { track } from "./analytics";
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

/** What the page's bottom inquiry form may attach: the chat so far and its summary. */
export type ChatSession = { messages: ChatMessage[]; brief: Brief | null; submitted: boolean; session?: string };

// 상담창 대화를 서버 기록에서 하나로 묶는 무작위 번호. 같은 탭에서는 새로고침해도 유지된다.
const SESSION_KEY = "consult-session";
function sessionId() {
  try { const kept = window.sessionStorage.getItem(SESSION_KEY); if (kept) return kept; } catch { /* 저장 불가 환경 */ }
  const bytes = new Uint8Array(18); window.crypto.getRandomValues(bytes);
  const id = btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  try { window.sessionStorage.setItem(SESSION_KEY, id); } catch { /* 저장 불가 환경 */ }
  return id;
}

type ChatProps = { onFallback: () => void; lang?: Lang; onChange?: (session: ChatSession) => void; sentElsewhere?: boolean };

// The chat shows plain text; drop Markdown emphasis and heading marks the model may still add.
// 휴대폰에서는 상담 기록지가 작아 위아래로 오가야 하므로, 입력을 시작하면 전체화면으로 띄우고 닫으면 원래 자리로 돌아온다.
const MOBILE = "(max-width: 960px)";
const isMobile = () => typeof window !== "undefined" && window.matchMedia(MOBILE).matches;

function useFullScreen() {
  const [full, setFull] = useState(false);
  const [box, setBox] = useState<{ top: number; height: number } | null>(null);
  const savedY = useRef(0);
  const pushed = useRef(false);
  const isOpen = useRef(false);
  const open = useCallback(() => {
    if (!isMobile() || isOpen.current) return;
    isOpen.current = true;
    savedY.current = window.scrollY;
    // 휴대폰의 뒤로 가기 버튼으로도 닫히도록 기록을 하나 남긴다.
    window.history.pushState({ stChat: true }, "");
    pushed.current = true;
    setFull(true);
  }, []);
  const close = useCallback(() => {
    if (pushed.current) { window.history.back(); return; }
    isOpen.current = false;
    setFull(false);
  }, []);
  useEffect(() => {
    const onPop = () => { if (pushed.current) { pushed.current = false; isOpen.current = false; setFull(false); } };
    window.addEventListener("popstate", onPop);
    window.addEventListener("st-open-chat", open);
    return () => { window.removeEventListener("popstate", onPop); window.removeEventListener("st-open-chat", open); };
  }, [open]);
  useEffect(() => {
    if (!full) return;
    const root = document.documentElement;
    root.classList.add("st-chat-open");
    // 키보드가 올라오면 보이는 영역에 맞춰 높이를 줄여 입력칸이 가려지지 않게 한다.
    const vv = window.visualViewport;
    const fit = () => setBox(vv ? { top: vv.offsetTop, height: vv.height } : null);
    fit();
    vv?.addEventListener("resize", fit); vv?.addEventListener("scroll", fit);
    return () => {
      vv?.removeEventListener("resize", fit); vv?.removeEventListener("scroll", fit);
      root.classList.remove("st-chat-open");
      setBox(null);
      const y = savedY.current;
      requestAnimationFrame(() => window.scrollTo(0, y));
    };
  }, [full]);
  // 화면을 돌리거나 넓혀 데스크톱 폭이 되면 원래 배치로 돌아간다.
  useEffect(() => {
    if (!full) return;
    const mq = window.matchMedia(MOBILE);
    const onChange = () => { if (!mq.matches) close(); };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [full, close]);
  return { full, box, open, close };
}

const plain = (text: string) => text.replace(/\*\*(.+?)\*\*/g, "$1").replace(/__(.+?)__/g, "$1").replace(/^#{1,6}\s+/gm, "");

export function ConsultChat({ onFallback, lang = "ko", onChange, sentElsewhere = false }: ChatProps) {
  const t = COPY[lang].chat;
  const FAQ = content(lang).FAQ;
  const [ready, setReady] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", content: t.greeting }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [sentHere, setSentHere] = useState(false);
  const submitted = sentHere || sentElsewhere;
  const [asked, setAsked] = useState<string[]>([]);
  const log = useRef<HTMLDivElement>(null);
  const { full, box, open, close } = useFullScreen();
  const session = useRef("");

  useEffect(() => {
    api<{ consult_ready: boolean }>("/api/site/config").then(c => setReady(c.consult_ready)).catch(() => setReady(false));
  }, []);
  useEffect(() => { onChange?.({ messages, brief, submitted: sentHere, session: session.current || undefined }); }, [messages, brief, sentHere, onChange]);
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
    if (!messages.some(m => m.role === "user")) track("consult_start", { lang });
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next); setInput(""); setBusy(true); setError("");
    try {
      const result = await api<{ reply: string; brief: Brief | null }>("/api/consult/chat", { method: "POST", body: JSON.stringify({ messages: next, lang, session: (session.current ||= sessionId()) }) }, lang);
      setMessages([...next, { role: "assistant", content: result.reply }]);
      if (result.brief) { if (!brief) track("consult_brief", { lang, project_type: result.brief.project_type || "" }); setBrief(result.brief); }
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
    open();
    track("faq_click", { question: q });
    setMessages([...messages, { role: "user", content: q }, { role: "assistant", content: a }]);
    setAsked([...asked, q]);
  }
  async function demo() {
    track("demo_quote_start", { from: "chat" });
    setBusy(true); setError("");
    // 견적서 화면은 새로 불러와 방문 분석 스크립트가 따라가지 않게 한다(주소에 토큰이 있다).
    try { window.location.assign(await createDemoQuote(brief?.title, lang)); } catch (err) { setError(err instanceof Error ? err.message : t.demoFailed); setBusy(false); }
  }
  const remaining = FAQ.filter(f => f.chip !== false && !asked.includes(f.q));
  const offline = ready === false;

  return <div className={"st-chat" + (full ? " is-full" : "")} aria-busy={busy} role={full ? "dialog" : undefined} aria-modal={full || undefined} aria-label={full ? t.head : undefined}
    style={full && box ? { top: box.top, height: box.height } : undefined}>
    <div className="st-chat-head"><strong>{t.head}</strong>
      <div className="st-chat-head-side"><span>{brief ? t.done : offline ? t.faqMode : t.live}</span>
        {full
          ? <button type="button" className="st-chat-toggle" onClick={close}>{t.close}</button>
          : <button type="button" className="st-chat-toggle st-chat-expand" onClick={open}>{t.expand}</button>}
      </div></div>
    <div className="st-chat-log" ref={log} role="log" aria-live="polite" aria-label={t.log}>
      {messages.map((m, i) => <p key={i} className={"st-msg st-msg-" + m.role}>{m.role === "assistant" ? plain(m.content) : m.content}</p>)}
      {busy && <p className="st-msg st-msg-assistant st-typing" aria-label={t.typing}><span /><span /><span /></p>}
      {brief && <div ref={briefRef}><BriefCard brief={brief} lang={lang} /></div>}
      {brief && !submitted && <div className="st-chat-submit"><p>{t.confirm}</p><InquiryForm lang={lang} compact brief={brief} transcript={messages} session={session.current || undefined} onDone={() => setSentHere(true)} /></div>}
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
            onFocus={open}
            onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(input); } }} />
          <button className="st-button" disabled={busy || !input.trim()}>{t.send}</button>
        </form>)}
    {!submitted && !offline && <p className="st-chat-notice">{t.aiNotice}</p>}
  </div>;
}
