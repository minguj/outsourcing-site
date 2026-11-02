// 회사 정보는 이 파일 한 곳에서 바꿉니다. 백엔드 상담봇 이름은 서버 환경변수 COMPANY_NAME과 맞춰 주세요.
export const SITE = {
  name: "핏에이전트",
  tagline: "기업 맞춤 AI 상담 에이전트와 문서 변환 툴 개발",
  description: "회사 업무에 맞춘 AI 상담 에이전트와 문서 변환·검수 툴, 사내 시스템 연동을 맡아 개발하는 외주 개발 서비스입니다.",
  privacy: {
    items: "이름, 회사명, 이메일, 전화번호(선택), 상담·의뢰 내용, 첨부 파일(선택)",
    // 수탁 업체 상세는 개인정보처리방침 페이지에 적는다:
    // Anthropic PBC(미국, AI 상담 답변 생성), Google LLC(미국, 메일 발송), Amazon Web Services(호주 시드니 리전, 서버 보관)
    transfer: "상담 응대와 견적 안내를 위해 일부 처리를 외부 업체(국외 포함)에 맡깁니다. 업체와 국가 등 자세한 내용은 개인정보처리방침에서 확인하실 수 있습니다.",
    purpose: "개발 의뢰 상담, 견적 안내와 연락",
    retention: "상담 종료 후 1년 보관 후 파기 (삭제를 요청하시면 즉시 파기)",
  },
};

// 영문 사이트(/en)용. 회사명은 영문 표기가 정해지면 name을 바꾼다.
export const SITE_EN = {
  name: "FitAgent",
  tagline: "Custom AI consultation agents and document conversion tools",
  description: "A development studio building AI consultation agents, document conversion and review tools, and internal system integrations tailored to your business.",
  privacy: {
    items: "Name, company, e-mail, phone (optional), consultation and request details, attachments (optional)",
    transfer: "To answer inquiries and send quotes, some processing is entrusted to outside providers, including providers abroad. See the privacy policy for the providers and countries.",
    purpose: "Consulting on development requests, sending quotes and contacting you",
    retention: "Kept for one year after the consultation ends, then destroyed (destroyed immediately on request)",
  },
};

// 카카오톡 문의 주소. 값을 넣으면 상담 접수 옆과 하단에 바로가기가 나온다. 비워 두면 숨긴다.
// 카카오톡 채널 채팅(https://pf.kakao.com/_xxxx/chat)이나 1:1 오픈채팅(https://open.kakao.com/o/xxxx) 주소를 넣는다.
export const CONTACT = {
  kakao: "",
};

// 실제 계약 대금(착수금·중도금·잔금)을 받는 계좌. 견적서 화면의 입금 안내에 나온다.
// 예금주(holder)를 적으면 계좌 아래에 함께 표시한다.
export const BANK = {
  bank: "토스뱅크",
  account: "1000-7205-2664",
  holder: "",
};

// 계약서(안)의 을(수급인). 프리랜서 계약이라 개인 이름으로 적는다.
// 개인정보처리방침·이용약관에 표시하는 운영자 정보와 시행일. 사업자등록이 없는 개인 운영이라 "대표" 대신 운영자 이름으로 표시한다.
// representative = 운영자(계약 당사자) 이름. 내용을 바꾸면 시행일도 함께 바꾼다.
export const OPERATOR = {
  brand: "핏에이전트",
  representative: "진민구",
  privacyOfficer: "진민구",
  email: "help@fitagent.co.kr",
  site: "fitagent.co.kr",
};
export const POLICY_EFFECTIVE = { privacy: "2026년 11월 2일", terms: "2026년 11월 2일" };

export const CONTRACTOR = {
  name: "진민구",
  brand: "핏에이전트",
};

export const siteFor = (lang: "ko" | "en") => (lang === "en" ? SITE_EN : SITE);
