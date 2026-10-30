"use client";

import Image from "next/image";
import Link from "next/link";
import { ConsultChat } from "./consult-chat";
import { InquiryForm } from "./inquiry-form";
import { SITE } from "../site-config";

const SERVICES = [
  { name: "AI 상담 에이전트", what: "자주 받는 문의, 주문, 견적 요청에 회사 규정대로 답하고 사람이 판단할 것만 담당자에게 넘깁니다.",
    examples: ["쇼핑몰 고객 문의 1차 응대", "B2B 견적·발주 접수", "사내 규정·업무 안내"] },
  { name: "문서 변환·검수 툴", what: "거래처마다 다른 발주서, 명세서, 주문 내역을 읽어 우리 양식으로 바꾸고, 빠지거나 틀린 값은 표시해 사람이 확인하게 합니다.",
    examples: ["발주서를 거래명세서로", "여러 채널 주문 엑셀 취합", "PDF 청구서 입력 자동화"] },
  { name: "시스템 연동", what: "만든 에이전트와 툴을 ERP, 쇼핑몰 관리자, 구글 시트, 메일과 이어서 손으로 옮겨 적는 단계를 없앱니다.",
    examples: ["ERP·회계 프로그램 입력", "쇼핑몰 주문 수집", "처리 결과 메일·메신저 알림"] },
];
const DEMO_TRIES = ["빠진 수량을 채우고 금액 차이를 확정하기", "마스터에 없는 품목을 그 자리에서 신규 등록하기", "취소된 주문을 되살려 다시 검수하기", "검수 결과를 거래처가 쓰는 원래 양식으로 회신하기"];
const STEPS = [
  { title: "상담", text: "AI 상담이나 문의 양식으로 업무와 목표를 정리합니다. 상담과 견적은 무료입니다." },
  { title: "견적", text: "담당자가 검토한 뒤 범위, 일정, 금액을 담은 견적서 링크를 보내 드립니다." },
  { title: "착수금 결제", text: "견적서 화면에서 바로 착수금을 결제하시면 개발을 시작합니다." },
  { title: "개발과 중간 시연", text: "실제 회사 문서와 문의 유형으로 중간 결과를 보여 드리고 함께 조정합니다." },
  { title: "납품과 안정화", text: "운영 환경에 설치하고, 안정화 기간 동안 실제 사용 결과를 보며 다듬습니다." },
];
const FAQ = [
  { q: "견적을 받기 전에 비용이 드나요?", a: "아니요. 상담과 견적은 무료이고, 견적에 동의하셔서 착수금을 결제하실 때부터 비용이 발생합니다." },
  { q: "회사 자료를 보내야 하나요?", a: "상담 단계에서는 실제 개인정보나 거래 자료 없이 양식 예시나 설명만으로 충분합니다. 실제 자료가 필요한 단계에서는 필요하면 비밀유지계약을 먼저 맺습니다." },
  { q: "작은 작업도 맡길 수 있나요?", a: "엑셀 양식 하나를 바꾸는 작은 작업부터 상담할 수 있습니다. 규모가 작으면 그만큼 짧은 일정과 금액으로 견적을 드립니다." },
  { q: "결제는 어떻게 하나요?", a: "견적서 링크에서 카드 등으로 착수금을 결제합니다. 나머지 금액과 방식은 견적서에 적어 드립니다." },
];

export default function Landing() {
  const goInquiry = () => document.getElementById("inquiry")?.scrollIntoView({ behavior: "smooth", block: "start" });
  return <div className="st-page">
    <header className="st-nav"><div className="st-wrap">
      <Link href="/" className="st-logo">{SITE.name}</Link>
      <nav aria-label="주요 메뉴"><a href="#services">서비스</a><a href="#demo">데모</a><a href="#process">진행 방식</a><a href="#inquiry" className="st-nav-cta">상담 접수</a></nav>
    </div></header>

    <main>
      <section className="st-hero"><div className="st-wrap st-hero-grid">
        <div className="st-hero-copy">
          <p className="st-hero-kicker">{SITE.tagline}</p>
          <h1>우리 회사 일을 아는 AI 상담사, 우리 양식에 맞는 문서 툴을 만듭니다</h1>
          <p className="st-lead">고객 문의에 답하는 상담 에이전트, 거래처마다 다른 엑셀과 PDF를 우리 양식으로 바꾸는 변환 툴을 회사 업무에 맞춰 개발합니다.</p>
          <p className="st-lead">옆의 상담 기록지가 바로 그 상담 에이전트예요. 맡기고 싶은 일을 말씀하시면 담당자가 볼 수 있게 정리해 드립니다.</p>
          <div className="st-hero-actions"><Link className="st-button" href="/demo/purchase-orders">발주서 변환 데모 해 보기</Link><button className="st-button st-button-ghost" onClick={goInquiry}>양식으로 문의하기</button></div>
        </div>
        <ConsultChat onFallback={goInquiry} />
      </div></section>

      <section id="services" className="st-section"><div className="st-wrap">
        <h2>맡길 수 있는 일</h2>
        <p className="st-section-lead">처음부터 범용 제품을 쓰는 대신, 회사가 이미 쓰는 문서와 규칙에 맞춰 만듭니다.</p>
        <div className="st-ledger" role="table" aria-label="서비스">
          <div className="st-ledger-head" role="row"><span role="columnheader">서비스</span><span role="columnheader">하는 일</span><span role="columnheader">예시</span></div>
          {SERVICES.map(s => <div className="st-ledger-row" role="row" key={s.name}>
            <h3 role="rowheader">{s.name}</h3><p role="cell">{s.what}</p><ul role="cell">{s.examples.map(e => <li key={e}>{e}</li>)}</ul>
          </div>)}
        </div>
      </div></section>

      <section id="demo" className="st-section st-demo"><div className="st-wrap st-demo-grid">
        <div>
          <h2>실제로 눌러 볼 수 있는 데모</h2>
          <p className="st-section-lead">가상의 거래처 세 곳이 보낸 서로 다른 발주서를 읽어, 우리 회사의 거래명세서 양식 하나로 바꿉니다. 문서 변환 툴을 맡기시면 이런 화면을 회사 문서에 맞춰 만들어 드려요.</p>
          <ul className="st-checks">{DEMO_TRIES.map(t => <li key={t}>{t}</li>)}</ul>
          <Link className="st-button" href="/demo/purchase-orders">데모 열기</Link>
        </div>
        <Link href="/demo/purchase-orders" className="st-demo-visual" aria-label="발주서 변환 데모 열기">
          <div className="st-demo-sources">{(["A", "B", "C"] as const).map((id, i) => <figure key={id} style={{ ["--i" as string]: i }}>
            <Image src={`/samples/purchase-orders/thumbnails/${id}.png`} alt={`${id} 거래처의 가상 발주서`} width={[850, 2470, 1270][i]} height={[1180, 660, 1140][i]} unoptimized />
            <figcaption><b>{id} 거래처</b>{["인쇄용 발주서", "쇼핑몰 주문 엑셀", "제조업 구매 발주서"][i]}</figcaption>
          </figure>)}</div>
          <div className="st-demo-target"><strong>거래명세서</strong><span>우리 회사 양식 하나로</span></div>
        </Link>
      </div></section>

      <section id="process" className="st-section"><div className="st-wrap">
        <h2>진행 방식</h2>
        <ol className="st-steps">{STEPS.map((s, i) => <li key={s.title} className={i === 2 ? "st-step-pay" : undefined}><span className="st-step-no" aria-hidden="true">{i + 1}</span><h3>{s.title}</h3><p>{s.text}</p></li>)}</ol>
      </div></section>

      <section id="inquiry" className="st-section st-inquiry"><div className="st-wrap st-inquiry-grid">
        <div>
          <h2>상담 접수</h2>
          <p className="st-section-lead">AI 상담 대신 직접 적어 주셔도 됩니다. 지금 하고 있는 일, 바라는 결과, 예산과 일정을 아는 만큼만 적어 주세요.</p>
          <div className="st-faq">{FAQ.map(f => <details key={f.q}><summary>{f.q}</summary><p>{f.a}</p></details>)}</div>
        </div>
        <InquiryForm />
      </div></section>
    </main>

    <footer className="st-footer"><div className="st-wrap">
      <strong>{SITE.name}</strong><p>{SITE.description}</p>
      <p className="st-footer-small">© {SITE.name}. 이 사이트의 데모에 쓰인 회사·거래 정보는 모두 가상입니다.</p>
    </div></footer>
  </div>;
}
