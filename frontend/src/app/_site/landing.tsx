"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createDemoQuote } from "./api";
import { ConsultChat } from "./consult-chat";
import { InquiryForm } from "./inquiry-form";
import { SITE } from "../site-config";
import { FAQ, PROCESS, SERVICES } from "../site-content";

const serviceName = (id: string) => SERVICES.find(s => s.id === id)?.name ?? id;

export default function Landing() {
  const router = useRouter();
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoError, setDemoError] = useState("");
  const goInquiry = () => document.getElementById("inquiry")?.scrollIntoView({ behavior: "smooth", block: "start" });
  const goChat = () => document.getElementById("consult")?.scrollIntoView({ behavior: "smooth", block: "center" });
  async function demo() {
    setDemoBusy(true); setDemoError("");
    try { router.push(await createDemoQuote()); }
    catch (err) { setDemoError(err instanceof Error ? err.message : "체험을 시작하지 못했습니다."); setDemoBusy(false); }
  }

  return <div className="st-page">
    <header className="st-nav"><div className="st-wrap">
      <Link href="/" className="st-logo">{SITE.name}</Link>
      <nav aria-label="주요 메뉴"><a href="#services">서비스</a><a href="#examples">작업 예시</a><a href="#process">진행 방식</a><a href="#faq">자주 묻는 질문</a><a href="#inquiry" className="st-nav-cta">상담 접수</a></nav>
    </div></header>

    <main>
      <section className="st-hero"><div className="st-wrap st-hero-grid">
        <div className="st-hero-copy">
          <p className="st-hero-kicker">{SITE.tagline}</p>
          <h1>사이트부터 결제, 문서 자동화, AI 에이전트, 배포까지 필요한 만큼 맡기세요</h1>
          <p className="st-lead">회사 업무에 맞춘 AI 상담 에이전트와 문서 변환 툴이 주력이고, 그에 필요한 웹사이트와 관리자 페이지, 결제 연동, 서버 배포까지 함께 만듭니다.</p>
          <ul className="st-hero-services" aria-label="서비스">{SERVICES.map(s => <li key={s.id}><a href={`#service-${s.id}`}>{s.name}</a></li>)}</ul>
          <p className="st-lead">옆의 상담 기록지에서 자주 묻는 질문을 바로 확인하거나, 맡기고 싶은 일을 말씀해 주세요.</p>
          <div className="st-hero-actions">
            <button className="st-button" disabled={demoBusy} onClick={() => void demo()}>{demoBusy ? "체험 견적서를 만드는 중" : "견적·결제 흐름 체험"}</button>
            <button className="st-button st-button-ghost" onClick={goInquiry}>양식으로 문의하기</button>
          </div>
          {demoError && <p className="st-error" role="alert" style={{ marginTop: 12 }}>{demoError}</p>}
        </div>
        <div id="consult"><ConsultChat onFallback={goInquiry} /></div>
      </div></section>

      <section id="services" className="st-section"><div className="st-wrap">
        <h2>맡길 수 있는 일</h2>
        <p className="st-section-lead">하나만 맡기셔도 되고, 필요한 것끼리 묶어 한 번에 진행할 수도 있습니다. 회사가 이미 쓰는 문서와 시스템에 맞춰 만듭니다.</p>
        <div className="st-ledger" role="table" aria-label="서비스">
          <div className="st-ledger-head" role="row"><span role="columnheader">서비스</span><span role="columnheader">하는 일</span><span role="columnheader">예시</span></div>
          {SERVICES.map(s => <div className="st-ledger-row" role="row" key={s.id} id={`service-${s.id}`}>
            <h3 role="rowheader">{s.name}</h3><p role="cell">{s.what}</p><ul role="cell">{s.examples.map(e => <li key={e}>{e}</li>)}</ul>
          </div>)}
        </div>
      </div></section>

      <section id="examples" className="st-section st-examples-section"><div className="st-wrap">
        <h2>이 사이트에서 직접 확인해 보세요</h2>
        <p className="st-section-lead">지금 보고 계신 사이트도 같은 방식으로 만들었습니다. 각 기능이 어떤 서비스에 해당하는지 눌러 보면서 확인할 수 있어요.</p>
        <div className="st-examples">
          <article className="st-example">
            <ul className="st-tags">{["ai"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
            <h3>AI 상담 기록지</h3>
            <p>자주 묻는 질문에 바로 답하고, 의뢰 내용을 대화로 정리해 담당자에게 넘깁니다. 회사 규정과 자료를 넣으면 고객 문의 응대용으로 바꿀 수 있어요.</p>
            <button className="st-text-link" onClick={goChat}>상담 기록지로 이동</button>
          </article>
          <article className="st-example">
            <ul className="st-tags">{["payment", "web"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
            <h3>견적서와 착수금 결제</h3>
            <p>체험용 견적서를 바로 만들어 착수금 결제부터 결제 완료 후 진행 안내까지 확인합니다. 실제로 청구되지 않아요.</p>
            <button className="st-text-link" disabled={demoBusy} onClick={() => void demo()}>견적·결제 흐름 체험</button>
          </article>
          <article className="st-example">
            <ul className="st-tags">{["web", "infra"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
            <h3>상담 관리 화면과 자동 배포</h3>
            <p>접수된 상담은 관리자 페이지에서 확인하고 견적서를 메일로 보냅니다. 코드는 GitHub에 올리면 검사를 거쳐 AWS 서버에 자동으로 배포됩니다.</p>
          </article>
          <article className="st-example st-example-wide">
            <div>
              <ul className="st-tags">{["docs"].map(id => <li key={id}>{serviceName(id)}</li>)}</ul>
              <h3>거래처 발주서 변환·검수</h3>
              <p>가상 거래처 세 곳의 서로 다른 발주서를 우리 거래명세서 양식으로 바꾸고, 빠진 값과 미등록 품목은 사람이 확인합니다. 결과를 거래처 원래 양식으로 회신할 수도 있어요.</p>
              <Link className="st-text-link" href="/demo/purchase-orders">발주서 변환 데모 열기</Link>
            </div>
            <Link href="/demo/purchase-orders" className="st-example-thumbs" aria-label="발주서 변환 데모 열기">
              {(["A", "B", "C"] as const).map((id, i) => <Image key={id} src={`/samples/purchase-orders/thumbnails/${id}.png`} alt={`${id} 거래처의 가상 발주서`} width={[850, 2470, 1270][i]} height={[1180, 660, 1140][i]} unoptimized />)}
            </Link>
          </article>
        </div>
      </div></section>

      <section id="process" className="st-section"><div className="st-wrap">
        <h2>진행 방식</h2>
        <ol className="st-steps">{PROCESS.map((s, i) => <li key={s.title} className={i === 2 ? "st-step-pay" : undefined}><span className="st-step-no" aria-hidden="true">{i + 1}</span><h3>{s.title}</h3><p>{s.text}</p></li>)}</ol>
      </div></section>

      <section id="faq" className="st-section"><div className="st-wrap st-faq-grid">
        <div><h2>자주 묻는 질문</h2><p className="st-section-lead">더 궁금한 점은 AI 상담에 물어보시거나 상담 접수로 남겨 주세요.</p></div>
        <div className="st-faq">{FAQ.map(f => <details key={f.q}><summary>{f.q}</summary><p>{f.a}</p></details>)}</div>
      </div></section>

      <section id="inquiry" className="st-section st-inquiry"><div className="st-wrap st-inquiry-grid">
        <div>
          <h2>상담 접수</h2>
          <p className="st-section-lead">AI 상담 대신 직접 적어 주셔도 됩니다. 지금 하고 있는 일, 바라는 결과, 예산과 일정을 아는 만큼만 적어 주세요.</p>
          <ul className="st-checks">
            <li>접수하면 확인 메일을 보내 드립니다</li>
            <li>담당자가 검토해 견적서 링크를 메일로 보내 드립니다</li>
            <li>상담과 견적은 무료입니다</li>
          </ul>
        </div>
        <InquiryForm />
      </div></section>
    </main>

    <footer className="st-footer"><div className="st-wrap">
      <strong>{SITE.name}</strong><p>{SITE.description}</p>
      <p className="st-footer-small">© {SITE.name}. 이 사이트의 데모와 체험에 쓰인 회사·거래 정보는 모두 가상입니다.</p>
    </div></footer>
  </div>;
}
