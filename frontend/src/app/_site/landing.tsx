"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { track } from "./analytics";
import { createDemoQuote } from "./api";
import { ConsultChat, type ChatSession } from "./consult-chat";
import { COPY, HOME, type Lang } from "./i18n";
import { InquiryForm } from "./inquiry-form";
import { CONTACT, siteFor } from "../site-config";
import { content, type FlowAction } from "../site-content";

export default function Landing({ lang = "ko" }: { lang?: Lang }) {
  const [chat, setChat] = useState<ChatSession | null>(null);
  const [sentBelow, setSentBelow] = useState(false);
  const onChat = useCallback((session: ChatSession) => setChat(session), []);
  const t = COPY[lang];
  const site = siteFor(lang);
  const { FLOW, STACK, FAQ } = content(lang);
  // One root layout serves both languages; keep <html lang> right for screen readers and translation tools.
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  // 버튼 위치(where)를 함께 기록해 어느 버튼으로 상담·접수에 들어오는지 본다.
  const goInquiry = (where = "other") => { track("cta_click", { target: "inquiry", where }); document.getElementById("inquiry")?.scrollIntoView({ behavior: "smooth", block: "start" }); };
  // 휴대폰에서는 상담 기록지를 전체화면으로 연다(consult-chat.tsx가 이 이벤트를 받는다).
  const goChat = (where = "other") => {
    track("cta_click", { target: "chat", where });
    if (window.matchMedia("(max-width: 960px)").matches) window.dispatchEvent(new Event("st-open-chat"));
    else document.getElementById("consult")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const goFlow = () => { track("cta_click", { target: "flow", where: "hero" }); document.getElementById("flow")?.scrollIntoView({ behavior: "smooth", block: "start" }); };
  // 동작 흐름의 견적서·계약·결제 단계는 체험용 견적서(청구 없음)를 만들어 연다.
  // 계약서(안)는 견적 토큰이 있어야 열리므로 같은 토큰으로 /contract 를 연다. 견적서·계약서 화면은 새로 불러와 방문 분석이 따라가지 않는다.
  const [flowBusy, setFlowBusy] = useState(false);
  const [flowError, setFlowError] = useState("");
  // 체험 견적서로 이동한 뒤 브라우저 뒤로 가기로 돌아오면 페이지가 이동 직전 상태(진행 중)로 복원된다(bfcache). 그때 버튼을 다시 켠다.
  useEffect(() => {
    const restore = (e: PageTransitionEvent) => { if (e.persisted) setFlowBusy(false); };
    window.addEventListener("pageshow", restore);
    return () => window.removeEventListener("pageshow", restore);
  }, []);
  async function openDemo(kind: "quote" | "contract") {
    track("demo_quote_start", { from: kind === "contract" ? "flow_contract" : "flow" });
    setFlowBusy(true); setFlowError("");
    try {
      const path = await createDemoQuote(undefined, lang);
      window.location.assign(kind === "contract" ? path.replace(/^\/quote/, "/contract") : path);
    } catch (err) { setFlowError(err instanceof Error ? err.message : t.flow.failed); setFlowBusy(false); }
  }
  const runFlow = (action: FlowAction) => {
    if (action === "chat") goChat("flow");
    else if (action === "inquiry") goInquiry("flow");
    else void openDemo(action);
  };

  return <div className={"st-page" + (lang === "en" ? " st-lang-en" : "")}>
    <header className="st-nav"><div className="st-wrap">
      <Link href={HOME[lang]} className="st-logo">{site.name}</Link>
      <nav aria-label={t.nav.label}><a href="#flow">{t.nav.flow}</a><a href="#examples">{t.nav.examples}</a><a href="#stack">{t.nav.stack}</a><a href="#faq">{t.nav.faq}</a><a href="#inquiry" className="st-nav-cta">{t.nav.inquiry}</a>
        {/* 영문 사이트는 보류 중이라 한국어 페이지에는 전환 버튼을 숨긴다. 다시 열 때 lang 조건을 지운다. */}
        {lang === "en" && <Link href={t.nav.switchHref} className="st-lang-switch" hrefLang={t.nav.switchLang} lang={t.nav.switchLang}>{t.nav.switchTo}</Link>}</nav>
    </div></header>

    <main>
      <section className="st-hero"><div className="st-wrap st-hero-grid">
        <div className="st-hero-copy">
          <p className="st-hero-kicker">{site.tagline}</p>
          <h1>{t.hero.title}</h1>
          <p className="st-lead">{t.hero.lead}</p>
          <div className="st-hero-actions">
            <button className="st-button" onClick={() => goChat("hero")}>{t.hero.chat}</button>
            <button className="st-button st-button-ghost" onClick={goFlow}>{t.hero.flow}</button>
          </div>
        </div>
        <div id="consult"><ConsultChat lang={lang} onFallback={() => goInquiry("chat_offline")} onChange={onChat} sentElsewhere={sentBelow} /></div>
      </div></section>

      <section id="flow" className="st-section"><div className="st-wrap">
        <h2>{t.flow.title}</h2>
        <p className="st-section-lead">{t.flow.lead}</p>
        <ol className="st-steps st-flow">{FLOW.map((s, i) => <li key={s.title}>
          <span className="st-step-no" aria-hidden="true">{i + 1}</span><h3>{s.title}</h3><p>{s.text}</p>
          <button type="button" className="st-text-link" disabled={flowBusy} onClick={() => runFlow(s.action)}>{s.cta}</button>
        </li>)}</ol>
        {flowBusy && <p className="st-flow-status" role="status">{t.flow.busy}</p>}
        {flowError && <p className="st-error" role="alert">{flowError}</p>}
      </div></section>

      <section id="examples" className="st-section st-examples-section"><div className="st-wrap">
        <h2>{t.examples.title}</h2>
        <p className="st-section-lead">{t.examples.lead}</p>
        <div className="st-examples">
          <article className="st-example">
            <ul className="st-tags">{t.examples.tags.chat.map(tag => <li key={tag}>{tag}</li>)}</ul>
            <h3>{t.examples.chat[0]}</h3>
            <p>{t.examples.chat[1]}</p>
            <button className="st-text-link" onClick={() => goChat("examples")}>{t.examples.chat[2]}</button>
          </article>
          <article className="st-example">
            <ul className="st-tags">{t.examples.tags.tower.map(tag => <li key={tag}>{tag}</li>)}</ul>
            <h3>{t.examples.tower[0]}</h3>
            <p>{t.examples.tower[1]}</p>
            <Link className="st-text-link" href="/demo/tower" onClick={() => track("demo_open", { demo: "tower" })}>{t.examples.tower[2]}</Link>
          </article>
          <article className="st-example">
            <ul className="st-tags">{t.examples.tags.zeb.map(tag => <li key={tag}>{tag}</li>)}</ul>
            <h3>{t.examples.zeb[0]}</h3>
            <p>{t.examples.zeb[1]}</p>
            <Link className="st-text-link" href="/demo/zeb" onClick={() => track("demo_open", { demo: "zeb" })}>{t.examples.zeb[2]}</Link>
          </article>
          <article className="st-example st-example-wide">
            <div>
              <ul className="st-tags">{t.examples.tags.spend.map(tag => <li key={tag}>{tag}</li>)}</ul>
              <h3>{t.examples.spend[0]}</h3>
              <p>{t.examples.spend[1]}</p>
              <Link className="st-text-link" href="/demo/spend" onClick={() => track("demo_open", { demo: "spend" })}>{t.examples.spend[2]}</Link>
            </div>
            <Link href="/demo/spend" className="st-example-thumbs" aria-label={t.examples.spend[2]} onClick={() => track("demo_open", { demo: "spend" })}>
              {(["summary", "detail", "upcoming"] as const).map((id, i) => <Image key={id} src={`/samples/spend/thumbnails/${id}.png`} alt={t.examples.spendAlt[i]} width={960} height={700} unoptimized />)}
            </Link>
          </article>
          <article className="st-example st-example-wide">
            <div>
              <ul className="st-tags">{t.examples.tags.pms.map(tag => <li key={tag}>{tag}</li>)}</ul>
              <h3>{t.examples.pms[0]}</h3>
              <p>{t.examples.pms[1]}</p>
              <Link className="st-text-link" href="/demo/pms" onClick={() => track("demo_open", { demo: "pms" })}>{t.examples.pms[2]}</Link>
            </div>
            <Link href="/demo/pms" className="st-example-thumbs" aria-label={t.examples.pms[2]} onClick={() => track("demo_open", { demo: "pms" })}>
              {(["roles", "voc", "billing"] as const).map((id, i) => <Image key={id} src={`/samples/pms/thumbnails/${id}.png`} alt={t.examples.pmsAlt[i]} width={960} height={700} unoptimized />)}
            </Link>
          </article>
          <article className="st-example st-example-wide">
            <div>
              <ul className="st-tags">{t.examples.tags.nurse.map(tag => <li key={tag}>{tag}</li>)}</ul>
              <h3>{t.examples.nurse[0]}</h3>
              <p>{t.examples.nurse[1]}</p>
              <Link className="st-text-link" href="/demo/nurse" onClick={() => track("demo_open", { demo: "nurse" })}>{t.examples.nurse[2]}</Link>
            </div>
            <Link href="/demo/nurse" className="st-example-thumbs" aria-label={t.examples.nurse[2]} onClick={() => track("demo_open", { demo: "nurse" })}>
              {(["home", "mobile", "admin"] as const).map((id, i) => <Image key={id} src={`/samples/nurse/thumbnails/${id}.png`} alt={t.examples.nurseAlt[i]} width={[960, 390, 960][i]} height={[700, 700, 700][i]} unoptimized />)}
            </Link>
          </article>
          <article className="st-example st-example-wide">
            <div>
              <ul className="st-tags">{t.examples.tags.po.map(tag => <li key={tag}>{tag}</li>)}</ul>
              <h3>{t.examples.po[0]}</h3>
              <p>{t.examples.po[1]}</p>
              {t.examples.poNote && <p className="st-example-note">{t.examples.poNote}</p>}
              <Link className="st-text-link" href="/demo/purchase-orders">{t.examples.po[2]}</Link>
            </div>
            <Link href="/demo/purchase-orders" className="st-example-thumbs" aria-label={t.examples.po[2]}>
              {(["A", "B", "C"] as const).map((id, i) => <Image key={id} src={`/samples/purchase-orders/thumbnails/${id}.png`} alt={t.examples.poAlt(id)} width={[850, 2470, 1270][i]} height={[1180, 660, 1140][i]} unoptimized />)}
            </Link>
          </article>
        </div>
      </div></section>

      <section id="stack" className="st-section"><div className="st-wrap">
        <h2>{t.stack.title}</h2>
        <p className="st-section-lead">{t.stack.lead}</p>
        <ol className="st-stack-diagram" aria-label={t.stack.diagramLabel}>{t.stack.diagram.map(node => <li key={node}>{node}</li>)}</ol>
        <table className="st-table st-stack">
          <thead><tr>{t.stack.cols.map(c => <th key={c} scope="col">{c}</th>)}</tr></thead>
          <tbody>{STACK.map(s => <tr key={s.layer}><th scope="row">{s.layer}</th><td className="st-stack-tech">{s.tech}</td><td>{s.text}</td></tr>)}</tbody>
        </table>
        <ul className="st-stack-notes">{t.stack.notes.map(n => <li key={n}>{n}</li>)}</ul>
      </div></section>

      <section id="faq" className="st-section"><div className="st-wrap st-faq-grid">
        <div><h2>{t.faq.title}</h2><p className="st-section-lead">{t.faq.lead}</p></div>
        <div className="st-faq">{FAQ.map(f => <details key={f.q}><summary>{f.q}</summary><p>{f.a}{f.link && <> <Link href={f.link.href} className="st-faq-link" target="_blank">{f.link.label}</Link></>}</p></details>)}</div>
      </div></section>

      <section id="inquiry" className="st-section st-inquiry"><div className="st-wrap st-inquiry-grid">
        <div>
          <h2>{t.inquiry.title}</h2>
          <p className="st-section-lead">{t.inquiry.lead}</p>
          <ul className="st-checks">{t.inquiry.checks.map(c => <li key={c}>{c}</li>)}</ul>
          {CONTACT.kakao && <div className="st-contact">
            <p>{t.contact.lead}</p>
            <div className="st-contact-links">
              <a href={CONTACT.kakao} target="_blank" rel="noreferrer" className="st-button st-button-kakao">{t.contact.kakao}</a>
            </div>
          </div>}
        </div>
        <InquiryForm lang={lang} chat={chat} onDone={includedChat => { if (includedChat) setSentBelow(true); }} />
      </div></section>
    </main>

    <footer className="st-footer"><div className="st-wrap">
      <strong>{site.name}</strong><p>{site.description}</p>
      {CONTACT.kakao && <p className="st-footer-small"><a href={CONTACT.kakao} target="_blank" rel="noreferrer">{t.contact.kakao}</a></p>}
      <p className="st-footer-small st-footer-links"><Link href="/privacy"><strong>{t.legal.privacy}</strong></Link><Link href="/terms">{t.legal.terms}</Link></p>
      <p className="st-footer-small">{t.footer(site.name)}</p>
    </div></footer>
  </div>;
}
