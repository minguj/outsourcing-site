"use client";

import type { ReactNode } from "react";
import { BANK } from "../../site-config";
import { Articles, BLANK, DocShell, Loading, Parties, Signs, useQuote } from "../doc-kit";
import { MAINTENANCE } from "./maintenance-data";

// 건별 요금 칸. 표 안에서 줄바꿈되지 않게 짧은 빈칸을 쓴다.
const FEE = "　　　　　";

// 월 구독형 유지보수 계약서. 플랜 구성은 maintenance-data.ts에 있다.
// 공개 화면(랜딩·FAQ·계약 문서 목록)에서는 링크하지 않고, 관리자 화면의 문서 바로가기로만 연다.
export default function MaintenanceView() {
  const { token, quote, error, ready } = useQuote(false);
  if (!ready) return <Loading error={error} />;

  const system = quote ? <>「{quote.title}」</> : <>{BLANK}{BLANK}</>;
  const articles: [string, ReactNode][] = [
    ["목적", <>이 계약은 을이 갑의 시스템 {system}(이하 &ldquo;대상 시스템&rdquo;)을 월 구독 방식으로 유지보수하는 데 필요한 조건을 정하는 것을 목적으로 한다.</>],
    ["플랜과 범위", <>갑은 아래 플랜 중 하나를 고르며, 을은 고른 플랜에 포함된 일을 수행한다. 모든 플랜에는 장애 감시와 대응, 보안 업데이트, 매일 백업과 월 1회 복구 점검, 월간 점검 보고가 포함된다.
      <table className="st-table st-contract-pay"><thead><tr><th style={{ width: 120 }}>선택</th><th>포함 내용</th><th style={{ width: 90 }}>월 포인트</th><th style={{ width: 100 }}>월 요금</th></tr></thead><tbody>
        {MAINTENANCE.plans.map(p => <tr key={p.name}><td>☐ {p.name}</td><td>{p.includes.join(", ")}</td><td>{p.points}점</td><td style={{ whiteSpace: "nowrap" }}>{p.price.replace("월 ", "")}</td></tr>)}
      </tbody></table></>],
    ["작업 등급과 포인트", <>갑이 요청한 작업은 아래 등급에 따라 그 달의 작업 포인트에서 차감한다.
      <table className="st-table st-contract-pay"><thead><tr><th style={{ width: 150 }}>등급</th><th>작업 예</th><th style={{ width: 90 }}>포인트</th><th style={{ width: 130 }}>건별 요금</th></tr></thead><tbody>
        {MAINTENANCE.levels.map(l => <tr key={l.name}><td>{l.code} {l.name}</td><td>{l.examples}</td><td>{l.points}</td>
          <td style={{ whiteSpace: "nowrap" }}>{l.code === "L1" || l.code === "L2" ? <>{FEE}원</> : l.code === "L3" ? <>{FEE}원부터</> : l.code === "L4" ? "사전 견적" : "별도 견적"}</td></tr>)}
      </tbody></table>
      <ol className="st-contract-items st-contract-rules">
        <li>을은 작업 전에 등급과 차감할 포인트를 알리고 갑의 동의를 받아 진행한다. 작업 중 등급을 바꿔야 하면 추가 작업 전에 다시 동의를 받는다.</li>
        <li>그 달에 쓰지 않은 포인트는 다음 달까지 한 번 이월되며, 그 뒤에는 소멸한다.</li>
        <li>포인트를 넘는 작업은 위 건별 요금으로 청구한다.</li>
        <li>을이 납품한 코드의 결함으로 생긴 오류는 계약 기간 중 포인트를 차감하지 않고 고친다.</li>
      </ol></>],
    ["범위 밖 작업", <>새 기능이나 새 시스템 개발, 새로운 외부 시스템 연동처럼 위 작업 등급에 해당하지 않는 작업은 별도로 견적을 내고 합의한 뒤 진행한다.</>],
    ["이용료와 지급", <>월 이용료는 갑이 고른 플랜의 월 요금({BLANK}원)으로 한다. 갑은 매 이용 기간이 시작되기 전까지 그 기간의 이용료를 을의 계좌({BANK.bank} {BANK.account}{BANK.holder ? `, 예금주 ${BANK.holder}` : ""})로 이체한다.</>],
    ["기간과 연장", <>이용 기간은 {BLANK}년　　월　　일부터 1개월 단위로 한다(보통 무상 하자보수 기간이 끝난 다음 날부터 시작한다). 어느 쪽도 종료 의사를 밝히지 않으면 같은 조건으로 1개월씩 자동으로 연장된다.</>],
    ["요청과 대응", <>갑은 장애나 작업 요청을 메일 등 기록이 남는 방법으로 접수한다. 을은 영업일 기준 요청 당일에 첫 응답을 하고(업무 시간이 끝난 뒤 들어온 요청은 다음 영업일), 서비스가 멈춘 장애는 다른 요청보다 먼저 처리한다. 처리 결과는 메일 등으로 알린다. 갑의 요청으로 야간·주말·공휴일에 작업하는 경우 차감 포인트나 건별 요금에 50%를 더한다. 다만 서비스가 멈춘 장애 대응에는 더하지 않는다.</>],
    ["운영 비용", <>AI 사용료(토큰), 서버·도메인 등 외부 서비스 비용은 갑이 부담하며, 필요한 계정은 갑의 명의로 준비한다. 을이 서버를 위탁 운영하는 경우의 비용은 별도로 협의한다.</>],
    ["해지", <>갑 또는 을은 다음 이용 기간이 시작되기 7일 전까지 메일 등으로 알리면 다음 기간부터 계약을 끝낼 수 있다. 이미 시작된 기간의 이용료는 돌려주지 않는다. 다만 을의 사정으로 그 기간에 유지보수를 하지 못한 경우에는 남은 일수만큼 일할 계산하여 돌려준다.</>],
    ["비밀유지", <>갑과 을은 이 계약으로 알게 된 상대방의 업무 정보와 자료를 상대방의 동의 없이 제3자에게 알리거나 이 계약 외의 목적으로 쓰지 않는다. 이 의무는 계약이 끝난 뒤에도 유지된다.</>],
    ["손해배상", <>갑 또는 을이 고의나 과실로 이 계약을 위반하여 상대방에게 손해를 입힌 경우 그 손해를 배상한다. 다만 을의 배상액은 손해가 생긴 날 이전 3개월 동안 갑이 실제로 지급한 이용료를 넘지 않는다.</>],
    ["기타", <>이 계약에서 정하지 않은 사항은 갑과 을이 협의하여 정한다. 이 계약과 관련한 분쟁은 먼저 협의로 해결하고, 소송이 필요하면 민사소송법에 따른 관할 법원에서 다툰다.</>],
  ];

  return <DocShell title="유지보수 계약서" token={token}
    notice="월 구독형 유지보수 계약서 양식입니다. 플랜, 월 이용료, 건별 요금, 시작일을 채운 뒤 인쇄·PDF 저장이나 Word로 저장해 서명하세요.">
    <h1 className="st-contract-title">유지보수(월 구독) 계약서</h1>
    <Parties quote={quote} tail="대상 시스템의 유지보수에 관하여 다음과 같이 계약을 맺는다." />
    <Articles items={articles} />
    <p className="st-contract-closing">이 계약을 증명하기 위하여 계약서 2부를 작성하여 갑과 을이 서명 또는 날인한 뒤 각 1부씩 보관한다.</p>
    <Signs quote={quote} />
  </DocShell>;
}
