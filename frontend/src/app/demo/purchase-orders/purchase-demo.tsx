"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import "./purchase-demo.css";
import { COLUMNS, Original, Statement, type Row, type Action, type Session, type PreviewRow } from "./statement-workspace";

const BASE = "/api/demo/purchase-orders";
const choices = [
  { id: "A", title: "인쇄용 엑셀 발주서", text: "병합 셀·품목표·요청사항", width: 850, height: 1180 },
  { id: "B", title: "쇼핑몰 주문 내역", text: "취소 제외·옵션 매칭·취합", width: 2470, height: 660 },
  { id: "C", title: "제조업 구매 발주서", text: "규격·소수 수량·개별 납기", width: 1270, height: 1140 },
];

async function checked(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (typeof body.detail === "string") throw new Error(body.detail);
    if (Array.isArray(body.detail)) throw new Error("화면과 서버의 요청 형식이 맞지 않습니다. 백엔드 서버를 재시작했는지 확인해 주세요. (" + body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(" / ") + ")");
    throw new Error(response.status >= 500 ? "서버에 연결할 수 없습니다. 백엔드(8000번 포트)가 실행 중인지 확인해 주세요." : "요청값을 확인해 주세요. 서버가 실행 중인지도 확인해 주세요.");
  }
  return response;
}

export default function PurchaseDemo() {
  const [session, setSession] = useState<Session | null>(null);
  const [active, setActive] = useState("A");
  const [mobileTab, setMobileTab] = useState<"source" | "result">("result");
  const [sourceCollapsed, setSourceCollapsed] = useState(false);
  const sourceDialog = useRef<HTMLDialogElement>(null);
  const [original, setOriginal] = useState<{ sample: string; filename: string; sheet: string; preview: PreviewRow[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const order = session?.orders.find(o => o.sample === active);

  async function perform(task: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await task(); } catch (e) { setError(e instanceof Error ? e.message : "요청에 실패했습니다."); } finally { setBusy(false); }
  }
  function start(samples: string[]) {
    void perform(async () => {
      const r = await checked(await fetch(`${BASE}/start`, { method: "POST", headers: { "Content-Type": "application/json", "X-Demo-Client": "purchase-orders" }, body: JSON.stringify({ samples }) }));
      setSession(await r.json()); setActive(samples[0]); setOriginal(null); setMobileTab("result"); setNotice("실제 샘플 XLSX를 읽어 변환했습니다. 확인 필요 행은 부분 합계에서 제외했습니다.");
    });
  }
  function review(row: Row, action: Action) {
    if (!session || !order) return;
    void perform(async () => {
      const r = await checked(await fetch(`${BASE}/${order.sample}/rows/${row.id}`, { method: "POST", headers: { "Content-Type": "application/json", "X-Demo-CSRF": session.csrf }, body: JSON.stringify({ ...action, revision: session.revision }) }));
      setSession(await r.json()); setNotice(`${row.id}행을 서버에서 재검증했습니다.`);
    });
  }
  function download(layout?: string) {
    if (!session || !order) return;
    void perform(async () => {
      const query = layout ? `&layout=${layout}` : "";
      const r = await checked(await fetch(`${BASE}/${order.sample}/download?revision=${session.revision}${query}`));
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a"); a.href = url; a.download = layout ? `statement_${order.sample}_as_${layout}_form.xlsx` : `statement_${order.sample}.xlsx`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice(layout ? `${order.sample} 거래처의 검수 결과를 ${layout} 거래처 양식으로 회신하는 XLSX를 다운로드했습니다.` : "거래명세서·원본추적·납기별내역을 포함한 XLSX를 다운로드했습니다.");
    });
  }

  function viewSource(sample: string) {
    setActive(sample); setMobileTab("source"); setOriginal(null);
    if (session?.orders.some(o => o.sample === sample)) return;
    void perform(async () => {
      const r = await checked(await fetch(BASE + "/samples/" + sample + "/preview"));
      setOriginal(await r.json());
    });
  }
  const source = order ?? (original?.sample === active ? original : null);

  return <main className="po-page"><div className="po-container">
    <nav className="po-nav"><Link href="/">모아소모품 · 가상 업무 체험</Link><span>샘플 전용 데모</span></nav>
    <header className="po-hero">
      <p className="po-kicker">거래처 발주서 → 우리 회사 거래명세서</p>
      <h1>거래처마다 다른 발주서를<br /><em>우리 회사의 동일한 거래명세서 양식으로.</em></h1>
      <p>A/B/C 원본은 각각 읽고, 검수하고, 각각 발행합니다. <strong>거래처는 따로, 출력 포맷은 하나입니다.</strong></p>
    </header>
    <section className="po-flow" aria-label="A/B/C 원본에서 동일한 거래명세서 양식으로 변환">
      <div className="po-thumbnails">{choices.map(c => <button key={c.id} className="po-thumbnail" aria-label={c.id + " 원본 보기"} aria-pressed={active === c.id && !!source} disabled={busy} onClick={() => viewSource(c.id)}>
        <div className="po-thumbnail-image"><Image src={"/samples/purchase-orders/thumbnails/" + c.id + ".png"} width={c.width} height={c.height} unoptimized alt={c.id + " 거래처의 가상 " + c.title + " 원본 썸네일"} /></div>
        <span><b>{c.id} 거래처</b> {c.title}</span><small>{c.text}</small>
      </button>)}</div>
      <div className="po-flow-arrow"><span aria-hidden="true">→</span><small>동일한 양식으로</small></div>
      <div className="po-common-thumbnail"><span className="po-kicker">우리 회사의 공통 출력 양식</span><h2>거래명세서</h2>
        <p>공급자 (가상)모아소모품 도매</p><div className="po-mini-sheet" aria-label="공통 거래명세서의 동일한 열"><div>{COLUMNS.map(c => <span key={c}>{c}</span>)}</div>{[1,2,3].map(r => <div key={r}>{COLUMNS.map(c => <span key={c}>—</span>)}</div>)}</div>
        <div className="po-separate-files"><span>A 거래처 XLSX</span><span>B 거래처 XLSX</span><span>C 거래처 XLSX</span></div><small>검수 후 거래처별로 개별 다운로드 · 합쳐서 발행하지 않음 · 거래처 원래 양식으로 회신도 가능</small>
      </div>
    </section>
    <div className="po-start-bar"><div><strong>제공된 가상 샘플 A/B/C 세 종류만 체험할 수 있습니다.</strong><p>실제 XLSX를 읽어 변환합니다. 모든 회사·담당자·연락처는 가상이며 실제 거래용이 아닙니다.</p></div>
      <div className="po-start-actions"><button disabled={busy} onClick={() => start(["A", "B", "C"])}>A/B/C 전체 체험 →</button><button className="po-secondary" disabled={busy} onClick={() => start([active])}>{active} 거래처만 체험</button>
        <button className="po-text-button" disabled={busy} onClick={() => void perform(async () => { const r = await checked(await fetch(BASE + "/session")); const data: Session = await r.json(); setSession(data); setActive(data.orders[0].sample); setMobileTab("result"); })}>진행 중 체험 다시 불러오기</button>
      </div>
      {session && <small>새 체험을 시작하면 현재 브라우저의 검수 내역이 초기화됩니다.</small>}
    </div>
    <div className="po-feedback" aria-live="polite">{busy && <p>서버에서 재검증 중…</p>}{notice && <p>✓ {notice}</p>}</div>
    {error && <div role="alert" className="po-error po-error-toast"><span>! {error}</span><button className="po-text-button" onClick={() => setError("")} aria-label="오류 메시지 닫기">닫기 ×</button></div>}
    {session && <div className="po-customer-bar"><div className="po-customer-tabs" aria-label="거래처 선택">{session.orders.map(o => <button key={o.sample} disabled={busy} aria-pressed={active === o.sample} onClick={() => { setActive(o.sample); setOriginal(null); setMobileTab("result"); }}>
      <b>{o.sample}</b> {o.customer}<span>{o.review ? "! 확인 " + o.review + "행" : "✓ 검수 완료"}</span>
    </button>)}</div><p>전체 주문 원본 {session.summary.source_rows}행 · 확인 필요 {session.summary.review}행 · 취소 제외 {session.summary.canceled}행</p></div>}
    {source && <section id="workspace" className="po-workspace" data-source-collapsed={sourceCollapsed} aria-label="원본과 공통 거래명세서 비교">
      <div className="po-mobile-tabs" role="tablist" aria-label="모바일 원본 결과 전환">
        <button id="po-source-tab" role="tab" aria-selected={mobileTab === "source"} aria-controls="po-source-panel" onClick={() => setMobileTab("source")}>원본</button>
        <button id="po-result-tab" role="tab" aria-selected={mobileTab === "result"} aria-controls="po-result-panel" onClick={() => setMobileTab("result")}>공통 결과{order?.review ? " · 확인 " + order.review + "행" : ""}</button>
      </div>
      <div className="po-workspace-grid">
        <section id="po-source-panel" className="po-original-pane" data-mobile-active={mobileTab === "source"} aria-label="왼쪽 거래처 원본">
          <div className="po-source-collapsed"><button aria-expanded={false} onClick={() => setSourceCollapsed(false)}>원본 펼치기 →</button></div>
          <div className="po-original-content"><div className="po-source-controls"><button className="po-collapse-source po-secondary" aria-expanded={!sourceCollapsed} onClick={() => setSourceCollapsed(true)}>원본 접기</button><button className="po-secondary" onClick={() => sourceDialog.current?.showModal()}>확대 보기 ↗</button></div>
            <Original sample={source.sample} filename={source.filename} sheet={source.sheet} rows={source.preview} />
          </div>
        </section>
        <section id="po-result-panel" className="po-result-pane" data-mobile-active={mobileTab === "result"} aria-label="오른쪽 공통 거래명세서">
          {order && session ? <Statement key={order.sample} order={order} master={session.master} busy={busy} review={review} download={download} /> :
            <div className="po-awaiting-conversion"><span className="po-kicker">우리 회사의 동일한 출력 양식</span><h2>거래명세서</h2><p>{active} 원본을 확인한 뒤 변환하면, 이 자리에서 결과 행을 바로 검수할 수 있습니다.</p><button disabled={busy} onClick={() => start([active])}>{active} 거래처 변환 시작 →</button></div>}
        </section>
      </div>
      <dialog ref={sourceDialog} className="po-original-dialog" aria-label={source.sample + " 원본 확대 보기"}><div className="po-dialog-toolbar"><strong>{source.sample} 거래처 원본 확대 보기</strong><button onClick={() => sourceDialog.current?.close()}>닫기 ×</button></div><Original sample={source.sample} filename={source.filename} sheet={source.sheet} rows={source.preview} /></dialog>
    </section>}
    <footer className="po-footer">체험 내용은 브라우저별로 분리하며 시작 후 30분 또는 서버 재시작 시 사라집니다. 같은 브라우저의 탭은 상태를 공유합니다. 실제 업무·개인정보를 입력하지 마세요. 파일 업로드·AI 호출은 하지 않습니다.</footer>
  </div></main>;
}
