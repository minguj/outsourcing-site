"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, won } from "../_site/api";
import { SITE } from "../site-config";

type Quote = {
  title: string; items: { name: string; amount: number }[]; total: number; deposit: number; schedule: string; note: string;
  status: string; created_at: number; paid_at: number | null; customer: { name: string; company: string }; payment_ready: boolean; payment_mode: "toss" | "mock" | "off"; payment_test: boolean;
};
type Checkout = { mock: boolean; client_key: string; order_id: string; amount: number; order_name: string; customer_name: string; customer_email: string };
type TossFactory = ((clientKey: string) => { payment: (o: { customerKey: string }) => { requestPayment: (o: object) => Promise<void> } }) & { ANONYMOUS?: string };

const date = (seconds: number) => new Intl.DateTimeFormat("ko-KR", { dateStyle: "long" }).format(new Date(seconds * 1000));

function loadToss(): Promise<TossFactory> {
  const existing = (window as unknown as { TossPayments?: TossFactory }).TossPayments;
  if (existing) return Promise.resolve(existing);
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://js.tosspayments.com/v2/standard";
    script.onload = () => {
      const loaded = (window as unknown as { TossPayments?: TossFactory }).TossPayments;
      if (loaded) resolve(loaded); else reject(new Error("결제창을 불러오지 못했습니다."));
    };
    script.onerror = () => reject(new Error("결제창을 불러오지 못했습니다. 광고 차단 기능을 끄고 다시 시도해 주세요."));
    document.head.appendChild(script);
  });
}

export default function QuoteView({ mode }: { mode: "view" | "success" | "fail" }) {
  const [token, setToken] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const params = new URLSearchParams(window.location.search);
    const t = params.get("t") ?? "";
    void (async () => {
      setToken(t);
      if (!t) { setError("견적서 링크가 올바르지 않습니다. 받은 링크를 다시 확인해 주세요."); return; }
      try {
        if (mode === "success") {
          setNotice("결제를 확인하고 있습니다.");
          const paid = await api<Quote>(`/api/quotes/${t}/confirm`, { method: "POST", body: JSON.stringify({
            payment_key: params.get("paymentKey") ?? "", order_id: params.get("orderId") ?? "", amount: Number(params.get("amount") ?? 0) }) });
          setQuote(paid); setNotice("착수금 결제가 완료되었습니다. 담당자가 확인 후 착수 일정을 안내해 드립니다.");
          window.history.replaceState(null, "", `/quote?t=${encodeURIComponent(t)}`);
        } else {
          setQuote(await api<Quote>(`/api/quotes/${t}`));
          if (mode === "fail") setError(params.get("code") === "PAY_PROCESS_CANCELED" ? "결제를 취소하셨습니다. 준비되면 다시 결제해 주세요." : `결제가 완료되지 않았습니다. ${params.get("message") ?? ""}`.trim());
        }
      } catch (err) {
        setNotice("");
        setError(err instanceof Error ? err.message : "견적서를 불러오지 못했습니다.");
        if (mode === "success") api<Quote>(`/api/quotes/${t}`).then(setQuote).catch(() => undefined);
      }
    })();
  }, [mode]);

  async function pay() {
    if (!quote) return;
    setBusy(true); setError("");
    try {
      const order = await api<Checkout>(`/api/quotes/${token}/checkout`, { method: "POST" });
      if (order.mock) {
        // Local test: skip the payment window and return the way Toss would, so the same server check runs.
        const query = new URLSearchParams({ t: token, paymentKey: `mock_${order.order_id}`, orderId: order.order_id, amount: String(order.amount) });
        window.location.assign(`${window.location.origin}/quote/success?${query}`);
        return;
      }
      const Toss = await loadToss();
      const base = `${window.location.origin}/quote`;
      await Toss(order.client_key).payment({ customerKey: Toss.ANONYMOUS ?? "ANONYMOUS" }).requestPayment({
        method: "CARD", amount: { currency: "KRW", value: order.amount }, orderId: order.order_id, orderName: order.order_name,
        successUrl: `${base}/success?t=${encodeURIComponent(token)}`, failUrl: `${base}/fail?t=${encodeURIComponent(token)}`,
        customerName: order.customer_name || undefined, customerEmail: order.customer_email || undefined,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "결제를 시작하지 못했습니다.";
      if (!/취소|cancel/i.test(message)) setError(message);
    } finally { setBusy(false); }
  }

  const paid = quote?.status === "paid";
  return <div className="st-doc-page"><div className="st-wrap">
    <p style={{ marginBottom: 16 }}><Link href="/" className="st-logo">{SITE.name}</Link></p>
    {notice && <p className="st-badge" role="status" style={{ marginBottom: 14 }}>{notice}</p>}
    {error && <p className="st-error" role="alert" style={{ marginBottom: 14 }}>{error}</p>}
    {!quote && !error && <p>견적서를 불러오는 중입니다.</p>}
    {quote && <article className="st-doc" aria-label="견적서">
      {paid && <span className="st-stamp st-paid-stamp" aria-label="착수금 결제 완료">결제<br />완료</span>}
      <div className="st-doc-title"><h1>견적서</h1><div className="st-doc-meta">발행 {date(quote.created_at)}<br />{SITE.name}</div></div>
      <p style={{ marginBottom: 6 }}><strong>{quote.customer.company || quote.customer.name}</strong> 귀하{quote.customer.company && quote.customer.name ? ` (${quote.customer.name} 님)` : ""}</p>
      <h2 style={{ fontSize: 20, margin: "14px 0 18px" }}>{quote.title}</h2>
      <table className="st-table">
        <thead><tr><th>항목</th><th className="st-num">금액</th></tr></thead>
        <tbody>{quote.items.map((item, i) => <tr key={i}><td>{item.name}</td><td className="st-num">{won(item.amount)}</td></tr>)}</tbody>
        <tfoot><tr><td>합계</td><td className="st-num">{won(quote.total)}</td></tr></tfoot>
      </table>
      {quote.schedule && <p className="st-note"><strong>일정</strong><br />{quote.schedule}</p>}
      {quote.note && <p className="st-note"><strong>안내</strong><br />{quote.note}</p>}
      <div className="st-pay-box">
        <div><small>착수금</small><strong>{won(quote.deposit)}</strong><small>{paid && quote.paid_at ? `${date(quote.paid_at)} 결제 완료` : "결제하시면 개발을 시작합니다."}</small></div>
        {paid ? <span className="st-badge">결제 완료</span>
          : quote.payment_ready ? <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <button className="st-button" disabled={busy} onClick={() => void pay()}>{busy ? "결제창을 여는 중" : `착수금 ${won(quote.deposit)} 결제`}</button>
            {quote.payment_mode === "mock" ? <span className="st-badge st-badge-test">모의 결제: 결제창 없이 결제 완료 흐름만 확인합니다</span>
              : quote.payment_test && <span className="st-badge st-badge-test">테스트 결제: 실제로 청구되지 않습니다</span>}
          </div>
          : <p style={{ fontSize: 14, color: "var(--muted)", maxWidth: 280 }}>온라인 결제를 준비하고 있습니다. 결제 방법은 담당자가 따로 안내해 드립니다.</p>}
      </div>
    </article>}
  </div></div>;
}
