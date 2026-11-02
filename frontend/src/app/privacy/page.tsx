import type { Metadata } from "next";
import Link from "next/link";
import "../_site/site.css";
import { LegalPage, Section } from "../_legal/legal-page";
import { OPERATOR, POLICY_EFFECTIVE, SITE } from "../site-config";

export const metadata: Metadata = { title: `개인정보처리방침 | ${SITE.name}` };

// 개인정보처리방침. 수집 항목·위탁 업체·보유 기간을 바꾸면 site-config.ts의 privacy 안내문과 시행일도 함께 바꾼다.
const PROCESSORS = [
  { name: "Anthropic, PBC", country: "미국", work: "AI 상담 답변 생성", items: "AI 상담에 입력한 대화 내용", when: "AI 상담에서 메시지를 보낼 때마다 네트워크로 전송", keep: "답변 생성에 필요한 기간(업체의 데이터 보관 정책에 따름)", contact: "anthropic.com/legal/privacy" },
  { name: "Google LLC", country: "미국", work: "접수 확인·견적 안내 메일 발송과 수신", items: "이름, 회사명, 이메일, 상담·의뢰 내용, 견적 정보", when: "접수·견적 메일을 보내거나 받을 때 네트워크로 전송", keep: "보유 기간 동안(제3조와 같음)", contact: "policies.google.com/privacy" },
  { name: "Amazon Web Services, Inc.", country: "호주(시드니 리전)", work: "사이트 서버 운영과 상담 기록 보관", items: "제2조의 모든 항목", when: "상담 접수·견적 발행 시 서버에 저장", keep: "보유 기간 동안(제3조와 같음)", contact: "aws.amazon.com/privacy" },
];

export default function PrivacyPage() {
  return <LegalPage title="개인정보처리방침" effective={POLICY_EFFECTIVE.privacy}>
    <p className="st-legal-lead">{OPERATOR.representative}(이하 &ldquo;운영자&rdquo;)는 &lsquo;{OPERATOR.brand}&rsquo;라는 이름으로 운영하는 {OPERATOR.site}(이하 &ldquo;사이트&rdquo;)에서 개발 의뢰 상담과 견적·계약을 위해 개인정보를 처리하며, 개인정보 보호법에 따라 이용자의 개인정보를 보호하고 관련 고충을 처리하기 위하여 다음과 같이 개인정보처리방침을 둡니다.</p>

    <Section n={1} title="처리 목적">
      <ul><li>개발 의뢰 상담 접수와 응대(AI 상담 포함)</li><li>견적서 발행, 계약 체결과 이행, 대금 확인</li><li>접수 확인·견적 안내 등 필요한 연락</li><li>사이트 보안과 부정 이용 방지</li></ul>
    </Section>

    <Section n={2} title="처리하는 개인정보 항목">
      <table className="st-table"><thead><tr><th>구분</th><th>항목</th></tr></thead><tbody>
        <tr><td>상담 접수(필수)</td><td>이름, 이메일, 상담·의뢰 내용</td></tr>
        <tr><td>상담 접수(선택)</td><td>회사명, 전화번호, 첨부 파일, AI 상담 대화와 요약(함께 보내기를 선택한 경우)</td></tr>
        <tr><td>견적·계약</td><td>계약서에 적는 상호·주소·대표자 또는 성명, 입금 확인 정보(입금자명·금액·일자)</td></tr>
        <tr><td>자동 수집</td><td>접속 IP 주소, 접속 일시(서버 접속 기록), 쿠키, 방문·이용 기록(방문 경로, 본 페이지, 누른 버튼, 기기·브라우저 종류) (제7조)</td></tr>
      </tbody></table>
      <p>AI 상담 대화는 상담 접수 때 함께 보내기를 선택한 경우에만 저장합니다. 접수하지 않은 대화는 저장하지 않습니다. 운영자는 만 14세 미만 아동의 개인정보를 받지 않습니다.</p>
    </Section>

    <Section n={3} title="처리 및 보유 기간">
      <ul>
        <li>상담 접수 정보: 상담이 끝난 날부터 1년 동안 보관한 뒤 파기합니다. 삭제를 요청하시면 즉시 파기합니다.</li>
        <li>계약을 맺은 경우: 계약이 끝난 뒤 세법 등 관련 법령이 정한 기간 동안 보관합니다.</li>
        <li>서버 접속 기록: 보안과 장애 대응을 위해 정해진 용량만큼만 보관하고, 용량을 넘으면 오래된 기록부터 자동으로 삭제합니다.</li>
      </ul>
    </Section>

    <Section n={4} title="파기 절차와 방법">
      <p>보유 기간이 지나거나 처리 목적을 이룬 개인정보는 지체 없이 파기합니다. 전자 파일은 복구할 수 없는 방법으로 삭제하고, 종이 문서는 분쇄하거나 소각합니다. 법령에 따라 계속 보관해야 하는 정보는 다른 정보와 분리하여 보관합니다.</p>
    </Section>

    <Section n={5} title="제3자 제공">
      <p>운영자는 이용자의 개인정보를 제3자에게 제공하지 않습니다. 다만 법령에 특별한 규정이 있는 경우는 예외로 합니다.</p>
    </Section>

    <Section n={6} title="처리 위탁과 국외 이전">
      <p>운영자는 상담 응대와 견적·계약 이행을 위해 아래와 같이 개인정보 처리를 위탁하며, 위탁받는 업체가 국외에 있어 개인정보가 국외로 이전됩니다. 이는 이용자와의 계약 체결과 이행에 필요한 처리위탁·보관으로서 개인정보 보호법 제28조의8 제1항 제3호에 따라 이 처리방침에 공개합니다.</p>
      <div className="st-table-scroll"><table className="st-table"><thead><tr><th>이전받는 자(연락처)</th><th>국가</th><th>위탁 업무</th><th>이전 항목</th><th>이전 시기·방법</th><th>보유·이용 기간</th></tr></thead><tbody>
        {PROCESSORS.map(p => <tr key={p.name}><td>{p.name}<br /><small>{p.contact}</small></td><td>{p.country}</td><td>{p.work}</td><td>{p.items}</td><td>{p.when}</td><td>{p.keep}</td></tr>)}
      </tbody></table></div>
      <p>국외 이전을 원하지 않으시면 AI 상담과 상담 접수를 이용하지 않고 {OPERATOR.email}로 알려 주세요. 다만 메일 역시 위 업체를 통해 처리되므로, 이 경우 사이트를 통한 상담 진행이 어려울 수 있습니다.</p>
    </Section>

    <Section n={7} title="쿠키 등 자동 수집 장치">
      <ul>
        <li>관리자 로그인 쿠키: 운영자만 사용하는 관리 화면의 로그인 유지용입니다.</li>
        <li>발주서 변환 데모 쿠키: 데모 체험 세션을 30분 동안 유지하는 데만 씁니다.</li>
        <li>방문 분석 쿠키(Google Analytics): 사이트를 고쳐 나가기 위해 방문 경로, 본 페이지, 누른 버튼, 기기·브라우저 종류를 통계로 봅니다. 이름·연락처·상담 내용은 보내지 않으며, 견적서·계약서 화면에서는 수집하지 않습니다. 수집된 정보는 Google LLC(미국)가 처리하며, 운영자는 개인을 알아볼 수 없는 통계로만 확인합니다. 보관 기간은 14개월입니다.</li>
        <li>광고 쿠키는 쓰지 않습니다.</li>
      </ul>
      <p>브라우저 설정에서 쿠키 저장을 거부할 수 있으며, 이 경우 데모 체험 일부가 동작하지 않을 수 있습니다. 방문 분석만 거부하시려면 Google 애널리틱스 차단 브라우저 부가기능(tools.google.com/dlpage/gaoptout)을 설치하시면 됩니다.</p>
    </Section>

    <Section n={8} title="정보주체의 권리와 행사 방법">
      <p>이용자는 언제든지 자신의 개인정보 열람, 정정·삭제, 처리정지를 요구하거나 동의를 철회할 수 있습니다. {OPERATOR.email}로 요청하시면 본인 확인 후 10일 이내에 처리하고 결과를 알려 드립니다. 대리인을 통해서도 요청할 수 있습니다. 법령에서 보관하도록 정한 정보는 삭제를 요구할 수 없습니다.</p>
    </Section>

    <Section n={9} title="안전성 확보 조치">
      <ul>
        <li>사이트의 모든 통신은 HTTPS로 암호화합니다.</li>
        <li>관리 화면은 비밀번호로 보호하고 로그인 시도 횟수를 제한합니다.</li>
        <li>서버 접속은 허용한 주소에서만 가능하게 제한하고, 비밀번호·인증 키는 소스코드와 분리하여 보관합니다.</li>
        <li>개인정보를 다루는 사람은 운영자 1인으로 한정합니다.</li>
      </ul>
    </Section>

    <Section n={10} title="개인정보 보호책임자">
      <p>개인정보 처리에 관한 문의, 불만, 피해 구제는 아래로 연락해 주세요.</p>
      <ul><li>개인정보 보호책임자: {OPERATOR.privacyOfficer}</li><li>이메일: <a href={`mailto:${OPERATOR.email}`}>{OPERATOR.email}</a></li></ul>
    </Section>

    <Section n={11} title="권익침해 구제 방법">
      <p>개인정보 침해에 대한 상담이나 분쟁 해결이 필요하시면 아래 기관에 문의하실 수 있습니다.</p>
      <ul>
        <li>개인정보분쟁조정위원회: 1833-6972 (www.kopico.go.kr)</li>
        <li>개인정보침해신고센터: 118 (privacy.kisa.or.kr)</li>
        <li>대검찰청: 1301 (www.spo.go.kr)</li>
        <li>경찰청: 182 (ecrm.police.go.kr)</li>
      </ul>
    </Section>

    <Section n={12} title="처리방침의 변경">
      <p>이 처리방침은 {POLICY_EFFECTIVE.privacy}부터 적용합니다. 내용이 바뀌면 시행 7일 전에 사이트에 알리고, 이용자 권리에 중요한 변경은 30일 전에 알립니다. 이용약관과 환불 기준은 <Link href="/terms">이용약관·환불 규정</Link>을 확인해 주세요.</p>
    </Section>
  </LegalPage>;
}
