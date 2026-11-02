// 검색·링크 미리보기에 쓰는 정식 주소.
export const SITE_URL = "https://fitagent.co.kr";

// 검색 등록 확인 코드. Google Search Console·네이버 서치어드바이저에서 "HTML 태그" 방식으로 받은 content 값만 넣는다.
export const SEARCH_VERIFY = { google: "", naver: "7e1fbaa24af177e04b8477a9040b280fc0cd4007" };

// 검색 키워드. 네이버 등은 참고하고 Google은 무시하므로, 실제 검색 노출은 본문 문구가 좌우한다.
export const KEYWORDS = [
  "외주 개발", "AI 상담 에이전트", "AI 챗봇 개발", "업무 자동화", "문서 자동화", "엑셀 자동화", "PDF 변환",
  "웹사이트 제작", "관리자 페이지 개발", "모바일 앱 개발", "결제 연동", "토스페이먼츠 연동", "프리랜서 개발자", "핏에이전트",
];

// 회사 정보는 이 파일 한 곳에서 바꿉니다. 백엔드 상담봇 이름은 서버 환경변수 COMPANY_NAME과 맞춰 주세요.
export const SITE = {
  name: "핏에이전트",
  tagline: "AI 상담·업무 자동화부터 웹사이트·앱 개발까지",
  description: "AI 상담 에이전트와 문서·업무 자동화부터 웹사이트, 관리자 페이지, 모바일 앱, 결제 연동까지 회사에 맞춰 개발하는 외주 개발 서비스입니다.",
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
  tagline: "From AI agents and workflow automation to websites and apps",
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
