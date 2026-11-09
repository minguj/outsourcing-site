"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../_site/api";
import { money } from "../_site/i18n";
import { CONTRACTOR, SITE } from "../site-config";

// 계약 문서 4종이 함께 쓰는 부분: 견적 불러오기, 상단 버튼(인쇄·PDF, Word), 문서 목록, 서명란.
// 견적서 링크의 토큰(?t=…)이 있으면 고객사·과업명·금액을 채우고, 없으면 빈칸 양식으로 보여 준다.
export type Quote = {
  title: string; items: { name: string; amount: number }[]; total: number; deposit: number; schedule: string; note: string;
  created_at: number; customer: { name: string; company: string }; is_demo: boolean;
};

export const won = (value: number) => money("ko", value);
export const day = (seconds: number) => new Intl.DateTimeFormat("ko-KR", { dateStyle: "long" }).format(new Date(seconds * 1000));
export const BLANK = "　　　　　　　　　　";

/** 중도금은 합계의 50%, 잔금은 나머지(착수금은 견적에 적은 금액). */
export const payments = (quote: Quote) => {
  const middle = Math.round(quote.total * 0.5);
  return { deposit: quote.deposit, middle, balance: Math.max(quote.total - quote.deposit - middle, 0) };
};

// 유지보수 계약서(/contract/maintenance)는 공개 경로에서 숨기려고 목록에서 뺐다. 관리자 화면의 문서 바로가기로만 연다.
export const DOCS = [
  { href: "/contract", label: "도입 계약서(안)" },
  { href: "/contract/nda", label: "비밀유지계약서" },
  { href: "/contract/completion", label: "완료 확인서" },
];

export function useQuote(required: boolean) {
  const [token, setToken] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("t") ?? "";
    setToken(t);
    if (!t) {
      if (required) setError("계약서 링크가 올바르지 않습니다. 받은 링크를 다시 확인해 주세요.");
      setReady(!required);
      return;
    }
    api<Quote>(`/api/quotes/${t}`, undefined, "ko").then(q => { setQuote(q); setReady(true); })
      .catch(err => setError(err instanceof Error ? err.message : "문서를 불러오지 못했습니다."));
  }, [required]);
  return { token, quote, error, ready };
}

const WORD_STYLE = `body{font-family:'Malgun Gothic','맑은 고딕',sans-serif;font-size:11pt;line-height:1.6;color:#111}
h1{text-align:center;font-size:18pt;margin:0 0 14pt}h2{font-size:12pt;margin:12pt 0 3pt}h3{font-size:12pt;margin:10pt 0 4pt}
table{border-collapse:collapse;width:100%;margin:6pt 0}th,td{border:1px solid #888;padding:4pt 6pt;text-align:left;vertical-align:top}
ol,ul{margin:4pt 0 4pt 18pt;padding:0}dl{margin:0}dt{font-weight:bold;margin-top:4pt}dd{margin:0 0 4pt 0}
.st-num{text-align:right}a{color:#111;text-decoration:none}`;

/** Word가 여는 HTML 문서(.doc)로 저장한다. 내용은 화면에 보이는 문서 그대로다. */
function saveWord(article: HTMLElement, title: string) {
  const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="utf-8"><title>${title}</title><style>${WORD_STYLE}</style></head><body>${article.innerHTML}</body></html>`;
  const url = URL.createObjectURL(new Blob(["﻿", html], { type: "application/msword" }));
  const link = document.createElement("a");
  link.href = url; link.download = `${title}.doc`;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DocShell({ title, token, notice, children }: { title: string; token: string; notice: ReactNode; children: ReactNode }) {
  const article = useRef<HTMLElement>(null);
  const path = usePathname();
  const q = token ? `?t=${encodeURIComponent(token)}` : "";
  return <div className="st-doc-page st-contract-page"><div className="st-wrap">
    <div className="st-contract-bar st-no-print">
      <Link href="/" className="st-logo">{SITE.name}</Link>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {token && <Link href={`/quote${q}`} className="st-button st-button-ghost">견적서로 돌아가기</Link>}
        <button type="button" className="st-button st-button-ghost" onClick={() => article.current && saveWord(article.current, title)}>Word로 저장</button>
        <button type="button" className="st-button" onClick={() => window.print()}>인쇄 · PDF 저장</button>
      </div>
    </div>
    <nav className="st-doc-tabs st-no-print" aria-label="계약 문서">
      {DOCS.map(d => <Link key={d.href} href={`${d.href}${q}`} aria-current={path === d.href ? "page" : undefined}>{d.label}</Link>)}
    </nav>
    <p className="st-contract-draft st-no-print">{notice}</p>
    <article ref={article} className="st-doc st-contract" aria-label={title}>{children}</article>
  </div></div>;
}

export function Loading({ error }: { error: string }) {
  return <div className="st-doc-page"><div className="st-wrap">
    <p style={{ marginBottom: 16 }}><Link href="/" className="st-logo">{SITE.name}</Link></p>
    {error ? <p className="st-error" role="alert">{error}</p> : <p>문서를 불러오는 중입니다.</p>}
  </div></div>;
}

export function Articles({ items }: { items: [string, ReactNode][] }) {
  return <ol className="st-contract-articles">{items.map(([title, body], i) => <li key={title}><h2>제{i + 1}조 ({title})</h2><div>{body}</div></li>)}</ol>;
}

export function Signs({ quote, clientRole = "대표자" }: { quote: Quote | null; clientRole?: string }) {
  return <>
    <p className="st-contract-date">{BLANK}년　　월　　일</p>
    <div className="st-contract-signs">
      <section><h3>갑</h3><dl><dt>상호</dt><dd>{quote?.customer.company || BLANK}</dd><dt>주소</dt><dd>{BLANK}</dd><dt>{clientRole}</dt><dd>{BLANK}　(서명 또는 인)</dd></dl></section>
      <section><h3>을</h3><dl><dt>성명</dt><dd>{BLANK}　(서명 또는 인)</dd><dt>주소</dt><dd>{BLANK}</dd><dt>서비스명</dt><dd>{CONTRACTOR.brand}</dd></dl></section>
    </div>
  </>;
}

/** 갑(고객)과 을(운영자)을 처음 소개하는 문장. */
export function Parties({ quote, tail }: { quote: Quote | null; tail: string }) {
  const client = quote ? (quote.customer.company || quote.customer.name) : BLANK;
  return <p className="st-contract-intro"><strong>{client}</strong>(이하 &ldquo;갑&rdquo;)와 <strong>{CONTRACTOR.brand}</strong>(이하 &ldquo;을&rdquo;)은 {tail}</p>;
}
