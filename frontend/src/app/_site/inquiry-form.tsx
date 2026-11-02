"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { api, createDemoQuote, type Brief, type ChatMessage } from "./api";
import type { ChatSession } from "./consult-chat";
import { COPY, type Lang } from "./i18n";
import { siteFor } from "../site-config";

type Props = { brief?: Brief | null; transcript?: ChatMessage[]; compact?: boolean; onDone?: (includedChat: boolean) => void; lang?: Lang;
  /** Bottom form only: the AI chat on the same page, offered as an attachment to this inquiry. */
  chat?: ChatSession | null };

const ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.hwp,.hwpx,.txt,.md,.png,.jpg,.jpeg,.zip";
const MAX_FILES = 3;
const MAX_BYTES = 10 * 1024 * 1024;
const mb = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)}MB`;

/** The full collection-and-use notice, opened from the consent label so it can be read before agreeing. */
export function PrivacyDialog({ lang = "ko", open, onClose, onAgree }: { lang?: Lang; open: boolean; onClose: () => void; onAgree: () => void }) {
  const t = COPY[lang].form;
  const { privacy } = siteFor(lang);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return <dialog ref={ref} className="st-privacy-dialog" aria-labelledby="st-privacy-title" onClose={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="st-privacy-body">
      <h3 id="st-privacy-title">{t.privacy}</h3>
      <dl><dt>{t.items}</dt><dd>{privacy.items}</dd><dt>{t.purpose}</dt><dd>{privacy.purpose}</dd><dt>{t.retention}</dt><dd>{privacy.retention}</dd><dt>{t.transfer}</dt><dd>{privacy.transfer}</dd></dl>
      <p>{t.privacyNote} <a href="/privacy" target="_blank" rel="noreferrer">{COPY[lang].legal.full}</a></p>
      <div className="st-privacy-actions">
        <button type="button" className="st-button st-button-ghost" onClick={onClose}>{t.close}</button>
        <button type="button" className="st-button" onClick={onAgree}>{t.agreeClose}</button>
      </div>
    </div>
  </dialog>;
}

export function InquiryForm({ brief: givenBrief, transcript: givenTranscript = [], compact = false, onDone, lang = "ko", chat }: Props) {
  const t = COPY[lang].form;
  const [form, setForm] = useState({ name: "", company: "", email: "", phone: "", message: "", website: "" });
  const [consent, setConsent] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const consentId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<number | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const router = useRouter();
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [key]: e.target.value });
  // A visitor who talked to the AI and then used this form keeps that conversation with the inquiry.
  const [attachChat, setAttachChat] = useState(true);
  const chatUsed = !!chat && !chat.submitted && (!!chat.brief || chat.messages.some(m => m.role === "user"));
  const useChat = chatUsed && attachChat;
  const brief = useChat ? chat.brief : givenBrief;
  const transcript = useChat ? chat.messages : givenTranscript;
  const needsMessage = !brief;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const data = new FormData();
      data.append("payload", JSON.stringify({ ...form, brief: brief ?? null, transcript, consent, lang }));
      files.forEach(file => data.append("files", file, file.name));
      const result = await api<{ ok: boolean; id?: number }>("/api/inquiries", { method: "POST", body: data }, lang);
      setDone(result.id ?? 0); onDone?.(useChat);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.failed);
    } finally { setBusy(false); }
  }

  function addFiles(list: FileList | null) {
    if (!list) return;
    const next = [...files];
    for (const file of Array.from(list)) {
      const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
      if (!ACCEPT.split(",").includes(ext)) { setError(t.badType(file.name)); continue; }
      if (file.size > MAX_BYTES) { setError(t.tooBig(file.name)); continue; }
      if (next.length >= MAX_FILES) { setError(t.tooMany(MAX_FILES)); break; }
      if (!next.some(f => f.name === file.name && f.size === file.size)) next.push(file);
    }
    setFiles(next);
  }

  if (done !== null) {
    return <div className="st-received" role="status">
      <span className="st-stamp st-stamp-static" aria-hidden="true">{t.receivedStamp}</span>
      <div><strong>{t.received}</strong><p>{t.receivedText}</p>
        <button type="button" className="st-text-link" onClick={() => void createDemoQuote(brief?.title, lang).then(path => router.push(path)).catch(() => undefined)}>{t.preview}</button></div>
    </div>;
  }

  return <form className={"st-form" + (compact ? " st-form-compact" : "")} onSubmit={submit}>
    <div className="st-form-grid">
      <label>{t.name}<input required maxLength={40} autoComplete="name" value={form.name} onChange={set("name")} /></label>
      <label>{t.company}<input maxLength={80} autoComplete="organization" value={form.company} onChange={set("company")} /></label>
      <label>{t.email}<input required type="email" maxLength={254} autoComplete="email" value={form.email} onChange={set("email")} /></label>
      <label>{t.phone}<input type="tel" maxLength={30} autoComplete="tel" value={form.phone} onChange={set("phone")} /></label>
    </div>
    {chatUsed && <label className="st-attach-chat">
      <input type="checkbox" checked={attachChat} onChange={e => setAttachChat(e.target.checked)} />
      <span><strong>{t.attachChat}</strong><small>{chat.brief ? t.attachBrief(chat.brief.title || t.attachUntitled) : t.attachTalk(chat.messages.filter(m => m.role === "user").length)}</small></span>
    </label>}
    {(needsMessage || !compact) && <label className="st-form-wide">{needsMessage ? t.message : t.extra}
      <textarea required={needsMessage} minLength={needsMessage ? 5 : 0} maxLength={3000} rows={needsMessage ? 6 : 3} value={form.message} onChange={set("message")}
        placeholder={needsMessage ? t.placeholder : ""} /></label>}
    <div className="st-files">
      <span className="st-files-label">{t.files}</span>
      <label className="st-file-pick">
        <input type="file" multiple accept={ACCEPT} disabled={busy || files.length >= MAX_FILES} onChange={e => { setError(""); addFiles(e.target.files); e.target.value = ""; }} />
        <span>{files.length >= MAX_FILES ? t.full : t.pick}</span>
      </label>
      <small>{t.filesHelp(MAX_FILES)}</small>
      {files.length > 0 && <ul className="st-file-list">{files.map((file, i) => <li key={file.name + file.size}>
        <span>{file.name}</span><small>{mb(file.size)}</small>
        <button type="button" disabled={busy} aria-label={t.removeLabel(file.name)} onClick={() => setFiles(files.filter((_, j) => j !== i))}>{t.remove}</button>
      </li>)}</ul>}
    </div>
    <input className="st-honeypot" tabIndex={-1} autoComplete="off" aria-hidden="true" value={form.website} onChange={set("website")} />
    <div className="st-consent-row">
      <input id={consentId} type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} required />
      <label htmlFor={consentId}>{t.consent[0]}<button type="button" className="st-consent-link" onClick={e => { e.preventDefault(); setShowPrivacy(true); }}>{t.consent[1]}</button>{t.consent[2]}</label>
    </div>
    <PrivacyDialog lang={lang} open={showPrivacy} onClose={() => setShowPrivacy(false)} onAgree={() => { setConsent(true); setShowPrivacy(false); }} />
    {error && <p className="st-error" role="alert">{error}</p>}
    <button className="st-button" disabled={busy || !consent}>{busy ? t.busy : brief ? t.submitBrief : t.submit}</button>
  </form>;
}
