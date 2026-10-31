"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, createDemoQuote, type Brief, type ChatMessage } from "./api";
import { COPY, type Lang } from "./i18n";
import { siteFor } from "../site-config";

type Props = { brief?: Brief | null; transcript?: ChatMessage[]; compact?: boolean; onDone?: () => void; lang?: Lang };

const ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.hwp,.hwpx,.txt,.md,.png,.jpg,.jpeg,.zip";
const MAX_FILES = 3;
const MAX_BYTES = 10 * 1024 * 1024;
const mb = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)}MB`;

export function PrivacyNotice({ lang = "ko" }: { lang?: Lang }) {
  const t = COPY[lang].form;
  const { privacy } = siteFor(lang);
  return <details className="st-privacy"><summary>{t.privacy}</summary>
    <dl><dt>{t.items}</dt><dd>{privacy.items}</dd><dt>{t.purpose}</dt><dd>{privacy.purpose}</dd><dt>{t.retention}</dt><dd>{privacy.retention}</dd></dl>
    <p>{t.privacyNote}</p>
  </details>;
}

export function InquiryForm({ brief, transcript = [], compact = false, onDone, lang = "ko" }: Props) {
  const t = COPY[lang].form;
  const [form, setForm] = useState({ name: "", company: "", email: "", phone: "", message: "", website: "" });
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<number | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const router = useRouter();
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [key]: e.target.value });
  const needsMessage = !brief;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const data = new FormData();
      data.append("payload", JSON.stringify({ ...form, brief: brief ?? null, transcript, consent, lang }));
      files.forEach(file => data.append("files", file, file.name));
      const result = await api<{ ok: boolean; id?: number }>("/api/inquiries", { method: "POST", body: data }, lang);
      setDone(result.id ?? 0); onDone?.();
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
    <label className="st-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} required /> {t.consent}</label>
    <PrivacyNotice lang={lang} />
    {error && <p className="st-error" role="alert">{error}</p>}
    <button className="st-button" disabled={busy || !consent}>{busy ? t.busy : brief ? t.submitBrief : t.submit}</button>
  </form>;
}
