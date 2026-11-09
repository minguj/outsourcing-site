// 화면에 보이는 동작 흐름·기술 구조·자주 묻는 질문. AI 상담봇이 아는 같은 내용은 backend/site_knowledge.py 에 있다.
// 문구를 바꿀 때는 두 곳을 함께 맞춘다.

// 영문 사이트(/en) 문구는 아래 *_EN 에 있다. AI 상담봇은 한국어 정보를 영어로 옮겨 답한다.
import type { Lang } from "./_site/i18n";

// chip: false 인 질문은 아래 자주 묻는 질문 목록에만 보이고 상담 기록지 버튼으로는 나오지 않는다.
// link: 메인 자주 묻는 질문 목록에서 답 아래에 붙는 바로가기(상담 기록지 버튼 답에는 나오지 않는다).
export type Faq = { q: string; a: string; chip?: boolean; link?: { href: string; label: string } };

// 동작 흐름 한 단계. action은 랜딩에서 누르면 하는 일이다.
// chat: 상담창 열기, inquiry: 접수 양식으로 이동, quote: 체험용 견적서 열기, contract: 체험 견적서로 계약서(안) 열기
export type FlowAction = "chat" | "inquiry" | "quote" | "contract";
export type FlowStep = { title: string; text: string; action: FlowAction; cta: string };
// 기술 구조 한 줄: 맡은 일(layer), 쓰는 기술(tech), 설명(text).
export type StackLayer = { layer: string; tech: string; text: string };

export const FLOW: FlowStep[] = [
  { title: "상담", text: "방문자가 상담창에서 질문하거나 하고 싶은 일을 말합니다. 자주 묻는 질문은 버튼으로 바로 답합니다.", action: "chat", cta: "상담창에서 해 보기" },
  { title: "요약", text: "AI가 방문자가 직접 말한 내용만으로 담당자용 요약 카드를 만듭니다.", action: "chat", cta: "요약 카드 만들어 보기" },
  { title: "접수", text: "방문자가 요약을 확인하고 연락처를 남기면 접수됩니다. 고객에게 확인 메일, 담당자에게 알림 메일이 갑니다.", action: "inquiry", cta: "접수 양식 보기" },
  { title: "견적서", text: "담당자가 관리자 화면에서 견적서를 만들어 고객별 링크로 보냅니다.", action: "quote", cta: "체험용 견적서 열기" },
  { title: "계약", text: "견적서 내용이 채워진 계약서(안)를 확인하고, 인쇄하거나 Word로 내려받습니다.", action: "contract", cta: "계약서(안) 열어 보기" },
  { title: "결제", text: "견적서에서 착수금을 결제하면 진행 안내가 메일로 발송됩니다. 체험 결제는 청구되지 않습니다.", action: "quote", cta: "결제 흐름 체험하기" },
];

export const STACK: StackLayer[] = [
  { layer: "화면", tech: "Next.js 16", text: "랜딩, 상담창, 접수 양식, 견적서·계약서 화면과 관리자 화면" },
  { layer: "서버", tech: "FastAPI", text: "상담·접수·견적·결제 API, 접수 확인과 알림 메일 발송" },
  { layer: "데이터", tech: "SQLite", text: "접수 내용, 견적서, AI 상담 기록(90일 보관 후 삭제)" },
  { layer: "AI", tech: "Claude API", text: "등록된 FAQ·운영 기준으로 답하고, 도구 호출(save_brief)로 요약을 만듭니다. 매번 같은 회사 정보는 프롬프트 캐싱으로 비용을 줄입니다." },
  { layer: "운영", tech: "Docker Compose · Caddy", text: "AWS 서버에서 컨테이너로 운영하고 HTTPS를 자동으로 적용합니다." },
  { layer: "배포", tech: "GitHub Actions", text: "main 브랜치에 올리면 검사를 거쳐 서버에 자동으로 다시 배포됩니다." },
];

export const FAQ: Faq[] = [
  { q: "이 사이트는 무엇인가요?", a: "AI 상담 → 요약 → 접수 → 견적서 → 계약 → 결제를 하나로 잇는 AI 상담 접수 시스템의 데모입니다. 지금 보고 계신 상담창과 접수 양식, 견적·결제 체험이 실제로 동작합니다." },
  { q: "데모에서 무엇을 해 볼 수 있나요?", a: "상담창에 궁금한 점을 묻거나 도입하고 싶은 내용을 말하면 AI가 요약 카드를 만들어 줍니다. '견적·결제 흐름 체험'으로 체험용 견적서와 결제 흐름을 볼 수 있고, 아래 데모 모음에서 발주서 변환과 플랫폼 샘플도 열어 볼 수 있습니다." },
  { q: "결제하면 실제로 청구되나요?", a: "아니요. 체험용 견적서의 금액은 예시이고 결제해도 청구되지 않습니다. 체험 견적서는 2시간 뒤 사라집니다." },
  { q: "우리 회사에 맞게 바꿀 수 있나요?", a: "회사 FAQ와 운영 기준, 상담에서 확인할 항목, 견적서·계약서 양식을 회사 기준으로 바꿔 적용할 수 있습니다. 구체적인 범위는 도입 문의를 남겨 주시면 담당자가 검토해 안내드립니다." },
  { q: "지금 쓰는 홈페이지에 붙일 수 있나요?", a: "기존 홈페이지나 사내 시스템과 연결하는 방법은 환경에 따라 다릅니다. 쓰고 계신 사이트를 알려 주시면 담당자가 가능 여부와 방법을 확인해 안내드립니다." },
  { q: "상담 내용은 어떻게 보관되나요?", a: "AI 상담 대화는 답변 품질 개선을 위해 90일 보관 후 삭제됩니다. 접수하신 연락처와 내용은 상담 종료 후 1년 보관 후 파기하고, 요청하시면 바로 삭제합니다. 자세한 내용은 개인정보처리방침에 있습니다." },
  { q: "도입 비용과 일정은 어떻게 알 수 있나요?", a: "연동 범위와 맞춤 정도에 따라 달라서, 도입 문의를 남겨 주시면 담당자가 검토해 견적서로 안내드립니다. 상담과 견적은 무료입니다." },
  { q: "AI가 틀린 답을 하면 어떻게 하나요?", a: "AI는 등록된 FAQ와 운영 기준 안에서만 답하도록 설정되어 있고, 없는 내용은 담당자가 확인해 안내한다고 답합니다. 금액은 말하지 않고, 요약에는 고객이 직접 말한 내용만 넣습니다.", chip: false },
  { q: "관리자 화면도 볼 수 있나요?", a: "관리자 화면은 로그인이 필요해 공개하지 않습니다. 접수 목록, AI 상담 기록, 첨부 파일 확인, 견적서 작성·발송 기능이 있고, 도입 문의를 남겨 주시면 담당자가 안내드립니다.", chip: false },
  { q: "어떤 기술로 만들었나요?", a: "화면은 Next.js, 서버는 FastAPI와 SQLite, AI 상담은 Claude API로 만들었습니다. Docker Compose와 Caddy로 AWS 서버에서 운영하고, GitHub에 올리면 자동으로 배포됩니다.", chip: false },
  { q: "AI 사용료는 누가 내나요?", a: "도입하시면 AI 사용료(토큰)는 회사에서 결제·충전한 계정을 제공해 주셔야 합니다. 서버 운영 방식과 비용은 상담 후 안내드립니다.", chip: false },
  { q: "회사 자료를 보내야 하나요?", a: "상담 단계에서는 실제 개인정보나 거래 자료 없이 설명만으로 충분합니다. 요청하시면 계약서와 함께 비밀유지계약(NDA)을 맺고 실제 자료를 받습니다.", chip: false, link: { href: "/contract/nda", label: "비밀유지계약서 양식 보기" } },
];

// 영문 사이트는 보류 중이다. 다시 열 때 한국어 최신 내용과 맞춰 다듬는다.
export const FLOW_EN: FlowStep[] = [
  { title: "Consult", text: "A visitor asks questions or describes what they need in the chat. Common questions are answered instantly by button.", action: "chat", cta: "Try the chat" },
  { title: "Summarize", text: "The AI writes a staff-ready summary card using only what the visitor actually said.", action: "chat", cta: "Make a summary card" },
  { title: "Intake", text: "The visitor checks the summary and leaves contact details. They get a confirmation e-mail and staff get a notification.", action: "inquiry", cta: "See the intake form" },
  { title: "Quote", text: "Staff create a quote in the admin page and send it as a per-customer link.", action: "quote", cta: "Open a sample quote" },
  { title: "Contract", text: "A draft contract filled in from the quote, ready to print or download as Word.", action: "contract", cta: "Open the draft contract" },
  { title: "Payment", text: "Paying the deposit on the quote sends the next steps by e-mail. Sample payments are never charged.", action: "quote", cta: "Try the payment flow" },
];

export const STACK_EN: StackLayer[] = [
  { layer: "Frontend", tech: "Next.js 16", text: "Landing page, chat, intake form, quote and contract pages, and the admin page" },
  { layer: "Server", tech: "FastAPI", text: "Chat, intake, quote and payment APIs, confirmation and notification e-mails" },
  { layer: "Data", tech: "SQLite", text: "Inquiries, quotes and AI chat logs (deleted after 90 days)" },
  { layer: "AI", tech: "Claude API", text: "Answers from your FAQ and policies, writes summaries through a tool call (save_brief), and uses prompt caching for the unchanging company information." },
  { layer: "Hosting", tech: "Docker Compose · Caddy", text: "Runs in containers on an AWS server with HTTPS applied automatically." },
  { layer: "Deploys", tech: "GitHub Actions", text: "Pushing to main runs checks and redeploys the server automatically." },
];

export const FAQ_EN: Faq[] = [
  { q: "What is this site?", a: "A demo of an AI consultation intake system that links consultation, summary, intake, quote, contract and payment. The chat, intake form and sample quote and payment on this page all actually work." },
  { q: "What can I try in the demo?", a: "Ask the chat anything, or describe what you'd like to adopt and the AI writes a summary card. 'Sample quote & payment' walks you through a sample quote and payment, and the demo section below has a purchase order converter and a platform sample." },
  { q: "Will I be charged if I pay?", a: "No. Sample quote amounts are examples and paying never charges you. Sample quotes disappear after two hours." },
  { q: "Can it be tailored to my company?", a: "Your FAQ and policies, the questions the chat asks, and the quote and contract formats can all be set to your company's standards. Leave an inquiry and we'll review the scope." },
  { q: "How are conversations stored?", a: "AI chat conversations are kept for 90 days to improve answers, then deleted. Contact details and inquiries are kept for one year after the consultation ends, or deleted right away on request." },
  { q: "How do I find out cost and timeline?", a: "It depends on integrations and customization, so we answer with a quote after you leave an inquiry. Consultation and quotes are free." },
  { q: "What is it built with?", a: "Next.js for the frontend, FastAPI and SQLite on the server, and the Claude API for the AI chat. It runs on AWS with Docker Compose and Caddy, and deploys automatically from GitHub.", chip: false },
];

export const content = (lang: Lang) => lang === "en"
  ? { FLOW: FLOW_EN, STACK: STACK_EN, FAQ: FAQ_EN }
  : { FLOW, STACK, FAQ };
