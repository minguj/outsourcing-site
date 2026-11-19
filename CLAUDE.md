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
  - `src/app/site-content.ts` 화면 동작 흐름·기술 구조·FAQ 콘텐츠, `site-config.ts` 사이트 주소·GA ID·키워드·정책 시행일
  - `src/app/contract/maintenance/` 유지보수 계약서(내용 유지, 공개 화면에서 링크하지 않음. 관리자 문서 바로가기로만 연다)
  - `src/app/admin/` 관리자 (상담 접수, AI 상담 기록 consult-log.tsx)
  - `src/app/quote`, `contract` 견적서·계약 (고객별 토큰 주소, GA 수집 제외)
  - `src/app/demo/` 작업 예시 데모 (tower: 입주기업 플랫폼 샘플(디렉토리·상가 쿠폰·회의실 예약, 브라우저 localStorage만 사용), 브랜드명 쓰지 않음)
    - nurse: 방문간호센터 홈페이지 샘플(홈페이지 /demo/nurse/site + 관리자 /demo/nurse/admin). 센터명 "늘곁방문간호센터"는 가상, CSS는 nc- 접두어, 상태는 localStorage(nurse-demo-v1)만 쓰고 백엔드 없음. 랜딩 썸네일은 public/samples/nurse/thumbnails/. 관리자 인증코드 메일만 실제 발송(`backend/nurse_demo.py`, `/api/demo/nurse/code·verify`, 고정 문구·IP/주소/하루 제한·코드는 메모리 10분). 예시 도메인(.example 등)이나 서버 미응답 시 데모 메일함으로 대체. 상담 신청 알림은 데모 기록만 남긴다
    - zeb: 건축 초기 기획(대지 규모 + ZEB 신재생 시나리오) 샘플. 검색 제외·공개 화면 미링크, CSS는 zb- 접두어. 백엔드는 `backend/zeb/`
    - pms: 운영 플랫폼(PMS) 샘플. 역할 전환·사업장 선택·운영 현황/호실/입주자/계약/청구·수납/회계 마감/민원/출입 연동/감사 기록 탭(3단계 탭은 _pms/tabs-ops.tsx). 검색 제외, 랜딩 데모 모음에서 링크(썸네일 public/samples/pms/thumbnails), CSS는 pm- 접두어(.pm-root 안). 백엔드는 `backend/pms/`
    - spend: 구독·고정지출 찾기 샘플. 가상 사용자 선택·월 고정지출 요약·구독 목록(근거·신호·사람 확인)·결제 예정 30일·원본 거래내역·절감 후보·알림. 검색 제외, 랜딩 데모 모음에서 링크(썸네일 public/samples/spend/thumbnails), CSS는 sp- 접두어(.sp-root 안). 백엔드는 `backend/spend/`
  - `src/app/privacy/` 개인정보처리방침
- `backend/` FastAPI + SQLite (`DATA_DIR/site.db`)
  - `consult.py` Claude API 호출과 시스템 프롬프트
  - `site_knowledge.py` AI 상담이 아는 내용(FAQ·정책). 화면 FAQ(site-content.ts)와 내용을 맞춰 둔다
  - `site_api.py` API, `site_store.py` DB (AI 상담 기록은 기본 90일 보관, `CONSULT_RETENTION_DAYS`)
  - `pms/` 운영 플랫폼(PMS) 데모: 여러 사업장을 위탁 운영하는 가상 운영사의 사업장·호실·계약·청구·수납, 역할 × 사업장 권한, 연락처 가림·건강정보 열람 제한·감사 기록 (`/api/demo/pms`). 방문자마다 가상 데이터 샌드박스를 메모리에 2시간만 두고 DB에 남기지 않는다. 계산(billing)·권한(access)·민원 규칙(voc)·연동(integration)·분개(ledger)는 I/O 없는 모듈로 분리. 민원 분류는 가린 문장만 Claude(voc_ai.py)에 보내고, 못 쓰면 키워드 규칙으로 대신한다. 자세한 내용: backend/pms/README.md
  - `spend/` 구독·고정지출 찾기 데모: 가상 거래내역에서 반복 결제를 감지(detect.py, I/O 없음)하고 가맹점 정리(merchants.py), 사전에 없는 가맹점은 Claude로 정리(enrich_ai.py, 결과는 서버 메모리에 재사용), 중복·절감 후보·결제 예정 계산(service.py). 방문자 입력 없음, 샌드박스 메모리 2시간. 자세한 내용: backend/spend/README.md
  - `zeb/` 초기 기획 데모 계산 엔진·규칙 YAML·브이월드 어댑터 (`/api/demo/zeb`). 키가 없으면 샘플 필지로 동작. 브이월드는 해외 서버 IP를 막으므로 브라우저가 조회하고 서버는 해석·계산만 한다. 조례 개정은 `zeb/ordinance/`가 매일 감지해 수정안 PR을 연다(.github/workflows/ordinance-watch.yml, 승인은 사람). 전국 시도·시군 조례는 같은 워크플로의 mode=collect로 일괄 수집해 `rules/zoning_collected.yaml`(미검증)에 둔다. 자세한 내용: backend/zeb/README.md
- `Caddyfile`, `compose.yaml` 배포 구성. `ops/` 백업 스크립트(서버 미설치)

## 배포
- main에 push → GitHub Actions → EC2(시드니) self-hosted runner → Docker Compose(Caddy 포함) 재배포.
- compose 프로젝트 이름 `outsourcing-site`, 데이터 볼륨 `outsourcing-site_backend_data`. 볼륨을 지우는 명령은 절대 실행하지 않는다.
- 자세한 내용: DEPLOYMENT.md, RUNNER_DEPLOYMENT.md, SITE_SETUP.md

## 작업 규칙
- 줄바꿈: ts/tsx/py/md/css는 기존 CRLF를 유지한다. sh/yaml/Caddyfile은 LF(.gitattributes).
- 검색 노출: robots.ts에서 /admin, /quote, /contract, /en, /api/, /demo/tower, /demo/zeb, /demo/nurse, /demo/pms, /demo/spend 제외 유지.
- GA: 비공개 경로(/admin, /quote, /contract)는 수집하지 않는다. page_view에는 utm_* 등 유입 파라미터만 남긴다.
- 개인정보를 새로 수집·보관하는 변경을 하면 privacy/page.tsx와 site-config.ts의 시행일도 함께 고친다.
- 화면 FAQ를 바꾸면 backend/site_knowledge.py도 같이 맞춘다.
- backend에 하위 패키지(폴더)를 추가하면 backend/Dockerfile에 COPY 줄도 추가한다. 빠지면 배포 때 백엔드가 뜨지 않는다(test_pms_demo의 DeployPackagingTests가 확인).

## 확인 방법
- 백엔드 테스트 (저장소 루트, PowerShell). pytest는 설치되어 있지 않아서 `backend\.venv`의 unittest로 돌린다.
  `$env:DATA_DIR="$env:TEMP\fitagent-test"; .\backend\.venv\Scripts\python.exe -c "import functools,sys,tempfile,unittest; T=tempfile.TemporaryDirectory; T.__init__=functools.partialmethod(T.__init__, ignore_cleanup_errors=True); r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromNames(['backend.tests.test_site','backend.tests.test_purchase_demo','backend.tests.test_zeb_demo','backend.tests.test_zeb_ordinance','backend.tests.test_zeb_collect','backend.tests.test_nurse_demo','backend.tests.test_pms_demo','backend.tests.test_spend_demo'])); sys.exit(not r.wasSuccessful())"`
  - Windows에서는 테스트가 끝날 때 임시 폴더의 site.db가 잠겨 있어 정리 단계에서 `PermissionError`(WinError 32)가 난다. 위 명령은 이 정리 오류만 무시한다. 테스트 본문의 실패는 그대로 잡힌다.
  - 테스트 파일을 새로 만들면 위 목록(`backend.tests.…`)에 추가한다.
- 프론트 타입 검사: `cd frontend; npx tsc --noEmit`
- 큰 변경은 Plan 모드로 계획을 먼저 보여 주고 승인받은 뒤 진행한다.
