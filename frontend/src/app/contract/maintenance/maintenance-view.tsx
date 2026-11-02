"use client";

import type { ReactNode } from "react";
import { BANK } from "../../site-config";
import { MAINTENANCE } from "../../site-content";
import { Articles, BLANK, DocShell, Loading, Parties, Signs, useQuote } from "../doc-kit";

// 월 구독형 유지보수 계약서. 플랜 구성은 메인의 '유지보수' 섹션(site-content.ts MAINTENANCE)과 같다.
export default function MaintenanceView() {
  const { token, quote, error, ready } = useQuote(false);
  if (!ready) return <Loading error={error} />;

  const system = quote ? <>「{quote.title}」</> : <>{BLANK}{BLANK}</>;
  const articles: [string, ReactNode][] = [
    ["목적", <>이 계약은 을이 갑의 시스템 {system}(이하 &ldquo;대상 시스템&rdquo;)을 월 구독 방식으로 유지보수하는 데 필요한 조건을 정하는 것을 목적으로 한다.</>],
    ["플랜과 범위", <>갑은 아래 플랜 중 하나를 고르며, 을은 고른 플랜에 포함된 일을 수행한다.
      <table className="st-table st-contract-pay"><thead><tr><th style={{ width: 120 }}>선택</th><th>포함 내용</th></tr></thead><tbody>
        {MAINTENANCE.plans.map(p => <tr key={p.name}><td>☐ {p.name}</td><td>{p.includes.join(", ")}</td></tr>)}
      </tbody></table></>],
    ["범위 밖 작업", <>새 기능이나 화면 추가, 큰 구조 변경, 새로운 외부 시스템 연동처럼 플랜에 포함되지 않은 작업은 별도로 견적을 내고 합의한 뒤 진행한다.</>],
    ["이용료와 지급", <>월 이용료는 {BLANK}원으로 한다. 갑은 매 이용 기간이 시작되기 전까지 그 기간의 이용료를 을의 계좌({BANK.bank} {BANK.account}{BANK.holder ? `, 예금주 ${BANK.holder}` : ""})로 이체한다.</>],
    ["기간과 연장", <>이용 기간은 {BLANK}년　　월　　일부터 1개월 단위로 한다(보통 무상 하자보수 기간이 끝난 다음 날부터 시작한다). 어느 쪽도 종료 의사를 밝히지 않으면 같은 조건으로 1개월씩 자동으로 연장된다.</>],
    ["요청과 대응", <>갑은 장애나 작업 요청을 메일 등 기록이 남는 방법으로 접수한다. 을은 영업일 기준 1일 안에 첫 응답을 하고, 서비스가 멈춘 장애는 다른 요청보다 먼저 처리한다. 처리 결과는 메일 등으로 알린다.</>],
    ["운영 비용", <>AI 사용료(토큰), 서버·도메인 등 외부 서비스 비용은 갑이 부담하며, 필요한 계정은 갑의 명의로 준비한다. 을이 서버를 위탁 운영하는 경우의 비용은 별도로 협의한다.</>],
    ["해지", <>갑 또는 을은 다음 이용 기간이 시작되기 7일 전까지 메일 등으로 알리면 다음 기간부터 계약을 끝낼 수 있다. 이미 시작된 기간의 이용료는 돌려주지 않는다. 다만 을의 사정으로 그 기간에 유지보수를 하지 못한 경우에는 남은 일수만큼 일할 계산하여 돌려준다.</>],
    ["비밀유지", <>갑과 을은 이 계약으로 알게 된 상대방의 업무 정보와 자료를 상대방의 동의 없이 제3자에게 알리거나 이 계약 외의 목적으로 쓰지 않는다. 이 의무는 계약이 끝난 뒤에도 유지된다.</>],
    ["손해배상", <>갑 또는 을이 고의나 과실로 이 계약을 위반하여 상대방에게 손해를 입힌 경우 그 손해를 배상한다. 다만 을의 배상액은 손해가 생긴 날 이전 3개월 동안 갑이 실제로 지급한 이용료를 넘지 않는다.</>],
    ["기타", <>이 계약에서 정하지 않은 사항은 갑과 을이 협의하여 정한다. 이 계약과 관련한 분쟁은 먼저 협의로 해결하고, 소송이 필요하면 민사소송법에 따른 관할 법원에서 다툰다.</>],
  ];

  return <DocShell title="유지보수 계약서" token={token}
    notice="월 구독형 유지보수 계약서 양식입니다. 플랜, 월 이용료, 시작일을 채운 뒤 인쇄·PDF 저장이나 Word로 저장해 서명하세요.">
    <h1 className="st-contract-title">유지보수(월 구독) 계약서</h1>
    <Parties quote={quote} tail="대상 시스템의 유지보수에 관하여 다음과 같이 계약을 맺는다." />
    <Articles items={articles} />
    <p className="st-contract-closing">이 계약을 증명하기 위하여 계약서 2부를 작성하여 갑과 을이 서명 또는 날인한 뒤 각 1부씩 보관한다.</p>
    <Signs quote={quote} />
  </DocShell>;
}
