"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { BANK } from "../site-config";
import { Articles, DocShell, Loading, Parties, Signs, day, payments, useQuote, won } from "./doc-kit";

// 견적서(/quote?t=…)와 같은 토큰으로 그 견적 내용을 채운 외주 개발 계약서(안).
// 서명은 이 화면을 인쇄·PDF 저장하거나 Word로 저장해 주고받는다.
export default function ContractView() {
  const { token, quote, error } = useQuote(true);
  if (!quote) return <Loading error={error} />;

  const { middle, balance } = payments(quote);
  const quoteLink = `/quote?t=${encodeURIComponent(token)}`;
  const articles: [string, ReactNode][] = [
    ["목적", <>이 계약은 갑이 을에게 맡기는 「{quote.title}」 개발(이하 &ldquo;이 과업&rdquo;)에 관하여 갑과 을의 권리와 의무를 정하는 것을 목적으로 한다.</>],
    ["과업 범위", <>을이 수행할 과업은 {day(quote.created_at)} 발행한 견적서(<Link href={quoteLink}>견적서 보기</Link>)의 항목과 같다. 세부 기능과 화면은 착수 미팅에서 정하고, 정한 내용은 메일 등 기록이 남는 방법으로 서로 확인한다.
      <ul className="st-contract-items">{quote.items.map((item, i) => <li key={i}>{item.name} <span>{won(item.amount)}</span></li>)}</ul></>],
    ["계약 금액", <>계약 금액은 총 <strong>{won(quote.total)}</strong>으로 한다.</>],
    ["대금 지급", <>갑은 아래와 같이 을이 지정한 계좌({BANK.bank} {BANK.account}{BANK.holder ? `, 예금주 ${BANK.holder}` : ""})로 대금을 지급한다.
      <table className="st-table st-contract-pay"><thead><tr><th>구분</th><th>시기</th><th className="st-num">금액</th></tr></thead><tbody>
        <tr><td>착수금</td><td>계약 체결 후 7일 이내</td><td className="st-num">{won(quote.deposit)}</td></tr>
        <tr><td>중도금</td><td>전체 일정의 절반이 지난 시점(중간 시연 후 7일 이내)</td><td className="st-num">{won(middle)}</td></tr>
        <tr><td>잔금</td><td>완료 보고 후 7일 이내</td><td className="st-num">{won(balance)}</td></tr>
      </tbody></table></>],
    ["계약 기간", <>계약 기간은 계약일부터 {quote.schedule && quote.schedule !== "미정" ? `${quote.schedule}까지` : "착수 미팅에서 정한 완료일까지"}로 한다. 을은 착수 미팅 후 중간 시연 날짜가 들어간 일정표를 갑에게 보낸다. 갑의 자료 제공이 늦어지거나 과업 범위가 바뀌면 서로 협의해 일정을 조정한다.</>],
    ["갑의 협조", <>갑은 과업 수행에 필요한 자료(양식 예시, 업무 설명, 연동할 시스템의 접근 정보 등)를 제때 제공하고, 을의 확인 요청에 성실히 답한다.</>],
    ["범위 변경", <>진행 중 수정이나 범위 변경이 필요하면 갑과 을은 협의하여 변경 내용과 그에 따른 일정·비용을 정하고, 메일 등 기록이 남는 방법으로 확인한 뒤 진행한다.</>],
    ["완료와 검수", <>을은 과업을 마치면 갑에게 완료를 보고하고 결과물을 전달한다. 갑은 완료 보고를 받은 날부터 7일 이내에 결과물을 검수하고, 고칠 점이 있으면 그 기간 안에 구체적으로 알린다. 이 기간 안에 이의가 없으면 검수를 마친 것으로 본다.</>],
    ["소스코드와 저작권", <>잔금 지급이 끝나면 이 과업으로 만든 결과물의 소스코드와 저작권은 갑에게 넘어간다. 다만 을이 이 계약 전부터 보유했거나 여러 과업에 공통으로 쓰는 도구·라이브러리는 을에게 남고, 갑은 결과물을 사용하는 데 필요한 범위에서 이를 계속 쓸 수 있다.</>],
    ["산출물 인도와 인수인계", <>을은 납품할 때 소스코드, 설치·배포 방법, 운영 매뉴얼, 인수인계 문서를 갑에게 전달한다. 을은 갑이 다른 개발자에게 운영이나 유지보수를 맡기더라도 이어서 운영할 수 있도록 이 문서들을 작성하고, 잔금 지급일부터 3주 안에 갑이 요청하면 인수인계에 필요한 설명을 제공한다.</>],
    ["하자보수", <>을은 잔금 지급일부터 3주 동안 결과물의 하자를 무상으로 보수한다. 그 이후의 유지보수와 기능 추가는 월 구독형 유지보수 계약 등으로 별도로 정한다.</>],
    ["운영 비용", <>AI 사용료(토큰), 서버·도메인 등 외부 서비스 비용은 갑이 부담하며, 필요한 계정은 갑의 명의로 준비한다. 을이 서버를 위탁 운영하는 경우의 비용은 별도로 협의한다.</>],
    ["비밀유지", <>갑과 을은 이 계약으로 알게 된 상대방의 업무 정보와 자료를 상대방의 동의 없이 제3자에게 알리거나 이 과업 외의 목적으로 쓰지 않는다. 이 의무는 계약이 끝난 뒤에도 유지된다. 갑이 요청하면 별도의 비밀유지계약을 맺는다.</>],
    ["계약 해지", <>한쪽이 이 계약을 위반하고 상대방의 서면(메일 포함) 시정 요구를 받은 날부터 14일 안에 고치지 않으면 상대방은 계약을 해지할 수 있다. 계약이 해지되면 갑과 을은 해지 시점까지 수행한 과업의 비율에 따라 대금을 정산한다.</>],
    ["손해배상", <>갑 또는 을이 고의나 과실로 이 계약을 위반하여 상대방에게 손해를 입힌 경우 그 손해를 배상한다. 다만 을의 배상액은 이 계약에서 갑이 실제로 지급한 금액을 넘지 않는다.</>],
    ["기타", <>이 계약에서 정하지 않은 사항은 갑과 을이 협의하여 정하며, 협의가 되지 않으면 관련 법령과 일반 관례에 따른다. 이 계약과 관련한 분쟁은 먼저 협의로 해결하고, 소송이 필요하면 민사소송법에 따른 관할 법원에서 다툰다.</>],
  ];

  return <DocShell title="외주 개발 계약서(안)" token={token}
    notice="계약서(안)입니다. 내용을 확인하시고 고칠 점이 있으면 견적 메일에 회신해 주세요. 확정되면 서명할 계약서를 보내 드립니다.">
    <h1 className="st-contract-title">외주 개발 계약서(안)</h1>
    <Parties quote={quote} tail="다음과 같이 외주 개발 계약을 맺는다." />
    <Articles items={articles} />
    {quote.note && <p className="st-contract-note"><strong>견적서 안내 문구</strong><br />{quote.note}</p>}
    <p className="st-contract-closing">이 계약을 증명하기 위하여 계약서 2부를 작성하여 갑과 을이 서명 또는 날인한 뒤 각 1부씩 보관한다.</p>
    <Signs quote={quote} />
  </DocShell>;
}
