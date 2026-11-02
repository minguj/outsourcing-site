"use client";

import { BANK } from "../../site-config";
import { BLANK, DocShell, Loading, Signs, day, payments, useQuote, won } from "../doc-kit";

// 완료(검수) 확인서. 외주 개발 계약서의 "완료와 검수"·"잔금"·"산출물 인도" 조항을 실제로 확인하는 문서다.
const OUTPUTS = ["소스코드 (저장소 또는 압축 파일)", "운영 환경 배포", "설치·배포 방법", "운영 매뉴얼", "인수인계 문서"];

export default function CompletionView() {
  const { token, quote, error, ready } = useQuote(false);
  if (!ready) return <Loading error={error} />;

  const balance = quote ? won(payments(quote).balance) : `${BLANK}원`;
  return <DocShell title="완료 확인서" token={token}
    notice="과업을 마친 뒤 고객이 결과물을 확인하고 서명하는 완료(검수) 확인서입니다. 잔금 지급일과 하자보수 기간의 기준이 됩니다.">
    <h1 className="st-contract-title">완료(검수) 확인서</h1>
    <table className="st-table st-contract-pay"><tbody>
      <tr><th style={{ width: 140 }}>과업명</th><td>{quote ? quote.title : BLANK}</td></tr>
      <tr><th>계약 금액</th><td>{quote ? won(quote.total) : `${BLANK}원`}</td></tr>
      <tr><th>견적서 발행일</th><td>{quote ? day(quote.created_at) : `${BLANK}년　　월　　일`}</td></tr>
      <tr><th>완료 보고일</th><td>{BLANK}년　　월　　일</td></tr>
      <tr><th>검수 완료일</th><td>{BLANK}년　　월　　일</td></tr>
    </tbody></table>

    <h2 className="st-contract-section">1. 인도받은 산출물</h2>
    <ul className="st-checklist">{OUTPUTS.map(o => <li key={o}>☐ {o}</li>)}<li>☐ 기타: {BLANK}{BLANK}</li></ul>

    <h2 className="st-contract-section">2. 검수 결과</h2>
    <ul className="st-checklist">
      <li>☐ 이상 없음: 검수를 마쳤습니다.</li>
      <li>☐ 아래 사항을 보완한 뒤 완료합니다.</li>
    </ul>
    <div className="st-lines" aria-label="보완 사항"><span /><span /><span /></div>

    <h2 className="st-contract-section">3. 잔금과 하자보수</h2>
    <ul className="st-contract-items">
      <li>잔금 {balance}은(는) 완료 보고일부터 7일 이내에 을의 계좌({BANK.bank} {BANK.account}{BANK.holder ? `, 예금주 ${BANK.holder}` : ""})로 지급합니다.</li>
      <li>을은 잔금 지급일부터 3주 동안 결과물의 하자를 무상으로 보수합니다.</li>
      <li>잔금 지급이 끝나면 결과물의 소스코드와 저작권은 계약서에 따라 갑에게 넘어갑니다.</li>
    </ul>

    <p className="st-contract-closing">갑은 위와 같이 과업의 완료와 산출물 인도를 확인합니다.</p>
    <Signs quote={quote} clientRole="확인자" />
  </DocShell>;
}
