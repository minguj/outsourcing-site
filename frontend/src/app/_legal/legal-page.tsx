import Link from "next/link";
import type { ReactNode } from "react";
import { SITE } from "../site-config";

// 개인정보처리방침·이용약관 공통 틀. 인쇄해도 본문만 깔끔하게 나온다.
export function LegalPage({ title, effective, children }: { title: string; effective: string; children: ReactNode }) {
  return <div className="st-doc-page st-legal-page"><div className="st-wrap">
    <div className="st-contract-bar st-no-print">
      <Link href="/" className="st-logo">{SITE.name}</Link>
      <nav className="st-legal-links" aria-label="정책 문서"><Link href="/privacy">개인정보처리방침</Link><Link href="/terms">이용약관·환불 규정</Link></nav>
    </div>
    <article className="st-doc st-contract st-legal">
      <h1 className="st-contract-title">{title}</h1>
      <p className="st-legal-meta">시행일: {effective}</p>
      {children}
    </article>
  </div></div>;
}

export function Section({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return <section className="st-legal-section"><h2>제{n}조 ({title})</h2>{children}</section>;
}
