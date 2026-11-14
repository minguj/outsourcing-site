// 방문간호센터 홈페이지 샘플 데이터. 센터 이름·연락처·수치는 모두 가상이다.
// 실제 구축 시 이 파일의 문구와 이미지는 센터가 제공한 원고로 바뀐다.

export const CENTER = {
  name: "늘곁방문간호센터",
  short: "늘곁",
  slogan: "집에서 받는 간호, 늘 곁에서",
  phone: "02-000-0000",
  hours: "평일 09:00–18:00 · 토 09:00–13:00",
  address: "서울특별시 ○○구 ○○로 00, 2층 (샘플 주소)",
  email: "care@neulgyeot.example",
  regNo: "장기요양기관 지정번호 0-00000-00000 (샘플)",
  kakao: "#kakao",
};

export const STATS = [
  { value: "12명", label: "담당 간호사" },
  { value: "8년", label: "평균 임상 경력" },
  { value: "6개 구", label: "방문 지역" },
  { value: "1영업일", label: "상담 회신" },
];

export type ArtKey = "home" | "care" | "walk" | "pill" | "team" | "wound" | "talk" | "tube";

export type Service = { id: string; title: string; summary: string; points: string[]; forWho: string[]; art: ArtKey };
export const SERVICES: Service[] = [
  { id: "basic", title: "기본 건강관리", art: "care",
    summary: "혈압·혈당·체온과 전신 상태를 확인하고, 변화가 있으면 보호자와 주치의에게 바로 알립니다.",
    points: ["활력징후 측정과 기록", "통증·수면·식사·배변 상태 확인", "이상 징후 발견 시 보호자 연락과 병원 연계"],
    forWho: ["혼자 계시는 시간이 긴 어르신", "만성질환으로 정기 확인이 필요한 분"] },
  { id: "wound", title: "욕창·상처 관리", art: "wound",
    summary: "욕창 단계와 상처 상태를 평가해 소독과 드레싱을 하고, 체위 변경과 피부 관리를 보호자에게 알려 드립니다.",
    points: ["욕창 단계 평가와 사진 기록(동의 시)", "소독·드레싱 교체", "재발을 막는 체위·영양 관리 안내"],
    forWho: ["누워 지내는 시간이 긴 분", "수술 부위나 상처 회복이 더딘 분"] },
  { id: "tube", title: "소변줄·콧줄 관리", art: "tube",
    summary: "유치도뇨관(소변줄)과 비위관(콧줄)의 교체·관리를 집에서 진행해 병원 왕래 부담을 줄입니다.",
    points: ["방문간호지시서에 따른 관 교체", "감염 징후와 막힘 확인", "보호자 일상 관리법 교육"],
    forWho: ["거동이 어려워 병원 방문이 부담되는 분", "관을 오래 유지해야 하는 분"] },
  { id: "stoma", title: "장루·기관절개관 관리", art: "home",
    summary: "장루 주변 피부와 기관절개관 상태를 살피고, 교체와 세척 방법을 보호자가 익히도록 함께합니다.",
    points: ["장루 주머니 교체와 피부 상태 확인", "기관절개관 세척·관리", "응급 상황 대처 요령 안내"],
    forWho: ["장루·기관절개관을 처음 관리하는 가족"] },
  { id: "chronic", title: "만성질환·복약 관리", art: "pill",
    summary: "드시는 약을 정리해 복용 시간을 맞추고, 당뇨·고혈압 등 만성질환 관리 습관을 함께 만듭니다.",
    points: ["복용 약 목록 정리와 약 상자 관리", "인슐린·혈당 관리 확인", "주치의 진료 때 전달할 내용 정리"],
    forWho: ["드시는 약이 많은 분", "복약을 자주 잊으시는 분"] },
  { id: "family", title: "보호자 교육·상담", art: "talk",
    summary: "간호사가 없는 시간에도 가족이 안심하고 돌볼 수 있도록 상황별 돌봄 방법을 알려 드립니다.",
    points: ["체위 변경·이동 보조 방법", "식사·수분 섭취 관리", "보호자 돌봄 부담 상담"],
    forWho: ["처음 돌봄을 맡게 된 가족", "돌봄 방법이 맞는지 확인하고 싶은 분"] },
];

export const SITUATIONS = [
  { title: "퇴원했는데 집에서 처치가 필요할 때", text: "상처 소독, 관 관리처럼 병원에서 받던 처치를 집에서 이어 갑니다.", art: "home" as ArtKey },
  { title: "욕창이 생겼거나 걱정될 때", text: "단계를 평가하고, 더 깊어지지 않도록 관리 계획을 세웁니다.", art: "wound" as ArtKey },
  { title: "관 교체 때문에 병원 가기 어려울 때", text: "소변줄·콧줄 교체를 방문해서 진행합니다.", art: "tube" as ArtKey },
  { title: "약이 많아 복용 관리가 어려울 때", text: "약을 정리하고 복용 시간을 맞춰 드립니다.", art: "pill" as ArtKey },
];

export const STEPS = [
  { title: "상담 신청", text: "전화·카카오톡·온라인으로 어르신 상황을 알려 주세요." },
  { title: "장기요양 등급 확인", text: "등급이 없으시면 국민건강보험공단 신청 방법을 안내해 드립니다." },
  { title: "방문간호지시서 발급", text: "주치의에게 방문간호지시서를 받습니다. 발급 방법을 도와드려요." },
  { title: "첫 방문·간호 계획", text: "간호사가 방문해 상태를 살피고 간호 계획을 함께 정합니다." },
  { title: "정기 방문", text: "약속한 일정에 방문하고, 방문 기록을 보호자와 공유합니다." },
];

export const DOCUMENTS = [
  { title: "장기요양인정서", text: "국민건강보험공단에서 발급한 등급 확인서" },
  { title: "방문간호지시서", text: "의사·한의사·치과의사가 발급 (유효기간 내)" },
  { title: "신분증 사본", text: "급여 계약 시 이용자·보호자 확인용" },
];

export const AREAS = ["강서구", "양천구", "구로구", "영등포구", "금천구", "관악구"];

export const FAQ = [
  { q: "장기요양 등급이 없어도 상담할 수 있나요?", a: "네. 등급 신청 방법과 준비할 서류부터 안내해 드립니다. 등급을 받은 뒤 방문간호를 시작할 수 있습니다." },
  { q: "비용은 어떻게 되나요?", a: "장기요양 재가급여는 본인부담 15%가 기본이며, 감경 대상자는 9%·6%, 기초생활수급자는 면제됩니다. 방문 시간과 횟수에 따라 달라지므로 상담 때 예상 금액을 안내해 드립니다." },
  { q: "방문간호지시서는 어디서 받나요?", a: "다니시는 병원이나 의원의 의사에게 받을 수 있습니다. 진료가 어려우시면 발급 방법을 함께 찾아 드립니다." },
  { q: "주말이나 공휴일에도 방문하나요?", a: "정기 방문은 평일 중심이며, 관 교체 등 일정이 정해진 처치는 상담을 통해 조정합니다." },
  { q: "같은 간호사가 계속 방문하나요?", a: "가능한 한 담당 간호사를 정해 같은 분이 방문합니다. 휴무 시에는 인수인계를 받은 간호사가 방문합니다." },
];

export const ABOUT = {
  greeting: [
    "병원에서 퇴원하는 날, 많은 보호자분들이 같은 질문을 하십니다. \"이제 집에서는 누가 봐 주나요?\"",
    "늘곁방문간호센터는 그 질문에 답하기 위해 문을 열었습니다. 병원에서 받던 간호를 익숙한 집에서 이어 가고, 간호사가 돌아간 뒤에도 가족이 안심할 수 있도록 돌봄 방법을 함께 나눕니다.",
    "약속한 시간에 방문하고, 본 것과 한 일을 빠짐없이 설명하는 것. 저희가 지키는 가장 기본적인 약속입니다.",
  ],
  director: "센터장 김○○ (간호사, 샘플)",
  promises: [
    { title: "약속한 시간에", text: "방문 일정은 하루 전 다시 안내하고, 늦어질 때는 미리 연락드립니다." },
    { title: "본 것을 그대로", text: "방문할 때마다 상태 변화와 처치 내용을 보호자에게 기록으로 남깁니다." },
    { title: "가족도 함께", text: "간호사가 없는 시간에 필요한 돌봄 방법을 가족에게 알려 드립니다." },
  ],
  team: [
    { role: "센터장", career: "종합병원 내과·중환자실 14년" },
    { role: "팀장 간호사", career: "상처·장루 전문 간호 9년" },
    { role: "방문 간호사", career: "가정간호·요양병원 7년" },
    { role: "방문 간호사", career: "재활병동·신경과 6년" },
  ],
};

export type PostStatus = "draft" | "published";
export type FaqItem = { q: string; a: string };
export type Post = {
  id: string; slug: string; title: string; body: string; cover: string | null;
  status: PostStatus; publishedAt: string | null; updatedAt: string;
  seoTitle: string; seoDesc: string; faq: FaqItem[];
};
export type ImageItem = { id: string; name: string; src: string; alt: string; width: number; height: number; bytes: number; originalBytes?: number; createdAt: string };
export type Inquiry = {
  id: string; name: string; phone: string; relation: string; area: string; grade: string; time: string; message: string;
  at: string; status: "new" | "done"; mail: "sent" | "failed";
};
export type Mail = { id: string; at: string; to: string; subject: string; body: string; ok: boolean };

/** 기본 이미지: 실제 사진 대신 직접 그린 일러스트(저작권 문제 없음). src가 "art:"로 시작한다. */
export const BUILTIN_IMAGES: ImageItem[] = [
  { id: "img-home", name: "방문 간호 (일러스트)", src: "art:home", alt: "간호사가 어르신 댁을 방문한 모습", width: 1600, height: 1000, bytes: 0, createdAt: "2026-10-02T09:00:00" },
  { id: "img-care", name: "건강 확인 (일러스트)", src: "art:care", alt: "간호사가 혈압을 재는 모습", width: 1600, height: 1000, bytes: 0, createdAt: "2026-10-02T09:00:00" },
  { id: "img-wound", name: "상처 관리 (일러스트)", src: "art:wound", alt: "상처 드레싱 도구", width: 1600, height: 1000, bytes: 0, createdAt: "2026-10-02T09:00:00" },
  { id: "img-pill", name: "복약 관리 (일러스트)", src: "art:pill", alt: "요일별로 정리한 약 상자", width: 1600, height: 1000, bytes: 0, createdAt: "2026-10-02T09:00:00" },
  { id: "img-walk", name: "보행 연습 (일러스트)", src: "art:walk", alt: "보호자와 함께 걷는 어르신", width: 1600, height: 1000, bytes: 0, createdAt: "2026-10-02T09:00:00" },
  { id: "img-team", name: "간호팀 (일러스트)", src: "art:team", alt: "센터 간호팀", width: 1600, height: 1000, bytes: 0, createdAt: "2026-10-02T09:00:00" },
];

export const INITIAL_POSTS: Post[] = [
  {
    id: "p1", slug: "pressure-sore-prevention", title: "욕창, 집에서 미리 막는 다섯 가지 습관", cover: "img-wound",
    status: "published", publishedAt: "2026-11-10T10:00:00", updatedAt: "2026-11-10T10:00:00",
    seoTitle: "욕창 예방, 집에서 지키는 다섯 가지 습관 | 늘곁방문간호센터",
    seoDesc: "누워 지내는 시간이 긴 어르신의 욕창을 막기 위해 보호자가 집에서 지킬 수 있는 체위 변경, 피부 확인, 영양 관리 방법을 정리했습니다.",
    body: `욕창은 한번 생기면 회복에 오랜 시간이 걸립니다. 그래서 생기기 전에 막는 것이 가장 중요합니다. 방문간호 현장에서 보호자분들께 가장 많이 알려 드리는 습관 다섯 가지를 정리했습니다.

## 1. 두 시간마다 자세 바꾸기
같은 자세로 오래 누워 있으면 뼈가 튀어나온 부위(엉치, 발뒤꿈치, 어깨)에 압력이 몰립니다. 낮에는 두 시간마다 자세를 바꿔 주세요.

## 2. 하루 한 번 피부 살피기
씻기거나 옷을 갈아입힐 때 붉게 변한 부위가 있는지 확인합니다. 눌렀을 때 하얗게 변하지 않는 붉은 자국은 욕창의 첫 신호일 수 있습니다.

## 3. 습기 관리
땀이나 기저귀의 습기는 피부를 약하게 만듭니다. 젖은 기저귀는 바로 갈고, 피부는 문지르지 말고 눌러서 말려 주세요.

## 4. 충분한 단백질과 수분
상처가 잘 낫지 않는 이유 중 하나는 영양 부족입니다. 식사량이 줄었다면 담당 간호사와 상의해 주세요.

## 5. 이상하면 바로 연락하기
물집, 피부 벗겨짐, 진물이 보이면 혼자 처치하지 말고 센터로 연락 주세요. 초기에 관리할수록 빨리 회복됩니다.`,
    faq: [
      { q: "욕창 초기 증상은 무엇인가요?", a: "눌러도 하얗게 변하지 않는 붉은 자국이 첫 신호입니다. 이 단계에서 압력을 줄여 주면 대부분 회복됩니다." },
      { q: "에어매트만 쓰면 자세를 안 바꿔도 되나요?", a: "아닙니다. 에어매트는 압력을 줄여 줄 뿐이라 정기적인 자세 변경은 계속 필요합니다." },
    ],
  },
  {
    id: "p2", slug: "visiting-nurse-order", title: "방문간호지시서, 어디서 어떻게 받나요?", cover: "img-care",
    status: "published", publishedAt: "2026-11-04T10:00:00", updatedAt: "2026-11-04T10:00:00",
    seoTitle: "방문간호지시서 발급 방법과 유효기간 | 늘곁방문간호센터",
    seoDesc: "방문간호를 시작하려면 꼭 필요한 방문간호지시서. 어디서 발급받는지, 무엇을 준비해야 하는지 보호자 눈높이로 정리했습니다.",
    body: `방문간호를 시작하려면 장기요양 등급과 함께 방문간호지시서가 필요합니다. 처음 듣는 분이 많아 자주 묻는 내용을 정리했습니다.

## 방문간호지시서란?
의사가 어르신의 상태를 보고 필요한 간호 내용(예: 욕창 드레싱, 소변줄 교체)을 적어 주는 문서입니다. 방문간호사는 이 지시서에 따라 간호합니다.

## 어디서 받나요?
다니시는 병원이나 의원의 의사에게 받을 수 있습니다. 진료를 받을 때 "방문간호지시서가 필요하다"고 말씀하시면 됩니다.

## 준비하면 좋은 것
- 장기요양인정서
- 현재 드시는 약 목록
- 집에서 필요한 처치 내용 메모

## 유효기간이 있나요?
네. 지시서에는 유효기간이 있어 기간이 끝나기 전에 다시 받아야 합니다. 센터에서 만료 전에 미리 알려 드립니다.`,
    faq: [
      { q: "거동이 어려워 병원에 갈 수 없으면 어떻게 하나요?", a: "보호자 상담이나 방문진료가 가능한 의료기관을 안내해 드립니다. 상황에 맞는 방법을 상담 때 함께 찾아 드려요." },
    ],
  },
  {
    id: "p3", slug: "after-discharge-checklist", title: "퇴원 첫 주, 보호자가 확인할 것", cover: "img-home",
    status: "published", publishedAt: "2026-10-28T10:00:00", updatedAt: "2026-10-28T10:00:00",
    seoTitle: "퇴원 후 첫 주 보호자 체크리스트 | 늘곁방문간호센터",
    seoDesc: "병원에서 집으로 돌아온 첫 주는 몸 상태가 가장 많이 변하는 시기입니다. 보호자가 매일 확인할 항목을 정리했습니다.",
    body: `퇴원 첫 주는 생활 환경이 바뀌면서 몸 상태가 크게 변할 수 있는 시기입니다. 매일 아래 항목을 확인해 주세요.

## 매일 확인할 것
- 체온과 혈압
- 식사량과 물 마신 양
- 소변·대변 횟수
- 수술 부위나 상처의 붓기, 열감

## 퇴원할 때 받아 둘 것
퇴원 요약지와 처방전, 다음 외래 일정은 꼭 챙겨 주세요. 방문간호를 시작할 때 간호사가 이 자료를 보고 계획을 세웁니다.

## 바로 연락해야 할 때
38도 이상의 열, 갑작스러운 의식 변화, 숨이 차는 증상이 있으면 지체하지 말고 병원이나 119에 연락하세요.`,
    faq: [],
  },
  {
    id: "p4", slug: "winter-fall-prevention", title: "겨울철 어르신 낙상 예방 (작성 중)", cover: "img-walk",
    status: "draft", publishedAt: null, updatedAt: "2026-11-12T16:20:00",
    seoTitle: "", seoDesc: "",
    body: `겨울에는 실내외 모두 낙상 위험이 커집니다.

## 집 안에서
- 화장실 바닥 미끄럼 방지 매트
- 밤에 켜 두는 작은 조명`,
    faq: [],
  },
];

export const INITIAL_INQUIRIES: Inquiry[] = [
  { id: "q1", name: "이*정", phone: "010-****-2841", relation: "자녀", area: "양천구", grade: "있음 (3등급)", time: "평일 오후", message: "어머니가 다음 주 퇴원하시는데 소변줄을 한 상태로 오십니다. 교체를 집에서 받을 수 있는지 궁금합니다.", at: "2026-11-13T15:42:00", status: "new", mail: "sent" },
  { id: "q2", name: "박*호", phone: "010-****-7720", relation: "배우자", area: "구로구", grade: "모름", time: "언제든", message: "등급 신청부터 해야 할 것 같은데 어떻게 시작하면 될까요?", at: "2026-11-12T10:05:00", status: "new", mail: "sent" },
  { id: "q3", name: "최*영", phone: "010-****-0193", relation: "자녀", area: "강서구", grade: "있음 (2등급)", time: "평일 오전", message: "아버지 엉덩이 쪽에 욕창이 생겼습니다. 방문 가능한 날짜 알려 주세요.", at: "2026-11-09T19:30:00", status: "done", mail: "sent" },
];

export const DEMO_ADMIN = { email: "admin@neulgyeot.example", password: "demo1234" };
