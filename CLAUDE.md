# 핏에이전트 (fitagent.co.kr)

AI 상담 → 요약 → 접수 → 견적서 → 계약 → 결제 흐름을 갖춘 웹 서비스.
현재 "외주 개발사 사이트"에서 "AI 상담 접수 시스템 제품 데모"로 피벗 중이다.

## 소통 규칙
- 답변과 설명은 한국어로 한다.
- 커밋, push, 배포는 사용자가 요청할 때만 한다.
- 새 브랜치를 만들기 전에는 먼저 main을 최신화하도록 안내한다. 사용자에게 아래 순서를 보여 주고, 커밋 안 된 변경이 있으면 먼저 알린다.
  `git checkout main` → `git pull origin main` → `git checkout -b <브랜치명>`
- 커밋 메시지는 한국어 한 줄로 쓰고, Claude·세션·Co-Authored-By 같은 문구는 넣지 않는다.
- 비밀번호, API 키, Gmail 앱 비밀번호를 대화나 파일에 적지 않는다. `.env`, `backend.env`는 읽거나 고치지 않는다.
- 운영 서버 설정에 `PAYMENT_MOCK`을 넣지 않는다.

## 구조
- `frontend/` Next.js 16 App Router
  - `src/app/_site/` 랜딩(landing.tsx), AI 채팅(consult-chat.tsx), 문의 양식(inquiry-form.tsx), 문구(i18n.ts), 스타일(site.css), GA(analytics.tsx)
  - `src/app/site-content.ts` 화면 FAQ·요금제 등 콘텐츠, `site-config.ts` 사이트 주소·GA ID·정책 시행일
  - `src/app/admin/` 관리자 (상담 접수, AI 상담 기록 consult-log.tsx)
  - `src/app/quote`, `contract` 견적서·계약 (고객별 토큰 주소, GA 수집 제외)
  - `src/app/demo/` 작업 예시 데모 (tower: 입주기업 플랫폼 샘플, 브랜드명 쓰지 않음)
  - `src/app/privacy/` 개인정보처리방침
- `backend/` FastAPI + SQLite (`DATA_DIR/site.db`)
  - `consult.py` Claude API 호출과 시스템 프롬프트
  - `site_knowledge.py` AI 상담이 아는 내용(FAQ·정책). 화면 FAQ(site-content.ts)와 내용을 맞춰 둔다
  - `site_api.py` API, `site_store.py` DB (AI 상담 기록은 기본 90일 보관, `CONSULT_RETENTION_DAYS`)
- `Caddyfile`, `compose.yaml` 배포 구성. `ops/` 백업 스크립트(서버 미설치)

## 배포
- main에 push → GitHub Actions → EC2(시드니) self-hosted runner → Docker Compose(Caddy 포함) 재배포.
- compose 프로젝트 이름 `outsourcing-site`, 데이터 볼륨 `outsourcing-site_backend_data`. 볼륨을 지우는 명령은 절대 실행하지 않는다.
- 자세한 내용: DEPLOYMENT.md, RUNNER_DEPLOYMENT.md, SITE_SETUP.md

## 작업 규칙
- 줄바꿈: ts/tsx/py/md/css는 기존 CRLF를 유지한다. sh/yaml/Caddyfile은 LF(.gitattributes).
- 검색 노출: robots.ts에서 /admin, /quote, /contract, /en, /api/, /demo/tower 제외 유지.
- GA: 비공개 경로(/admin, /quote, /contract)는 수집하지 않는다. page_view에는 utm_* 등 유입 파라미터만 남긴다.
- 개인정보를 새로 수집·보관하는 변경을 하면 privacy/page.tsx와 site-config.ts의 시행일도 함께 고친다.
- 화면 FAQ를 바꾸면 backend/site_knowledge.py도 같이 맞춘다.

## 확인 방법
- 백엔드 테스트 (저장소 루트, PowerShell):
  `$env:DATA_DIR="$env:TEMP\fitagent-test"; python -m pytest -q backend/tests`
- 프론트 타입 검사: `cd frontend; npx tsc --noEmit`
- 큰 변경은 Plan 모드로 계획을 먼저 보여 주고 승인받은 뒤 진행한다.
