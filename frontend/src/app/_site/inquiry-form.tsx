"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, createDemoQuote, type Brief, type ChatMessage } from "./api";
import { SITE } from "../site-config";

type Props = { brief?: Brief | null; transcript?: ChatMessage[]; compact?: boolean; onDone?: () => void };

const ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.hwp,.hwpx,.txt,.md,.png,.jpg,.jpeg,.zip";
const MAX_FILES = 3;
const MAX_BYTES = 10 * 1024 * 1024;
const mb = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)}MB`;

export function PrivacyNotice() {
  return <details className="st-privacy"><summary>개인정보 수집·이용 안내 보기</summary>
    <dl><dt>수집 항목</dt><dd>{SITE.privacy.items}</dd><dt>이용 목적</dt><dd>{SITE.privacy.purpose}</dd><dt>보유 기간</dt><dd>{SITE.privacy.retention}</dd></dl>
    <p>동의하지 않으셔도 되지만, 이 경우 상담 접수가 어렵습니다.</p>
  </details>;
}

export function InquiryForm({ brief, transcript = [], compact = false, onDone }: Props) {
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
      data.append("payload", JSON.stringify({ ...form, brief: brief ?? null, transcript, consent }));
      files.forEach(file => data.append("files", file, file.name));
      const result = await api<{ ok: boolean; id?: number }>("/api/inquiries", { method: "POST", body: data });
      setDone(result.id ?? 0); onDone?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "접수하지 못했습니다.");
    } finally { setBusy(false); }
  }

  function addFiles(list: FileList | null) {
    if (!list) return;
    const next = [...files];
    for (const file of Array.from(list)) {
      const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
      if (!ACCEPT.split(",").includes(ext)) { setError(`'${file.name}'은(는) 올릴 수 없는 형식입니다.`); continue; }
      if (file.size > MAX_BYTES) { setError(`'${file.name}' 파일이 10MB를 넘습니다.`); continue; }
      if (next.length >= MAX_FILES) { setError(`첨부 파일은 ${MAX_FILES}개까지 올릴 수 있습니다.`); break; }
      if (!next.some(f => f.name === file.name && f.size === file.size)) next.push(file);
    }
    setFiles(next);
  }

  if (done !== null) {
    return <div className="st-received" role="status">
      <span className="st-stamp st-stamp-static" aria-hidden="true">접수</span>
      <div><strong>상담이 접수되었습니다.</strong><p>남겨 주신 이메일로 접수 확인 메일을 보냈어요. 담당자가 검토한 뒤 견적서 링크를 메일로 보내 드립니다.</p>
        <button type="button" className="st-text-link" onClick={() => void createDemoQuote(brief?.title).then(path => router.push(path)).catch(() => undefined)}>견적서와 착수금 결제가 어떻게 진행되는지 미리 보기</button></div>
    </div>;
  }

  return <form className={"st-form" + (compact ? " st-form-compact" : "")} onSubmit={submit}>
    <div className="st-form-grid">
      <label>이름<input required maxLength={40} autoComplete="name" value={form.name} onChange={set("name")} /></label>
      <label>회사명<input maxLength={80} autoComplete="organization" value={form.company} onChange={set("company")} /></label>
      <label>이메일<input required type="email" maxLength={254} autoComplete="email" value={form.email} onChange={set("email")} /></label>
      <label>전화번호 (선택)<input type="tel" maxLength={30} autoComplete="tel" value={form.phone} onChange={set("phone")} /></label>
    </div>
    {(needsMessage || !compact) && <label className="st-form-wide">{needsMessage ? "어떤 일을 맡기고 싶으세요?" : "덧붙일 내용 (선택)"}
      <textarea required={needsMessage} minLength={needsMessage ? 5 : 0} maxLength={3000} rows={needsMessage ? 6 : 3} value={form.message} onChange={set("message")}
        placeholder={needsMessage ? "예: 거래처 다섯 곳이 각자 다른 엑셀로 발주서를 보내는데, 매일 우리 양식으로 옮겨 적고 있어요. 예산은 1천만 원 안팎, 다음 달 안에 쓰고 싶어요." : ""} /></label>}
    <div className="st-files">
      <span className="st-files-label">기획서·참고 자료 첨부 (선택)</span>
      <label className="st-file-pick">
        <input type="file" multiple accept={ACCEPT} disabled={busy || files.length >= MAX_FILES} onChange={e => { setError(""); addFiles(e.target.files); e.target.value = ""; }} />
        <span>{files.length >= MAX_FILES ? "최대 개수를 첨부했습니다" : "파일 선택"}</span>
      </label>
      <small>PDF, 워드, 파워포인트, 엑셀, 한글, 이미지, ZIP · 파일당 10MB, 최대 {MAX_FILES}개. 개인정보가 담긴 자료는 빼고 보내 주세요.</small>
      {files.length > 0 && <ul className="st-file-list">{files.map((file, i) => <li key={file.name + file.size}>
        <span>{file.name}</span><small>{mb(file.size)}</small>
        <button type="button" disabled={busy} aria-label={`${file.name} 첨부 취소`} onClick={() => setFiles(files.filter((_, j) => j !== i))}>삭제</button>
      </li>)}</ul>}
    </div>
    <input className="st-honeypot" tabIndex={-1} autoComplete="off" aria-hidden="true" value={form.website} onChange={set("website")} />
    <label className="st-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} required /> 개인정보 수집·이용에 동의합니다.</label>
    <PrivacyNotice />
    {error && <p className="st-error" role="alert">{error}</p>}
    <button className="st-button" disabled={busy || !consent}>{busy ? "접수하는 중" : brief ? "이 내용으로 상담 접수" : "상담 접수"}</button>
  </form>;
}
