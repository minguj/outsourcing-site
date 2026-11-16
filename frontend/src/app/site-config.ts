// 검색·링크 미리보기에 쓰는 정식 주소.
export const SITE_URL = "https://fitagent.co.kr";

// 방문 분석. Google Analytics 4 측정 ID(G-로 시작)를 넣으면 공개 페이지에서만 수집을 시작한다.
export const ANALYTICS = { ga: "G-628KHERQN6" };

// 검색 등록 확인 코드. Google Search Console·네이버 서치어드바이저에서 "HTML 태그" 방식으로 받은 content 값만 넣는다.
export const SEARCH_VERIFY = { google: "", naver: "7e1fbaa24af177e04b8477a9040b280fc0cd4007" };

// 검색 키워드. 네이버 등은 참고하고 Google은 무시하므로, 실제 검색 노출은 본문 문구가 좌우한다.
export const KEYWORDS = [
  "AI 상담 접수", "AI 상담 시스템", "상담 자동화", "문의 응대 자동화", "AI 챗봇 상담", "상담 요약",
  "견적서 자동화", "온라인 계약", "결제 연동", "고객 문의 관리", "핏에이전트",
];

// 회사 정보는 이 파일 한 곳에서 바꿉니다. 백엔드 상담봇 이름은 서버 환경변수 COMPANY_NAME과 맞춰 주세요.
export const SITE = {
  name: "핏에이전트",
  tagline: "문의 응대를 자동화하는 AI 상담 접수",
  description: "AI가 고객 문의에 답하고 상담 내용을 요약해 접수한 뒤, 견적서·계약·결제까지 이어 주는 AI 상담 접수 시스템입니다. 실제로 동작하는 데모를 직접 써 볼 수 있습니다.",
  privacy: {
    items: "이름, 회사명, 이메일, 전화번호(선택), 상담·문의 내용, 첨부 파일(선택)",
    // 수탁 업체 상세는 개인정보처리방침 페이지에 적는다:
    // Anthropic PBC(미국, AI 상담 답변 생성·운영 플랫폼 데모 민원 분류), Google LLC(미국, 메일 발송), Amazon Web Services(호주 시드니 리전, 서버 보관)
    transfer: "데모 상담 응대와 도입 문의 안내를 위해 일부 처리를 외부 업체(국외 포함)에 맡깁니다. 업체와 국가 등 자세한 내용은 개인정보처리방침에서 확인하실 수 있습니다.",
    purpose: "AI 상담 접수 시스템 데모 상담·도입 문의 응대와 연락",
    retention: "상담 종료 후 1년 보관 후 파기 (삭제를 요청하시면 즉시 파기)",
  },
};

// 영문 사이트(/en)용. 회사명은 영문 표기가 정해지면 name을 바꾼다.
export const SITE_EN = {
  name: "FitAgent",
  tagline: "AI consultation intake that automates inquiry handling",
  description: "An AI consultation intake system that answers customer inquiries, summarizes them for your staff, and carries them through to quotes, contracts and payment. Try the working demo.",
  privacy: {
    items: "Name, company, e-mail, phone (optional), consultation and inquiry details, attachments (optional)",
    transfer: "To answer demo consultations and adoption inquiries, some processing is entrusted to outside providers, including providers abroad. See the privacy policy for the providers and countries.",
    purpose: "Answering demo consultations and adoption inquiries, and contacting you",
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

// 개인정보처리방침·이용약관에 표시하는 운영자 정보와 시행일. 사업자등록이 없는 개인 운영이라 "대표" 대신 운영자 이름으로 표시한다.
// representative = 운영자(계약 당사자) 이름. 내용을 바꾸면 시행일도 함께 바꾼다.
export const OPERATOR = {
  brand: "핏에이전트",
  representative: "진민구",
  privacyOfficer: "진민구",
  email: "help@fitagent.co.kr",
  site: "fitagent.co.kr",
};
export const POLICY_EFFECTIVE = { privacy: "2026년 11월 16일", terms: "2026년 11월 2일" };

// 계약서(안)의 을(수급인). 공개 데모 문서라 개인 이름은 넣지 않고 서비스명만 표시하고, 성명은 빈칸으로 둔다.
export const CONTRACTOR = {
  brand: "핏에이전트",
};

export const siteFor = (lang: "ko" | "en") => (lang === "en" ? SITE_EN : SITE);
