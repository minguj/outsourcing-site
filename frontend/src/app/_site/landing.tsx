"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { createDemoQuote } from "./api";
import { ConsultChat, type ChatSession } from "./consult-chat";
import { COPY, HOME, type Lang } from "./i18n";
import { InquiryForm } from "./inquiry-form";
import { CONTACT, siteFor } from "../site-config";
import { content } from "../site-content";

export default function Landing({ lang = "ko" }: { lang?: Lang }) {
  const router = useRouter();
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoError, setDemoError] = useState("");
  const [chat, setChat] = useState<ChatSession | null>(null);
  const [sentBelow, setSentBelow] = useState(false);
  const onChat = useCallback((session: ChatSession) => setChat(session), []);
  const t = COPY[lang];
  const site = siteFor(lang);
  const { SERVICES, PROCESS, FAQ, MAINTENANCE } = content(lang);
  const serviceName = (id: string) => SERVICES.find(s => s.id === id)?.name ?? id;
  // One root layout serves both languages; keep <html lang> right for screen readers and translation tools.
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const goInquiry = () => document.getElementById("inquiry")?.scrollIntoView({ behavior: "smooth", block: "start" });
  // 휴대폰에서는 상담 기록지를 전체화면으로 연다(consult-chat.tsx가 이 이벤트를 받는다).
  const goChat = () => {
    if (window.matchMedia("(max-width: 960px)").matches) window.dispatchEvent(new Event("st-open-chat"));
    else document.getElementById("consult")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  // 휴대폰에서는 상담 기록지와 접수 양식이 화면 아래쪽에 있어, 둘 다 안 보일 때만 하단 바로가기 막대를 띄운다.
  const [ctaHidden, setCtaHidden] = useState(true);
  useEffect(() => {
    const targets = ["consult", "inquiry"].map(id => document.getElementById(id)).filter((el): el is HTMLElement => !!el);
    const visible = new Set<Element>();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) visible.add(e.target); else visible.delete(e.target); });
      setCtaHidden(visible.size > 0);
    }, { threshold: 0.15 });
    targets.forEach(el => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  async function demo() {
    setDemoBusy(true); setDemoError("");
    try { router.push(await createDemoQuote(undefined, lang)); }
    catch (err) { setDemoError(err instanceof Error ? err.message : t.hero.demoFailed); setDemoBusy(false); }
  }

  return <div className={"st-page" + (lang === "en" ? " st-lang-en" : "")}>
    <header className="st-nav"><div className="st-wrap">
      <Link href={HOME[lang]} className="st-logo">{site.name}</Link>
      <nav aria-label={t.nav.label}><a href="#services">{t.nav.services}</a><a href="#examples">{t.nav.examples}</a><a href="#process">{t.nav.process}</a><a href="#maintenance">{t.nav.maintenance}</a><a href="#faq">{t.nav.faq}</a><a href="#inquiry" className="st-nav-cta">{t.nav.inquiry}</a>
        {/* 영문 사이트는 보류 중이라 한국어 페이지에는 전환 버튼을 숨긴다. 다시 열 때 lang 조건을 지운다. */}
        {lang === "en" && <Link href={t.nav.switchHref} className="st-lang-switch" hrefLang={t.nav.switchLang} lang={t.nav.switchLang}>{t.nav.switchTo}</Link>}</nav>
    </div></header>

    <main>
      <section className="st-hero"><div className="st-wrap st-hero-grid">
        <div className="st-hero-copy">
          <p className="st-hero-kicker">{site.tagline}</p>
          <h1>{t.hero.title}</h1>
          <p className="st-lead">{t.hero.lead}</p>
          <ul className="st-hero-services" aria-label={t.hero.services}>{SERVICES.map(s => <li key={s.id}><a href={`#service-${s.id}`}>{s.name}</a></li>)}</ul>
          <p className="st-lead">{t.hero.lead2}</p>
          <div className="st-hero-actions">
            <button className="st-button" disabled={demoBusy} onClick={() => void demo()}>{demoBusy ? t.hero.demoBusy : t.hero.demo}</button>
            <button className="st-button st-button-ghost" onClick={goInquiry}>{t.hero.form}</button>
          </div>
          {demoError && <p className="st-error" role="alert" style={{ marginTop: 12 }}>{demoError}</p>}
        </div>
        <div id="consult"><ConsultChat lang={lang} onFallback={goInquiry} onChange={onChat} sentElsewhere={sentBelow} /></div>
      </div></section>

      <section id="services" className="st-section"><div className="st-wrap">
        <h2>{t.services.title}</h2>
        <p className="st-section-lead">{t.services.lead}</p>
        <div className="st-ledger" role="table" aria-label={t.services.cols[0]}>
          <div className="st-ledger-head" role="row">{t.services.cols.map(c => <span role="columnheader" key={c}>{c}</span>)}</div>
          {SERVICES.map(s => <div className="st-ledger-row" role="row" key={s.id} id={`service-${s.id}`}>
            <h3 role="rowheader">{s.name}</h3><p role="cell">{s.what}</p><ul role="cell">{s.examples.map(e => <li key={e}>{e}</li>)}</ul>
          </div>)}
        </div>
      </div></section>

      <section id="examples" className="st-section st-examples-section"><div className="st-wrap">
        <h2>{t.examples.title}</h2>
        <p className="st-section-lead">{t.examples.lead}</p>
        <div className="st-examples">
          <article className="st-example">
            <ul className="st-tags">{["ai"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
            <h3>{t.examples.chat[0]}</h3>
            <p>{t.examples.chat[1]}</p>
            <button className="st-text-link" onClick={goChat}>{t.examples.chat[2]}</button>
          </article>
          <article className="st-example">
            <ul className="st-tags">{["payment", "web"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
            <h3>{t.examples.quote[0]}</h3>
            <p>{t.examples.quote[1]}</p>
            <button className="st-text-link" disabled={demoBusy} onClick={() => void demo()}>{t.hero.demo}</button>
          </article>
          <article className="st-example">
            <ul className="st-tags">{["web", "infra"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
            <h3>{t.examples.admin[0]}</h3>
            <p>{t.examples.admin[1]}</p>
          </article>
          <article className="st-example st-example-wide">
            <div>
              <ul className="st-tags">{["docs"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
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

      <section id="process" className="st-section"><div className="st-wrap">
        <h2>{t.process.title}</h2>
        <ol className="st-steps">{PROCESS.map((s, i) => <li key={s.title} className={i === 2 ? "st-step-pay" : undefined}><span className="st-step-no" aria-hidden="true">{i + 1}</span><h3>{s.title}</h3><p>{s.text}</p></li>)}</ol>
      </div></section>

      <section id="maintenance" className="st-section"><div className="st-wrap">
        <h2>{t.maintenance.title}</h2>
        <p className="st-section-lead">{t.maintenance.lead}</p>
        <div className="st-plans">{MAINTENANCE.plans.map(p => <article key={p.name} className="st-plan">
          <h3>{p.name}</h3>
          <p className="st-plan-fit"><span>{t.maintenance.fit}</span> {p.fit}</p>
          <ul>{p.includes.map(item => <li key={item}>{item}</li>)}</ul>
        </article>)}</div>
        <ul className="st-plan-notes">{MAINTENANCE.notes.map(n => <li key={n}>{n}</li>)}</ul>
        <button className="st-text-link" onClick={goInquiry}>{t.maintenance.cta}</button>
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

    <nav className={"st-mobile-cta" + (ctaHidden ? " is-hidden" : "")} aria-label={t.mobileCta.label}>
      <button type="button" className="st-button st-button-ghost" onClick={goChat}>{t.mobileCta.chat}</button>
      <button type="button" className="st-button" onClick={goInquiry}>{t.mobileCta.form}</button>
    </nav>

    <footer className="st-footer"><div className="st-wrap">
      <strong>{site.name}</strong><p>{site.description}</p>
      {CONTACT.kakao && <p className="st-footer-small"><a href={CONTACT.kakao} target="_blank" rel="noreferrer">{t.contact.kakao}</a></p>}
      <p className="st-footer-small st-footer-links"><Link href="/privacy"><strong>{t.legal.privacy}</strong></Link><Link href="/terms">{t.legal.terms}</Link></p>
      <p className="st-footer-small">{t.footer(site.name)}</p>
    </div></footer>
  </div>;
}
