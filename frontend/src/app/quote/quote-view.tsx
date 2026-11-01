"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "../_site/api";
import { COPY, HOME, money, type Lang } from "../_site/i18n";
import { BANK, siteFor } from "../site-config";

type Quote = {
  title: string; items: { name: string; amount: number }[]; total: number; deposit: number; schedule: string; note: string;
  status: string; created_at: number; paid_at: number | null; customer: { name: string; company: string }; payment_ready: boolean; payment_mode: "toss" | "mock" | "off"; payment_test: boolean;
  is_demo: boolean; lang: Lang; next_steps: { title: string; text: string }[];
};
type Checkout = { mock: boolean; client_key: string; order_id: string; amount: number; order_name: string; customer_name: string; customer_email: string };
type TossFactory = ((clientKey: string) => { payment: (o: { customerKey: string }) => { requestPayment: (o: object) => Promise<void> } }) & { ANONYMOUS?: string };

const date = (lang: Lang, seconds: number) => new Intl.DateTimeFormat(COPY[lang].quote.locale, { dateStyle: "long" }).format(new Date(seconds * 1000));

function loadToss(lang: Lang): Promise<TossFactory> {
  const t = COPY[lang].quote;
  const existing = (window as unknown as { TossPayments?: TossFactory }).TossPayments;
  if (existing) return Promise.resolve(existing);
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://js.tosspayments.com/v2/standard";
    script.onload = () => {
      const loaded = (window as unknown as { TossPayments?: TossFactory }).TossPayments;
      if (loaded) resolve(loaded); else reject(new Error(t.tossLoad));
    };
    script.onerror = () => reject(new Error(t.tossBlocked));
    document.head.appendChild(script);
  });
}

export default function QuoteView({ mode }: { mode: "view" | "success" | "fail" }) {
  const [token, setToken] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  // The quote decides its language; ?lang=en is only a hint until it loads.
  const [hint, setHint] = useState<Lang>("ko");
  const lang: Lang = quote?.lang ?? hint;
  const t = COPY[lang].quote;
  const site = siteFor(lang);
  const won = (value: number) => money(lang, value);
  const started = useRef(false);
  const router = useRouter();

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const params = new URLSearchParams(window.location.search);
    const t = params.get("t") ?? "";
    const guess: Lang = params.get("lang") === "en" ? "en" : "ko";
    const copy = COPY[guess].quote;
    void (async () => {
      setToken(t); setHint(guess);
      document.documentElement.lang = guess;
      if (!t) { setError(copy.badLink); return; }
      try {
        if (mode === "success") {
          setNotice(copy.checking);
          const paid = await api<Quote>(`/api/quotes/${t}/confirm`, { method: "POST", body: JSON.stringify({
            payment_key: params.get("paymentKey") ?? "", order_id: params.get("orderId") ?? "", amount: Number(params.get("amount") ?? 0) }) }, guess);
          setQuote(paid);
          const done = COPY[paid.lang].quote;
          setNotice(paid.is_demo ? done.demoPaid : done.paidNotice);
          window.history.replaceState(null, "", `/quote?t=${encodeURIComponent(t)}${paid.lang === "en" ? "&lang=en" : ""}`);
        } else {
          const loaded = await api<Quote>(`/api/quotes/${t}`, undefined, guess);
          setQuote(loaded);
          const fail = COPY[loaded.lang].quote;
          if (mode === "fail") setError(params.get("code") === "PAY_PROCESS_CANCELED" ? fail.canceled : `${fail.notDone} ${params.get("message") ?? ""}`.trim());
        }
      } catch (err) {
        setNotice("");
        setError(err instanceof Error ? err.message : copy.loadFailed);
        if (mode === "success") api<Quote>(`/api/quotes/${t}`, undefined, guess).then(setQuote).catch(() => undefined);
      }
    })();
  }, [mode]);

  async function pay() {
    if (!quote) return;
    setBusy(true); setError("");
    try {
      const order = await api<Checkout>(`/api/quotes/${token}/checkout`, { method: "POST" }, lang);
      const suffix = lang === "en" ? "&lang=en" : "";
      if (order.mock) {
        // Local test: skip the payment window and return the way Toss would, so the same server check runs.
        const query = new URLSearchParams({ t: token, paymentKey: `mock_${order.order_id}`, orderId: order.order_id, amount: String(order.amount) });
        router.push(`/quote/success?${query}${suffix}`);
        return;
      }
      const Toss = await loadToss(lang);
      const base = `${window.location.origin}/quote`;
      await Toss(order.client_key).payment({ customerKey: Toss.ANONYMOUS ?? "ANONYMOUS" }).requestPayment({
        method: "CARD", amount: { currency: "KRW", value: order.amount }, orderId: order.order_id, orderName: order.order_name,
        successUrl: `${base}/success?t=${encodeURIComponent(token)}${suffix}`, failUrl: `${base}/fail?t=${encodeURIComponent(token)}${suffix}`,
        customerName: order.customer_name || undefined, customerEmail: order.customer_email || undefined,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : t.startFailed;
      if (!/취소|cancel/i.test(message)) setError(message);
    } finally { setBusy(false); }
  }

  async function copyAccount() {
    const text = BANK.account.replace(/-/g, "");
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch { /* no Clipboard API on plain http: fall back below */ }
    if (!ok) {
      const area = document.createElement("textarea");
      area.value = text; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
      document.body.appendChild(area); area.select();
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      area.remove();
    }
    setCopied(ok);
    if (ok) setTimeout(() => setCopied(false), 2000);
  }

  const paid = quote?.status === "paid";
  const b = t.bank;
  return <div className={"st-doc-page" + (lang === "en" ? " st-lang-en" : "")}><div className="st-wrap">
    <p style={{ marginBottom: 16 }}><Link href={HOME[lang]} className="st-logo">{site.name}</Link></p>
    {notice && <p className="st-badge" role="status" style={{ marginBottom: 14 }}>{notice}</p>}
    {error && <p className="st-error" role="alert" style={{ marginBottom: 14 }}>{error}</p>}
    {!quote && !error && <p>{t.loading}</p>}
    {quote?.is_demo && <div className="st-demo-banner" role="note">
      <p><strong>{t.demoBanner[0]}</strong> {t.demoBanner[1]}</p>
      <Link href={`${HOME[lang]}#inquiry`} className="st-button st-button-ghost">{t.realInquiry}</Link>
    </div>}
    {quote && <article className="st-doc" aria-label={t.label}>
      {paid && <span className="st-stamp st-paid-stamp" aria-label={t.paidStamp}>{t.stamp[0]}{t.stamp[1] && <><br />{t.stamp[1]}</>}</span>}
      <div className="st-doc-title"><h1>{t.title}</h1><div className="st-doc-meta">{t.issued} {date(lang, quote.created_at)}<br />{site.name}</div></div>
      <p style={{ marginBottom: 6 }}>{t.to[0]}<strong>{quote.customer.company || quote.customer.name}</strong>{t.to[1]}{quote.customer.company && quote.customer.name ? t.person(quote.customer.name) : ""}</p>
      <h2 style={{ fontSize: 20, margin: "14px 0 18px" }}>{quote.title}</h2>
      <table className="st-table">
        <thead><tr><th>{t.item}</th><th className="st-num">{t.amount}</th></tr></thead>
        <tbody>{quote.items.map((item, i) => <tr key={i}><td>{item.name}</td><td className="st-num">{won(item.amount)}</td></tr>)}</tbody>
        <tfoot><tr><td>{t.total}</td><td className="st-num">{won(quote.total)}</td></tr></tfoot>
      </table>
      {quote.schedule && <p className="st-note"><strong>{t.schedule}</strong><br />{quote.schedule}</p>}
      {quote.note && <p className="st-note"><strong>{t.note}</strong><br />{quote.note}</p>}
      <div className="st-pay-box">
        <div><small>{t.deposit}</small><strong>{won(quote.deposit)}</strong><small>{paid && quote.paid_at ? t.paidOn(date(lang, quote.paid_at)) : t.startsWork}</small></div>
        {paid ? <span className="st-badge">{t.paid}</span>
          : quote.payment_ready ? <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <button className="st-button" disabled={busy} onClick={() => void pay()}>{busy ? t.opening : t.pay(won(quote.deposit))}</button>
            {quote.payment_mode === "mock" ? <span className="st-badge st-badge-test">{t.mock}</span>
              : quote.payment_test && <span className="st-badge st-badge-test">{t.test}</span>}
          </div>
          : <p style={{ fontSize: 14, color: "var(--muted)", maxWidth: 280 }}>{t.off}</p>}
      </div>
      {!quote.is_demo && <section className="st-next st-bank" aria-label={b.title}>
        <h2>{b.title}</h2>
        <p className="st-bank-lead">{b.lead}{quote.payment_ready && !paid ? ` ${b.demoNote}` : ""}</p>
        <dl className="st-bank-info">
          <div><dt>{b.account}</dt><dd><strong>{BANK.bank} {BANK.account}</strong>
            <button type="button" className="st-button st-button-ghost st-bank-copy" onClick={() => void copyAccount()}>{copied ? b.copied : b.copy}</button></dd></div>
          {BANK.holder && <div><dt>{b.holder}</dt><dd>{BANK.holder}</dd></div>}
          <div><dt>{b.amount}</dt><dd>{won(quote.deposit)}</dd></div>
          <div><dt>{b.payer}</dt><dd>{b.payerText}</dd></div>
        </dl>
        <h3>{b.steps}</h3>
        <ol>{b.list.map(([title, text], i) => <li key={title}><strong>{title}</strong><span>{text}
          {i === 0 && lang === "ko" && <> <Link href={`/contract?t=${encodeURIComponent(token)}`} target="_blank" className="st-contract-link">{b.contract}</Link></>}</span></li>)}</ol>
      </section>}
      {paid && <section className="st-next" aria-label={t.next}>
        <h2>{t.next}</h2>
        <ol>{quote.next_steps.map(step => <li key={step.title}><strong>{step.title}</strong><span>{step.text}</span></li>)}</ol>
        {quote.is_demo && <p className="st-next-note">{t.demoNext} <Link href={`${HOME[lang]}#inquiry`}>{t.toInquiry}</Link></p>}
      </section>}
    </article>}
  </div></div>;
}
