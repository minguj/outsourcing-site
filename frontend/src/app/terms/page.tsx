import type { Metadata } from "next";
import Link from "next/link";
import "../_site/site.css";
import { LegalPage, Section } from "../_legal/legal-page";
import { OPERATOR, POLICY_EFFECTIVE, SITE } from "../site-config";

export const metadata: Metadata = { title: `이용약관·환불 규정 | ${SITE.name}` };

// 이용약관과 환불·정산 기준. 금액·기간 기준을 바꾸면 계약서(contract/)와 site_knowledge.py의 운영 기준도 함께 맞춘다.
export default function TermsPage() {
  return <LegalPage title="이용약관·환불 규정" effective={POLICY_EFFECTIVE.terms}>
    <Section n={1} title="목적">
      <p>이 약관은 {OPERATOR.brand}(대표 {OPERATOR.representative}, 이하 &ldquo;운영자&rdquo;)가 운영하는 {OPERATOR.site}(이하 &ldquo;사이트&rdquo;)의 이용 조건과, 사이트를 통해 의뢰한 외주 개발 용역의 대금 지급·환불 기준을 정합니다.</p>
    </Section>

    <Section n={2} title="운영자 정보">
      <ul><li>상호: {OPERATOR.brand}</li><li>대표: {OPERATOR.representative}</li><li>이메일: <a href={`mailto:${OPERATOR.email}`}>{OPERATOR.email}</a></li><li>계약 형태: 개인(프리랜서) 용역 계약</li></ul>
    </Section>

    <Section n={3} title="사이트 이용">
      <ul>
        <li>상담과 견적은 무료입니다.</li>
        <li>AI 상담의 답변은 참고용 안내입니다. 범위, 일정, 금액 등 확정 조건은 운영자가 보내는 견적서와 서명한 계약서에 따릅니다.</li>
        <li>이용자는 사실과 다른 정보나 다른 사람의 정보를 입력하거나, 법령에 어긋나는 자료를 보내서는 안 됩니다.</li>
      </ul>
    </Section>

    <Section n={4} title="체험 기능">
      <ul>
        <li>&lsquo;견적·결제 흐름 체험&rsquo;은 실제로 청구되지 않는 예시이며, 체험용 견적서는 2시간 뒤 자동으로 사라집니다.</li>
        <li>발주서 변환 데모는 사이트가 제공하는 가상 샘플만 사용하며, 체험 내용은 30분 뒤 자동으로 사라집니다.</li>
      </ul>
    </Section>

    <Section n={5} title="계약의 성립">
      <p>견적서 내용에 합의하고 계약서에 서명하면 계약이 성립합니다. 견적서 발행이나 상담 접수만으로는 계약이 성립하지 않습니다. 이 약관과 계약서의 내용이 다르면 계약서가 우선합니다.</p>
    </Section>

    <Section n={6} title="대금 지급">
      <p>대금은 착수금 30%(계약서 작성 후), 중도금 50%(전체 일정의 절반이 지난 시점), 잔금 20%(완료 보고 후 7일 이내)로 나누어 계좌이체로 받습니다. 견적서의 &lsquo;결제&rsquo; 버튼은 결제 연동 예시이며 실제 대금 지급 수단이 아닙니다.</p>
    </Section>

    <Section n={7} title="환불·정산 기준">
      <table className="st-table"><thead><tr><th style={{ width: "34%" }}>상황</th><th>기준</th></tr></thead><tbody>
        <tr><td>계약 후 착수 전에 이용자가 취소</td><td>착수금을 돌려드립니다. 다만 이용자의 요청으로 이미 한 작업(요구사항 정리, 기획 등)이 있으면 그 비용을 뺀 금액을 돌려드립니다.</td></tr>
        <tr><td>진행 중 이용자의 사정으로 해지</td><td>해지 시점까지 수행한 과업의 비율로 정산합니다. 이미 낸 금액이 더 많으면 차액을 돌려드리고, 적으면 부족한 금액을 청구합니다.</td></tr>
        <tr><td>운영자의 사정으로 해지하거나 수행할 수 없게 된 경우</td><td>받은 금액 중 수행하지 못한 부분에 해당하는 금액을 모두 돌려드립니다.</td></tr>
        <tr><td>검수를 마친 뒤</td><td>환불 대상이 아닙니다. 결과물의 하자는 잔금 지급일부터 3주 동안 무상으로 보수합니다.</td></tr>
        <tr><td>월 구독 유지보수</td><td>다음 이용 기간 시작 7일 전까지 알리면 다음 기간부터 해지됩니다. 이미 시작된 기간의 이용료는 돌려드리지 않지만, 운영자의 사정으로 유지보수를 하지 못한 기간은 일할 계산하여 돌려드립니다.</td></tr>
      </tbody></table>
      <p>돌려드릴 금액이 정해지면 7일 이내에 이용자가 알려 주신 계좌로 보내 드립니다.</p>
    </Section>

    <Section n={8} title="지식재산권">
      <p>사이트에 실린 글, 디자인, 데모의 권리는 운영자에게 있습니다. 의뢰받아 만든 결과물의 소스코드와 저작권은 계약서에 따라 잔금 지급이 끝나면 이용자에게 넘어갑니다.</p>
    </Section>

    <Section n={9} title="책임의 제한">
      <p>운영자는 천재지변, 외부 서비스(클라우드·메일·AI 등)의 장애처럼 운영자가 통제할 수 없는 사유로 사이트를 일시적으로 이용할 수 없는 경우 그에 대한 책임을 지지 않습니다. 다만 운영자의 고의나 과실로 생긴 손해는 예외로 합니다.</p>
    </Section>

    <Section n={10} title="개인정보 보호">
      <p>개인정보 처리에 관한 사항은 <Link href="/privacy">개인정보처리방침</Link>에 따릅니다.</p>
    </Section>

    <Section n={11} title="약관의 변경">
      <p>약관을 바꾸는 경우 시행 7일 전에 사이트에 알립니다. 이미 맺은 계약에는 계약 당시의 계약서가 적용됩니다.</p>
    </Section>

    <Section n={12} title="분쟁 해결">
      <p>이 약관과 관련한 분쟁은 먼저 협의로 해결하고, 소송이 필요하면 민사소송법에 따른 관할 법원에서 다툽니다.</p>
    </Section>

    <p className="st-legal-meta">부칙: 이 약관은 {POLICY_EFFECTIVE.terms}부터 시행합니다.</p>
  </LegalPage>;
}
