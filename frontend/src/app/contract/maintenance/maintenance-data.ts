// 유지보수 계약서(안)에 채우는 플랜·작업 등급. 메인 화면에는 더 이상 보이지 않고 이 계약서에서만 쓴다.
// 플랜마다 매달 작업 포인트를 주고, 요청 작업은 등급(L1~L4)에 따라 포인트를 차감한다. 건별 단가는 상담 후 계약서에 채운다.
export type Plan = { name: string; price: string; fit: string; points: number; includes: string[] };
export type Level = { code: string; name: string; examples: string; points: string };
type Maintenance = { plans: Plan[]; levels: Level[]; notes: string[] };

export const MAINTENANCE: Maintenance = {
  plans: [
    { name: "기본 관리", price: "월 15만 원", fit: "서버 운영까지 맡겨 개발했거나, 운영만 맡기려는 경우", points: 2,
      includes: ["장애 감시와 대응", "보안 업데이트, 매일 백업과 월 1회 복구 점검", "월간 점검 보고", "요청은 당일 첫 응답", "간단 수정(L1) 2건 정도"] },
    { name: "운영 지원", price: "월 35만 원", fit: "화면이나 기능을 가끔 수정하는 경우", points: 6,
      includes: ["기본 관리 전체", "화면·기능 수정(L2) 2건 정도", "또는 간단 수정(L1) 6건 정도"] },
    { name: "집중 지원", price: "월 70만 원", fit: "기능을 계속 고쳐 가며 운영하는 경우", points: 15,
      includes: ["기본 관리 전체", "데이터 구조 변경(L3) 1건과 화면·기능 수정(L2) 2건 정도"] },
  ],
  levels: [
    { code: "L1", name: "간단 수정", examples: "문구·이미지·색상·링크 변경, 공지 교체", points: "1점" },
    { code: "L2", name: "화면·기능 수정", examples: "화면·입력 항목 추가(데이터 구조는 그대로), 검증 규칙 변경, 엑셀·PDF 양식 추가, AI 답변·회사 자료 업데이트", points: "3점" },
    { code: "L3", name: "데이터 구조 변경", examples: "데이터베이스 마이그레이션이 필요한 변경. 백업, 되돌리기 계획, 사전 검증까지 포함", points: "8점" },
    { code: "L4", name: "운영환경 변경", examples: "서버 이전·사양 변경, 도메인·메일 교체, 배포 방식 변경, 외부 서비스 버전 교체", points: "사전 견적" },
    { code: "—", name: "신규 개발", examples: "새 기능이나 새 시스템", points: "별도 견적" },
  ],
  notes: [
    "납품한 코드의 결함은 구독 중이면 포인트를 차감하지 않고 고칩니다.",
    "개발 후 서버 운영까지 맡기시는 경우 기본 관리 이상의 구독이 필요합니다.",
    "서버·AI 사용료·도메인 같은 외부 비용은 실비로 별도입니다.",
    "무상 하자보수 기간(잔금 후 3주)이 끝나면 이어서 시작하고, 1개월 단위로 해지할 수 있습니다.",
    "포인트를 넘는 작업의 건별 요금과 운영환경 변경·신규 개발 비용은 상담 후 안내드립니다.",
  ],
};
