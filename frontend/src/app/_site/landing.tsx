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
import { content } from "../site-content";

export default function Landing({ lang = "ko" }: { lang?: Lang }) {
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
  // 버튼 위치(where)를 함께 기록해 어느 버튼으로 상담·접수에 들어오는지 본다.
  const goInquiry = (where = "other") => { track("cta_click", { target: "inquiry", where }); document.getElementById("inquiry")?.scrollIntoView({ behavior: "smooth", block: "start" }); };
  // 휴대폰에서는 상담 기록지를 전체화면으로 연다(consult-chat.tsx가 이 이벤트를 받는다).
  const goChat = (where = "other") => {
    track("cta_click", { target: "chat", where });
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
  async function demo(where: string) {
    track("demo_quote_start", { from: where });
    setDemoBusy(true); setDemoError("");
    // 견적서 화면은 새로 불러와 방문 분석 스크립트가 따라가지 않게 한다(주소에 토큰이 있다).
    try { window.location.assign(await createDemoQuote(undefined, lang)); }
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
            <button className="st-button" onClick={() => goInquiry("hero")}>{t.hero.form}</button>
          </div>
        </div>
        <div id="consult"><ConsultChat lang={lang} onFallback={() => goInquiry("chat_offline")} onChange={onChat} sentElsewhere={sentBelow} /></div>
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
            <button className="st-text-link" onClick={() => goChat("examples")}>{t.examples.chat[2]}</button>
          </article>
          <article className="st-example">
            <ul className="st-tags">{["payment", "web"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
            <h3>{t.examples.quote[0]}</h3>
            <p>{t.examples.quote[1]}</p>
            <button className="st-text-link" disabled={demoBusy} onClick={() => void demo("examples")}>{demoBusy ? t.hero.demoBusy : t.hero.demo}</button>
            {demoError && <p className="st-error" role="alert">{demoError}</p>}
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
          <p className="st-plan-price">{p.price}</p>
          <p className="st-plan-fit"><span>{t.maintenance.fit}</span> {p.fit}</p>
          <p className="st-plan-points">{t.maintenance.points} <strong>{p.points}{t.maintenance.pointUnit}</strong> {t.maintenance.pointsTail}</p>
          <ul>{p.includes.map(item => <li key={item}>{item}</li>)}</ul>
        </article>)}</div>
        <h3 className="st-levels-title">{t.maintenance.howTitle}</h3>
        <ol className="st-point-steps">{t.maintenance.how.map(([title, text]) => <li key={title}><strong>{title}</strong><p>{text}</p></li>)}</ol>
        <h3 className="st-levels-title">{t.maintenance.levelsTitle}</h3>
        <p className="st-levels-lead">{t.maintenance.levelsLead}</p>
        <table className="st-table st-levels">
          <thead><tr>{t.maintenance.levelCols.map(c => <th key={c} scope="col">{c}</th>)}</tr></thead>
          <tbody>{MAINTENANCE.levels.map(l => <tr key={l.name}>
            <td className="st-level-name"><span>{l.code}</span> {l.name}</td><td>{l.examples}</td><td className="st-level-points">{l.points}</td>
          </tr>)}</tbody>
        </table>
        <ul className="st-plan-notes">{MAINTENANCE.notes.map(n => <li key={n}>{n}</li>)}</ul>
        <button className="st-text-link" onClick={() => goInquiry("maintenance")}>{t.maintenance.cta}</button>
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
      <button type="button" className="st-button st-button-ghost" onClick={() => goChat("mobile_bar")}>{t.mobileCta.chat}</button>
      <button type="button" className="st-button" onClick={() => goInquiry("mobile_bar")}>{t.mobileCta.form}</button>
    </nav>

    <footer className="st-footer"><div className="st-wrap">
      <strong>{site.name}</strong><p>{site.description}</p>
      {CONTACT.kakao && <p className="st-footer-small"><a href={CONTACT.kakao} target="_blank" rel="noreferrer">{t.contact.kakao}</a></p>}
      <p className="st-footer-small st-footer-links"><Link href="/privacy"><strong>{t.legal.privacy}</strong></Link><Link href="/terms">{t.legal.terms}</Link></p>
      <p className="st-footer-small">{t.footer(site.name)}</p>
    </div></footer>
  </div>;
}
