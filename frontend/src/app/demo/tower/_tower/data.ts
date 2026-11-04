// 지식산업센터 통합 플랫폼 샘플용 가상 데이터. 실제 단지·기업·상가와 무관하다.

export type CompanyStatus = "approved" | "pending" | "rejected";
export type Company = {
  id: string; name: string; industry: string; room: string; ceo: string; bizNo: string;
  intro: string; techs: string[]; services: string[]; portfolio: { title: string; desc: string }[];
  phone: string; email: string; site: string; color: string;
  status: CompanyStatus; visible: boolean; appliedAt: string; reason?: string;
};
export type Store = { id: string; name: string; category: string; room: string; intro: string; hours: string; menu: string[]; color: string; pin: string };
export type Coupon = { id: string; storeId: string; title: string; benefit: string; from: string; to: string; total: number; issued: number; used: number; active: boolean };
export type MyCoupon = { id: string; couponId: string; status: "issued" | "used"; issuedAt: string; usedAt?: string };
export type Usage = { id: string; couponId: string; storeId: string; member: string; at: string };
export type Activity = { id: string; at: string; text: string };

export const INDUSTRIES = ["IT·소프트웨어", "제조·생산", "디자인·브랜딩", "전문서비스", "유통·물류"];
export const STORE_CATEGORIES = ["식당", "카페", "편의·생활", "운동·건강"];

const c = (o: Omit<Company, "visible" | "status" | "appliedAt"> & Partial<Pick<Company, "status" | "visible" | "appliedAt">>): Company =>
  ({ status: "approved", visible: true, appliedAt: "2026-10-02", ...o });

export const COMPANIES: Company[] = [
  c({ id: "c01", name: "누리소프트", industry: "IT·소프트웨어", room: "A동 1203호", ceo: "김도윤", bizNo: "214-81-30112", color: "#2f5bd3",
    intro: "중소 제조사를 위한 생산관리(MES)와 재고 관리 시스템을 만듭니다.", techs: ["MES", "React", "Java", "클라우드"],
    services: ["생산관리 시스템 구축", "재고·출하 관리", "기존 시스템 유지보수"], portfolio: [{ title: "부품 제조사 MES 구축", desc: "작업지시부터 출하까지 바코드로 추적" }, { title: "식품 공장 재고 앱", desc: "태블릿으로 입출고 기록" }],
    phone: "031-000-1203", email: "contact@nuri.example", site: "nuri.example" }),
  c({ id: "c02", name: "다온디자인랩", industry: "디자인·브랜딩", room: "A동 805호", ceo: "이서연", bizNo: "135-86-44120", color: "#d34f73",
    intro: "브랜드 아이덴티티, 패키지, 웹 디자인을 한 팀에서 진행합니다.", techs: ["BI·CI", "패키지", "UI/UX", "Figma"],
    services: ["로고·브랜드 가이드", "제품 패키지 디자인", "홈페이지·앱 UI 디자인"], portfolio: [{ title: "건강식품 브랜드 리뉴얼", desc: "로고와 패키지 12종" }, { title: "B2B 장비사 웹사이트", desc: "반응형 웹 디자인" }],
    phone: "031-000-0805", email: "hello@daon.example", site: "daon.example" }),
  c({ id: "c03", name: "한빛정밀", industry: "제조·생산", room: "B동 107호", ceo: "박준호", bizNo: "124-81-77231", color: "#3d7a4e",
    intro: "CNC 정밀 가공과 시제품 제작을 소량부터 받습니다.", techs: ["CNC 가공", "시제품", "알루미늄", "3D 측정"],
    services: ["정밀 부품 가공", "시제품 소량 생산", "도면 검토"], portfolio: [{ title: "의료기기 하우징 시제품", desc: "알루미늄 5축 가공" }],
    phone: "031-000-0107", email: "order@hanbit.example", site: "hanbit.example" }),
  c({ id: "c04", name: "세움세무회계", industry: "전문서비스", room: "A동 402호", ceo: "정민지", bizNo: "220-15-90341", color: "#7a5a2f",
    intro: "스타트업·제조사 기장과 세무 신고, 정부지원사업 정산을 돕습니다.", techs: ["기장", "부가세", "법인세", "지원사업 정산"],
    services: ["월 기장 대행", "법인 설립·세무 상담", "R&D 지원사업 정산"], portfolio: [{ title: "입주사 30곳 기장", desc: "같은 건물 방문 상담" }],
    phone: "031-000-0402", email: "tax@seum.example", site: "seum.example" }),
  c({ id: "c05", name: "모아로지스", industry: "유통·물류", room: "B동 B102호", ceo: "최성훈", bizNo: "312-87-11829", color: "#c26a1b",
    intro: "소량 보관부터 택배 출고까지, 입주사 전용 물류 대행을 합니다.", techs: ["3PL", "택배 연동", "재고 보관"],
    services: ["보관·출고 대행", "스마트스토어 주문 연동", "반품 처리"], portfolio: [{ title: "생활용품 브랜드 출고 대행", desc: "하루 300건 출고" }],
    phone: "031-000-1102", email: "ship@moa.example", site: "moa.example" }),
  c({ id: "c06", name: "브릿지에이아이", industry: "IT·소프트웨어", room: "A동 1507호", ceo: "윤하늘", bizNo: "561-88-02013", color: "#5b3fc9",
    intro: "사내 문서로 답하는 AI 상담봇과 업무 자동화를 만듭니다.", techs: ["AI 챗봇", "Python", "업무 자동화", "RAG"],
    services: ["고객 상담 AI 도입", "엑셀·문서 자동화", "AI 도입 컨설팅"], portfolio: [{ title: "쇼핑몰 상담 자동화", desc: "문의 60%를 AI가 1차 응답" }],
    phone: "031-000-1507", email: "ai@bridge.example", site: "bridge.example" }),
  c({ id: "c07", name: "그린팩코리아", industry: "제조·생산", room: "B동 211호", ceo: "강유진", bizNo: "409-81-56720", color: "#2a8a7a",
    intro: "친환경 종이 포장재와 맞춤 박스를 소량 생산합니다.", techs: ["친환경 포장", "맞춤 박스", "인쇄"],
    services: ["택배 박스 제작", "선물 패키지", "포장 컨설팅"], portfolio: [{ title: "베이커리 선물 박스", desc: "1,000개 단위 맞춤 제작" }],
    phone: "031-000-0211", email: "pack@green.example", site: "green.example" }),
  c({ id: "c08", name: "온새미특허", industry: "전문서비스", room: "A동 1110호", ceo: "임태경", bizNo: "117-09-38215", color: "#455a8a",
    intro: "기술 기업의 특허·상표 출원과 분쟁 대응을 맡습니다.", techs: ["특허 출원", "상표", "IP 전략"],
    services: ["특허·상표 출원", "선행기술 조사", "IP 컨설팅"], portfolio: [{ title: "제조 스타트업 특허 12건", desc: "등록률 92%" }],
    phone: "031-000-1110", email: "ip@onsaemi.example", site: "onsaemi.example" }),
  c({ id: "c09", name: "픽셀웍스", industry: "디자인·브랜딩", room: "A동 908호", ceo: "오지훈", bizNo: "206-86-71102", color: "#e0563b",
    intro: "제품 촬영과 상세페이지, 홍보 영상을 제작합니다.", techs: ["제품 촬영", "상세페이지", "영상"],
    services: ["스튜디오 촬영", "상세페이지 디자인", "브랜드 영상"], portfolio: [{ title: "가전 브랜드 상세페이지", desc: "20개 제품" }],
    phone: "031-000-0908", email: "studio@pixel.example", site: "pixel.example" }),
  c({ id: "c10", name: "코어시큐리티", industry: "IT·소프트웨어", room: "A동 1401호", ceo: "서동현", bizNo: "613-81-25540", color: "#1f6f8b",
    intro: "중소기업 보안 점검과 개인정보 보호 체계 수립을 돕습니다.", techs: ["보안 점검", "ISMS", "개인정보보호"],
    services: ["취약점 점검", "ISMS 인증 컨설팅", "보안 교육"], portfolio: [{ title: "핀테크 ISMS 인증", desc: "6개월 컨설팅" }],
    phone: "031-000-1401", email: "sec@core.example", site: "core.example" }),
  c({ id: "c11", name: "대한전자부품", industry: "제조·생산", room: "B동 305호", ceo: "한상철", bizNo: "131-81-90077", color: "#6b6f2a",
    intro: "PCB 조립(SMT)과 소형 전자부품 조립을 합니다.", techs: ["SMT", "PCB 조립", "검사"],
    services: ["PCB 조립", "소량 시제품 조립", "기능 검사"], portfolio: [{ title: "IoT 센서 보드 조립", desc: "월 5,000장" }],
    phone: "031-000-0305", email: "smt@daehan.example", site: "daehan.example" }),
  c({ id: "c12", name: "바른노무법인", industry: "전문서비스", room: "A동 610호", ceo: "신예린", bizNo: "305-82-14520", color: "#8a3f5c",
    intro: "급여·4대보험 아웃소싱과 인사노무 자문을 제공합니다.", techs: ["급여 대행", "4대보험", "인사노무 자문"],
    services: ["급여·4대보험 대행", "취업규칙 작성", "노무 분쟁 상담"], portfolio: [{ title: "제조사 취업규칙 정비", desc: "직원 120명" }],
    phone: "031-000-0610", email: "hr@bareun.example", site: "bareun.example" }),
  c({ id: "c13", name: "라온유통", industry: "유통·물류", room: "B동 B210호", ceo: "조현우", bizNo: "504-81-63309", color: "#b5482a",
    intro: "사무용품·소모품을 입주사 단가로 공급합니다.", techs: ["사무용품", "정기 배송", "공동구매"],
    services: ["사무용품 정기 납품", "탕비실 소모품", "공동구매 대행"], portfolio: [{ title: "입주사 40곳 정기 납품", desc: "주 2회 배송" }],
    phone: "031-000-1210", email: "order@raon.example", site: "raon.example" }),
  // 승인 대기·반려 (관리자 화면 시연용)
  c({ id: "c14", name: "스텔라모빌리티", industry: "IT·소프트웨어", room: "A동 1612호", ceo: "문가은", bizNo: "214-87-55031", color: "#3b6fd1", status: "pending", appliedAt: "2026-11-02",
    intro: "법인 차량 관제와 배차 앱을 개발합니다.", techs: ["차량 관제", "Flutter", "지도 API"], services: ["법인 차량 관제", "배차 앱 개발"], portfolio: [],
    phone: "031-000-1612", email: "hi@stella.example", site: "stella.example" }),
  c({ id: "c15", name: "미래로컨설팅", industry: "전문서비스", room: "A동 703호", ceo: "배수현", bizNo: "123-45-67890", color: "#7c4bb0", status: "pending", appliedAt: "2026-11-03",
    intro: "정부지원사업 신청과 사업계획서 작성을 돕습니다.", techs: ["정부지원사업", "사업계획서", "IR"], services: ["지원사업 신청 대행", "IR 자료 작성"], portfolio: [],
    phone: "031-000-0703", email: "go@mirae.example", site: "mirae.example" }),
  c({ id: "c16", name: "우드앤코", industry: "제조·생산", room: "B동 118호", ceo: "노태윤", bizNo: "402-11-28374", color: "#8a6a3d", status: "pending", appliedAt: "2026-11-03",
    intro: "사무 가구와 원목 소품을 맞춤 제작합니다.", techs: ["원목 가구", "맞춤 제작"], services: ["사무 가구 제작", "인테리어 소품"], portfolio: [],
    phone: "031-000-0118", email: "wood@co.example", site: "wood.example" }),
  c({ id: "c17", name: "제이원트레이딩", industry: "유통·물류", room: "B동 B015호", ceo: "류진혁", bizNo: "609-21-00451", color: "#5a6b7d", status: "rejected", appliedAt: "2026-10-28",
    reason: "사업자등록증 주소지가 입주 호실과 다릅니다. 주소 변경 후 다시 올려 주세요.", intro: "수입 생활용품 도매", techs: ["수입 유통"], services: ["생활용품 도매"], portfolio: [],
    phone: "031-000-0015", email: "j1@trade.example", site: "j1.example" }),
];

export const STORES: Store[] = [
  { id: "s1", name: "그라운드 커피", category: "카페", room: "B1층", intro: "매일 아침 직접 볶은 원두로 내리는 커피", hours: "평일 07:00~20:00", menu: ["아메리카노 3,000원", "라떼 3,800원", "샌드위치 5,500원"], color: "#6b4a2b", pin: "1234" },
  { id: "s2", name: "한끼 식당", category: "식당", room: "1층 103호", intro: "점심 백반과 저녁 단체 회식", hours: "평일 11:00~21:00", menu: ["오늘의 백반 8,500원", "제육볶음 9,000원"], color: "#b5482a", pin: "1234" },
  { id: "s3", name: "타워 피트니스", category: "운동·건강", room: "2층", intro: "입주사 임직원 전용 헬스·필라테스", hours: "평일 06:00~23:00", menu: ["헬스 월 6만 원", "필라테스 10회 25만 원"], color: "#2a6f8a", pin: "1234" },
  { id: "s4", name: "바른 세탁", category: "편의·생활", room: "B1층", intro: "셔츠·정장 세탁, 퇴근 전 픽업", hours: "평일 08:00~20:00", menu: ["셔츠 2,000원", "정장 8,000원"], color: "#3d7a6e", pin: "1234" },
  { id: "s5", name: "베이크하우스", category: "카페", room: "1층 110호", intro: "갓 구운 빵과 회의용 다과 세트", hours: "매일 08:00~21:00", menu: ["소금빵 3,200원", "회의 다과 세트 2만 원"], color: "#c08a2e", pin: "1234" },
  { id: "s6", name: "면가", category: "식당", room: "1층 105호", intro: "칼국수와 만두, 빠른 점심", hours: "평일 10:30~20:00", menu: ["칼국수 8,000원", "만두 6,000원"], color: "#7a3d3d", pin: "1234" },
];

export const COUPONS: Coupon[] = [
  { id: "k1", storeId: "s1", title: "아메리카노 10% 할인", benefit: "10%", from: "2026-11-01", to: "2026-11-30", total: 300, issued: 214, used: 151, active: true },
  { id: "k2", storeId: "s2", title: "점심 백반 1,000원 할인", benefit: "1,000원", from: "2026-11-01", to: "2026-11-30", total: 200, issued: 168, used: 120, active: true },
  { id: "k3", storeId: "s3", title: "첫 달 이용료 20% 할인", benefit: "20%", from: "2026-11-01", to: "2026-12-31", total: 50, issued: 31, used: 9, active: true },
  { id: "k4", storeId: "s4", title: "셔츠 5장 세탁 1장 무료", benefit: "1장 무료", from: "2026-11-01", to: "2026-11-30", total: 100, issued: 47, used: 22, active: true },
  { id: "k5", storeId: "s5", title: "회의 다과 세트 15% 할인", benefit: "15%", from: "2026-11-01", to: "2026-11-30", total: 80, issued: 36, used: 18, active: true },
  { id: "k6", storeId: "s6", title: "만두 서비스", benefit: "만두 1인분", from: "2026-10-01", to: "2026-10-31", total: 150, issued: 150, used: 131, active: false },
];

// 대시보드 시연용: 최근 12주 신규 가입자 수와 주간 활성 사용자 수
export const WEEKLY = {
  labels: ["8/17", "8/24", "8/31", "9/7", "9/14", "9/21", "9/28", "10/5", "10/12", "10/19", "10/26", "11/2"],
  signups: [42, 58, 61, 77, 69, 84, 92, 88, 104, 97, 118, 126],
  active: [310, 352, 371, 402, 418, 455, 470, 466, 512, 530, 561, 590],
};
export const MEMBER_BASE = 1284;
