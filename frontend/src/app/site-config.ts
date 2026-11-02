// 회사 정보는 이 파일 한 곳에서 바꿉니다. 백엔드 상담봇 이름은 서버 환경변수 COMPANY_NAME과 맞춰 주세요.
export const SITE = {
  name: "핏에이전트",
  tagline: "기업 맞춤 AI 상담 에이전트와 문서 변환 툴 개발",
  description: "회사 업무에 맞춘 AI 상담 에이전트와 문서 변환·검수 툴, 사내 시스템 연동을 개발하는 외주 개발사입니다.",
  privacy: {
    items: "이름, 회사명, 이메일, 전화번호(선택), 상담·의뢰 내용, 첨부 파일(선택)",
    transfer: "AI 상담 대화는 답변을 만들기 위해 Anthropic PBC(미국)로 전송됩니다. 접수·견적 알림 메일은 Google LLC(미국)의 Gmail로 발송되고, 상담 기록은 Amazon Web Services 서버에 보관됩니다.",
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
    transfer: "AI chat messages are sent to Anthropic PBC (USA) to generate replies. Notification e-mails are sent through Google LLC (USA) Gmail, and records are stored on Amazon Web Services servers.",
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
export const CONTRACTOR = {
  name: "진민구",
  brand: "핏에이전트",
};

export const siteFor = (lang: "ko" | "en") => (lang === "en" ? SITE_EN : SITE);
