// 화면에 보이는 서비스·진행 방식·자주 묻는 질문. AI 상담봇이 아는 같은 내용은 backend/site_knowledge.py 에 있다.
// 문구를 바꿀 때는 두 곳을 함께 맞춘다.

// 영문 사이트(/en) 문구는 아래 *_EN 에 있다. AI 상담봇은 한국어 정보를 영어로 옮겨 답한다.
import type { Lang } from "./_site/i18n";

export type Service = { id: string; name: string; what: string; examples: string[] };
// chip: false 인 질문은 아래 자주 묻는 질문 목록에만 보이고 상담 기록지 버튼으로는 나오지 않는다.
export type Faq = { q: string; a: string; chip?: boolean };

export const SERVICES: Service[] = [
  { id: "web", name: "웹사이트·관리자 페이지", what: "회사·서비스 소개 사이트와 예약·주문·문의 접수 화면, 직원이 쓰는 관리자 페이지를 만듭니다.",
    examples: ["서비스 소개·랜딩 페이지", "주문·예약 접수와 관리자 목록", "검색·상태 관리·엑셀 내려받기"] },
  { id: "app", name: "모바일 앱", what: "고객용·사내용 모바일 앱과 앱이 쓰는 서버 API, 관리자 페이지를 함께 만듭니다.",
    examples: ["중고거래·커뮤니티 앱", "학교·기관 안내 앱", "현장 작업 기록 앱과 관리자 페이지"] },
  { id: "payment", name: "결제 연동", what: "토스페이먼츠 등 결제창을 붙이고, 서버에서 결제를 검증해 완료 알림까지 이어지게 합니다.",
    examples: ["견적서에서 바로 착수금 결제", "주문 결제와 결제 완료 메일", "정기결제·환불 처리"] },
  { id: "docs", name: "문서 변환·자동화", what: "거래처마다 다른 엑셀·PDF를 읽어 우리 양식으로 바꾸고, 틀리거나 빠진 값은 사람이 확인하게 합니다.",
    examples: ["발주서를 거래명세서로", "여러 채널 주문 엑셀 취합", "PDF 청구서 입력 자동화"] },
  { id: "ai", name: "AI 에이전트 세팅", what: "회사 규정과 자료를 바탕으로 문의에 답하고, 상담 내용을 정리해 담당자에게 넘기는 AI를 세팅합니다.",
    examples: ["고객 문의 1차 응대", "견적·발주 상담 정리", "사내 규정·업무 안내"] },
  { id: "infra", name: "배포·인프라 구축", what: "AWS나 네이버 클라우드, 회사 내부 서버(온프레미스)를 구성하고, GitHub·Bitbucket에 올리면 자동으로 무중단 배포되게 설정합니다.",
    examples: ["AWS·NCP·온프레미스 서버와 Docker", "GitHub·Bitbucket 연동 무중단 자동 배포", "도메인·HTTPS·백업과 되돌리기"] },
];

export const PROCESS = [
  { title: "상담", text: "AI 상담이나 문의 양식으로 업무와 목표, 예산과 일정을 정리합니다. 상담과 견적은 무료이고, 화상·방문 미팅 모두 가능합니다." },
  { title: "견적", text: "담당자가 검토한 뒤 범위, 일정, 금액을 담은 견적서 링크를 메일로 보내 드립니다." },
  { title: "계약과 착수금", text: "견적에 합의하시면 계약서를 작성하고, 착수금(30%)이 계좌이체로 입금되면 착수 일정을 잡습니다." },
  { title: "개발과 중간 시연", text: "실제 회사 문서와 문의 유형으로 중간 결과를 보여 드리고 함께 조정합니다. 일정의 절반이 지나면 중도금(50%)을 정산합니다." },
  { title: "납품과 안정화", text: "운영 환경에 배포하고 완료 보고 후 7일 안에 잔금(20%)을 정산합니다. 잔금 후 3주간 무상으로 하자를 보수합니다." },
];

export const FAQ: Faq[] = [
  { q: "견적은 어떻게 받나요?", a: "AI 상담이나 문의 양식으로 하고 싶은 일, 예산, 일정을 남겨 주시면 담당자가 검토해 견적서 링크를 메일로 보내 드립니다. 상담과 견적은 무료이고, 범위가 모호하면 미팅으로 함께 정합니다." },
  { q: "신청은 어떻게 하나요?", a: "이 페이지의 AI 상담에서 대화로 내용을 정리하거나, 아래 상담 접수 양식에 직접 적어 주세요. 기획서나 참고 자료가 있으면 파일로 첨부할 수 있습니다. 접수되면 확인 메일이 가고, 담당자가 연락드립니다." },
  { q: "주로 어떤 프로젝트를 하나요?", a: "회사 업무에 맞춘 AI 상담 에이전트와 문서 변환·자동화 툴 외에도, 그와 함께 필요한 웹사이트·관리자 페이지, 모바일 앱, 결제 연동, 서버 배포까지 한 번에 맡을 수 있습니다." },
  { q: "어떤 개발 경력이 있나요?", a: "삼성전자 시스템 소프트웨어 개발, 중고거래 마켓·학교 앱 같은 모바일 앱, 재고·주문 관리 시스템(웹·관리자 페이지·DB), 현장 설비·작업 관리 시스템(API·DB·관리자 페이지)을 개발했습니다. 필요한 경우 소스 관리와 배포 파이프라인 구축까지 함께 진행했습니다." },
  { q: "기간은 얼마나 걸리나요?", a: "서버 개발을 포함한 사이트와 관리자 페이지는 2주~1개월 정도입니다. 범위와 자료 준비에 따라 달라지고, 확정 일정은 견적서로 안내드립니다. 바로 착수할 수 있는지는 접수 후 알려 드립니다." },
  { q: "결제는 어떻게 하나요?", a: "계약서를 작성한 뒤 착수금 30%가 입금되면 개발을 시작하고, 중도금 50%는 전체 일정의 절반이 지난 시점에, 잔금 20%는 완료 보고 후 7일 안에 받습니다. 모두 계좌이체로 정산합니다. 메인의 '견적·결제 흐름 체험'은 사이트에 넣어 드릴 수 있는 온라인 결제 예시입니다." },
  { q: "기획서나 디자인이 없어도 되나요?", a: "네, 없어도 맡기실 수 있습니다. 다만 기획과 디자인을 함께 확정하는 과정이 필요해서, 그만큼의 비용과 기간이 견적에 추가됩니다." },
  { q: "서버나 배포도 맡길 수 있나요?", a: "AWS나 네이버 클라우드뿐 아니라 회사 내부 서버(온프레미스) 환경에도 배포할 수 있습니다. GitHub, Bitbucket 등에 코드를 올리면 자동으로 무중단 배포되도록 설정해 드립니다. 이미 쓰는 서버가 있으면 그 환경에 맞춥니다." },
  { q: "비용은 어떻게 정해지나요?", a: "만들 범위와 연동할 시스템, 기획·디자인 확정 여부에 따라 달라서 상담 내용을 보고 견적으로 안내드립니다. 작은 변환 툴 하나부터 사이트·결제·AI를 묶은 프로젝트까지 단계를 나눠 진행할 수도 있습니다.", chip: false },
  { q: "세금계산서 발행이 되나요?", a: "모든 프로젝트는 프리랜서 계약으로 진행합니다. 세금계산서가 꼭 필요한 경우 별도로 문의해 주세요.", chip: false },
  { q: "진행 중에 수정하거나 범위를 바꿀 수 있나요?", a: "진행하면서 수정 사항이나 범위 변경이 생길 수 있습니다. 이 경우 함께 협의해 일정과 비용을 조정합니다.", chip: false },
  { q: "납품 후 소스코드는 누구 소유인가요?", a: "납품 후 소스코드와 저작권은 의뢰하신 회사에 넘겨 드립니다.", chip: false },
  { q: "하자보수나 유지보수는 어떻게 되나요?", a: "잔금 완료 후 3주 동안 무상으로 하자를 보수해 드립니다. 완료 보고 후 검수 1주를 더하면 납품부터 약 한 달입니다. 그 뒤에는 월 구독형 유지보수로 이어서 맡기실 수 있습니다.", chip: false },
  { q: "월 구독형 유지보수는 어떻게 되나요?", a: "납품 후에도 양식 변경, 예외 처리, AI 답변 개선처럼 손볼 일이 생깁니다. 월 구독으로 장애 대응과 점검, 작은 수정, AI 개선을 맡기실 수 있고, 플랜과 금액은 운영 규모를 보고 안내드립니다. 메인의 '유지보수' 메뉴에서 플랜 구성을 보실 수 있습니다.", chip: false },
  { q: "1인 회사인데 문제가 생기면 어떻게 하나요?", a: "납품할 때 소스코드와 함께 설치·배포 방법, 운영 매뉴얼, 인수인계 문서를 드리고 이 내용을 계약서에 넣습니다. 다른 개발자가 이어받아도 운영할 수 있게 정리해 드립니다.", chip: false },
  { q: "서버비나 AI 사용료는 누가 내나요?", a: "AI 에이전트의 AI 사용료(토큰)는 의뢰하신 회사에서 결제·충전한 계정을 제공해 주셔야 합니다. 서버를 저희가 위탁 운영하면 기본 위탁 운영비에 규모·설계에 따른 비용이 추가되고, 서버를 직접 운영하시고 개발만 맡기시면 운영비는 들지 않습니다.", chip: false },
  { q: "모바일 앱도 만드나요?", a: "네, 모바일 앱과 앱이 쓰는 서버 API, 관리자 페이지까지 함께 만들 수 있습니다.", chip: false },
  { q: "미팅은 어떻게 하나요?", a: "화상 미팅과 방문 미팅 모두 가능합니다. 접수 후 담당자가 편하신 방식으로 일정을 잡아 드립니다.", chip: false },
  { q: "회사 자료를 보내야 하나요?", a: "상담 단계에서는 실제 개인정보나 거래 자료 없이 양식 예시나 설명만으로 충분합니다. 요청하시면 계약서와 함께 비밀유지계약(NDA)을 맺고 실제 자료를 받습니다.", chip: false },
  { q: "맡기기 어려운 일도 있나요?", a: "대부분의 업무는 상담으로 범위를 정해 진행할 수 있습니다. 특정 분야의 전문 지식이 많이 필요한 업무는 내용을 남겨 주시면 검토 후 1영업일 이내에 진행 가능 여부와 방법을 회신드립니다.", chip: false },
];

export const SERVICES_EN: Service[] = [
  { id: "web", name: "Websites & admin pages", what: "Company and service sites, booking, order and inquiry screens, and admin pages your staff use every day.",
    examples: ["Service and landing pages", "Order or booking intake with an admin list", "Search, status tracking and Excel export"] },
  { id: "payment", name: "Payment integration", what: "We add a payment window such as Toss Payments, verify every payment on the server and send completion notices.",
    examples: ["Pay a deposit straight from a quote", "Order payment with confirmation e-mails", "Subscriptions and refunds"] },
  { id: "docs", name: "Document conversion & automation", what: "We read the different Excel and PDF files each partner sends, convert them to your format, and let people check missing or wrong values.",
    examples: ["Purchase orders into delivery statements", "Merging order exports from several channels", "Automating PDF invoice entry"] },
  { id: "ai", name: "AI agent setup", what: "AI that answers inquiries from your policies and materials, and hands a tidy summary of each conversation to your staff.",
    examples: ["First-line customer support", "Quote and order intake summaries", "Internal policy and process guide"] },
  { id: "infra", name: "Deployment & infrastructure", what: "We set up AWS, Naver Cloud or your own on-premises servers, and zero-downtime automatic deploys from GitHub or Bitbucket.",
    examples: ["AWS, NCP or on-premises servers with Docker", "Zero-downtime deploys from GitHub or Bitbucket", "Domains, HTTPS, backups and rollback"] },
];

export const PROCESS_EN = [
  { title: "Consultation", text: "Describe your work, goals, budget and timeline through the AI chat or the inquiry form. Consultation and quotes are free." },
  { title: "Quote", text: "After review, we e-mail you a quote link with the scope, schedule and price." },
  { title: "Deposit", text: "Pay the deposit right on the quote page and we schedule the kickoff." },
  { title: "Build & interim demo", text: "We show interim results with your real documents and inquiry types, and adjust them with you." },
  { title: "Delivery & stabilization", text: "We deploy to production and refine things during a stabilization period based on real use." },
];

// 영문 사이트는 보류 중이라 아래 영문 문구는 한국어 최신 내용(결제 조건·경력 등)과 맞춰지지 않았다.
export const FAQ_EN: Faq[] = [
  { q: "How do I get a quote?", a: "Tell us what you want to build, your budget and timeline through the AI chat or the inquiry form. We review it and e-mail you a quote link. Consultation and quotes are free, and if the scope is unclear we settle it in a short meeting." },
  { q: "How do I apply?", a: "Organize your request in a conversation with the AI chat on this page, or write it directly in the inquiry form below. You can attach a plan or reference files. We send a confirmation e-mail and get back to you." },
  { q: "What projects do you usually take on?", a: "Our focus is AI consultation agents and document conversion and automation tools built for your business, and we can also handle the websites, admin pages, payment integration and server deployment that go with them." },
  { q: "How does a project run?", a: "Consultation, quote, deposit, build with interim demos, then delivery and stabilization. At the interim demo you check results on your real materials and we adjust." },
  { q: "How much does it cost and how long does it take?", a: "It depends heavily on scope, so we answer with a quote after the consultation. Projects range from a single conversion tool to a bundle of site, payments and AI, and can be split into phases." },
  { q: "How do I pay?", a: "Pay the deposit by card on the quote link and we start development. The timing and method for the balance are stated on the quote. Amounts are in Korean won (KRW). Try the 'Sample quote & payment' flow on this page without paying anything." },
  { q: "Can you handle servers and deployment?", a: "Yes. We deploy to AWS, Naver Cloud or your own on-premises servers, and set up zero-downtime automatic deploys when you push code to GitHub or Bitbucket. If you already have servers, we work with that environment." },
  { q: "Do I need to send company data?", a: "Not for the consultation. Form examples or a description are enough, without real personal or transaction data. When real data is needed later, we sign an NDA first if you need one." },
];

// 월 구독형 유지보수 플랜. 금액은 공개하지 않고 상담 후 안내한다. 플랜 이름·구성은 여기서 바꾼다.
export type Plan = { name: string; fit: string; includes: string[] };
export const MAINTENANCE: { plans: Plan[]; notes: string[] } = {
  plans: [
    { name: "기본 관리", fit: "안정적으로 돌아가기만 하면 되는 경우", includes: ["장애 접수와 대응", "서버·도메인·인증서 점검", "백업 확인과 월간 점검 보고"] },
    { name: "운영 지원", fit: "양식이나 화면이 가끔 바뀌는 경우", includes: ["기본 관리 전체", "문구·양식 변경 같은 작은 수정", "새로 생긴 예외 케이스 보완"] },
    { name: "AI 개선", fit: "AI 상담·자동화를 계속 다듬어 쓰는 경우", includes: ["운영 지원 전체", "AI 답변과 회사 지식 업데이트", "월간 사용 내역 검토와 개선 제안"] },
  ],
  notes: ["무상 하자보수 기간(잔금 후 3주)이 끝나면 이어서 시작합니다.", "월 금액과 세부 범위는 운영 규모를 보고 상담 후 안내드립니다."],
};

export const MAINTENANCE_EN: { plans: Plan[]; notes: string[] } = {
  plans: [
    { name: "Basic care", fit: "It just needs to keep running", includes: ["Incident intake and response", "Server, domain and certificate checks", "Backup checks and a monthly report"] },
    { name: "Operations", fit: "Forms or screens change now and then", includes: ["Everything in Basic care", "Small changes such as wording or form updates", "Handling newly found edge cases"] },
    { name: "AI improvement", fit: "You keep refining your AI agent or automation", includes: ["Everything in Operations", "Updating AI answers and company knowledge", "Monthly usage review and improvement ideas"] },
  ],
  notes: ["Starts after the free defect-fix period (3 weeks after the final payment).", "Monthly price and exact scope are quoted after a consultation."],
};

export const content = (lang: Lang) => lang === "en"
  ? { SERVICES: SERVICES_EN, PROCESS: PROCESS_EN, FAQ: FAQ_EN, MAINTENANCE: MAINTENANCE_EN }
  : { SERVICES, PROCESS, FAQ, MAINTENANCE };
