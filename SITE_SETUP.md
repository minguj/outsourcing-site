# 메인 사이트 기능 설정 (AI 상담 · 문의 알림 · 견적 결제 · 관리 화면)

메인 페이지(`/`)는 서비스 소개, AI 상담봇, 발주서 데모 소개, 진행 방식, 상담 접수 양식으로 구성된다. 회사명 등 문구는 `frontend/src/app/site-config.ts` 한 곳에서 바꾼다.

| 경로 | 용도 |
| --- | --- |
| `/` | 메인 페이지. AI 상담 기록지에서 의뢰 내용·예산·일정을 정리하고 바로 접수 |
| `/en` | 영문 메인 페이지 (보류 중: 한국어 페이지의 English 버튼을 숨기고 검색 노출을 막아 두었다. 주소로 직접 들어가면 보인다) |
| `/admin` | 관리 화면. 접수 목록·상담 요약·대화 기록 확인, 상태·메모, 견적서 링크 발행 |
| `/quote?t=…` | 고객용 견적서. 착수금 결제(토스페이먼츠) |
| `/quote/success`, `/quote/fail` | 결제창에서 돌아오는 주소. 성공 시 서버가 금액·주문번호를 검증하고 승인 |

## 영문 사이트 (`/en`)

- 화면 문구는 `frontend/src/app/_site/i18n.ts`(버튼·안내 문구), `site-content.ts`의 `*_EN`(서비스·진행 방식·FAQ), `site-config.ts`의 `SITE_EN`(회사 소개·개인정보 안내)에 있다. 영문 회사명은 화면은 `SITE_EN.name`, 서버(AI 상담·메일)는 `COMPANY_NAME_EN`(기본 FitAgent)으로 맞춘다.
- AI 상담은 영문 페이지에서 오면 같은 한국어 회사 정보를 영어로 옮겨 답하고, 요약(브리프)도 영어로 만든다. 별도 영문 지식 파일을 관리하지 않아도 된다.
- 영문 페이지에서 접수된 상담은 관리 화면에 `EN`/`영문 고객`으로 표시되고, 고객 메일(접수 확인·견적서·결제 완료)과 견적서 화면이 영어로 나간다. 견적서 제목·항목·안내 문구는 관리자가 쓴 그대로 나가므로 영어로 적는다. 금액은 원화(KRW)이고 결제창은 토스페이먼츠(국내 카드) 그대로다.
- 서버 오류 메시지는 한국어로 되어 있어 영문 페이지에서는 상태별 영어 안내로 바꿔 보여 준다.
- 발주서 변환 데모(`/demo/purchase-orders`)는 아직 한국어 화면·샘플만 있다.

## 상담봇 지식과 자주 묻는 질문

- 대표 경력(`PROFILE`)과 결제 조건·계약·하자보수·운영비 같은 운영 기준(`POLICIES`)은 `backend/site_knowledge.py`에만 있고 AI 상담이 이 기준대로만 답한다. 금액은 어떤 경우에도 말하지 않는다.
- 자주 묻는 질문은 세 번째 값(`chip`)이 참인 것만 상담 기록지 버튼으로 나오고, 나머지는 메인의 자주 묻는 질문 목록과 AI 지식에만 쓰인다.
- 회사 소개·서비스·진행 과정·자주 묻는 질문·결제 후 진행 안내는 `backend/site_knowledge.py`(AI 상담 프롬프트와 메일)와 `frontend/src/app/site-content.ts`(화면) 두 곳에 있다. 문구를 바꿀 때는 함께 맞춘다.
- 방문자가 상담 기록지에서 대화한 뒤 메인 하단 상담 접수 양식을 쓰면 "AI 상담 내용 함께 보내기"(기본 체크)가 나타나 요약·대화 기록이 함께 접수된다. 요약이 없으면 의뢰 내용은 직접 적어야 한다. 알림 메일에 고객 메시지 수가 표시되고 전체 대화는 관리 화면에서 본다.
- 상담 기록지의 자주 묻는 질문 버튼은 화면에 있는 답을 바로 보여 준다. AI를 부르지 않으므로 토큰이 들지 않고 API 키가 없어도 동작한다. 자유 질문만 AI가 같은 회사 정보를 바탕으로 답한다.
- 회사 정보 프롬프트는 대화마다 같으므로 프롬프트 캐시를 켜 두었다.

## 고객 메일과 결제 체험

- 상담 접수 시 고객에게 접수 확인 메일, 관리 화면에서 견적서를 만들 때 "메일로 보내기"를 켜 두면 견적서 링크 메일, 착수금 결제가 끝나면 결제 완료와 진행 안내 메일이 간다. 고객 메일의 회신 주소는 `NOTIFY_EMAIL`이다. 견적서 메일에는 `PUBLIC_BASE_URL`이 필요하다.
- 메인과 상담 기록지의 "견적·결제 흐름 체험"은 체험용 견적서를 서버 메모리에만 2시간 만들어 둔다. 관리 화면·DB·메일에 남지 않고, 결제는 토스 테스트 키가 있으면 테스트 결제창, 없거나 실결제(live) 키면 모의 결제로만 진행되어 어떤 경우에도 청구되지 않는다. IP당 시간당 10회로 제한한다.

## 상담 접수 첨부 파일

- 상담 접수 양식에서 기획서·참고 자료를 파일당 10MB, 최대 3개까지 받는다. 허용 형식: PDF, 워드, 파워포인트, 엑셀, CSV, 한글(hwp/hwpx), 텍스트, PNG/JPG, ZIP.
- 파일은 `DATA_DIR/uploads/<상담번호>/`에 서버가 정한 이름으로 저장되고(운영: 데이터 볼륨의 `/app/data/uploads`), 관리 화면에서 로그인한 관리자만 내려받는다. 항상 다운로드로만 내려가고 브라우저에서 바로 열리지 않는다.
- 저장 실패(형식·크기·개수 초과) 시 상담 접수 자체를 되돌린다. 전체 첨부 용량 상한은 `UPLOADS_MAX_TOTAL_MB`(기본 2048MB).

## 서버 비밀값

EC2의 `/etc/outsourcing-deploy/backend.env`에 넣는다(`backend.env.example` 참고, `chmod 600`). 모든 값은 선택이며 없으면 해당 기능만 꺼진다.

- AI 상담: `ANTHROPIC_API_KEY` (없으면 자주 묻는 질문 버튼과 문의 양식 안내만 동작한다). 비용 상한 `CONSULT_DAILY_LIMIT`, IP당 시간당 40회, 대화당 20턴 제한.
- 알림 메일: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL` (+ `SMTP_FROM`, `PUBLIC_BASE_URL`). Gmail은 2단계 인증 후 앱 비밀번호를 쓴다. EC2는 25번 포트가 막혀 있으므로 587 또는 465를 쓴다.
- 관리 화면: `ADMIN_PASSWORD` (8자 이상). 없으면 관리 화면 로그인이 잠긴다.
- 결제: `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY` (토스페이먼츠 개발자센터의 **API 개별 연동 키**, 결제위젯 키 아님). 로컬에서 키 없이 결제 흐름만 보려면 `PAYMENT_MOCK=1`(운영 서버에는 넣지 않음). `test_` 키는 실제로 청구되지 않으며 견적서에 "테스트 결제" 표시가 나온다. 사업자 계약 후 `live_` 키로 바꾼다.

**반영 시점:** 배포 스크립트가 배포 순간의 `backend.env` 값을 릴리스 설정에 고정한다. 값을 바꾼 뒤에는 다음 main 배포에서 반영된다. 이미 배포한 같은 커밋은 다시 배포하지 않으므로, 값만 바꿨다면 작은 커밋을 하나 main에 올려 배포를 다시 돌린다.

## 데이터

상담·견적·결제 기록은 backend 컨테이너의 `/app/data/site.db`(SQLite), 첨부 파일은 `/app/data/uploads`에 저장되고, Compose 볼륨 `outsourcing-site_backend_data`로 배포·롤백과 무관하게 유지된다. 백업은 EC2에서 다음과 같이 한다.

```bash
# 상담 기록(DB)과 첨부 파일을 함께 백업
sudo docker run --rm -v outsourcing-site_backend_data:/data -v "$PWD":/backup alpine tar czf /backup/site-data-$(date +%F).tgz -C /data .
```

개인정보 보유 기간 안내(상담 종료 후 1년)는 `site-config.ts`의 문구와 실제 운영을 맞춘다.

## 로컬 실행

기존 두 터미널 실행 방법(`dev/purchase_order_demo/README.md`)과 같다. 기능을 켜려면 백엔드를 띄우기 전에 PowerShell에서 환경변수를 설정한다.

```powershell
$env:ADMIN_PASSWORD="local-admin-pass"
$env:ANTHROPIC_API_KEY="sk-ant-..."   # 선택
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

로컬 데이터는 저장소의 `data/`(git 제외)에 저장된다.

## 테스트

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

`backend/tests/test_site.py`는 Claude API·SMTP·토스 승인을 대체해 상담 응답·요약, 입력 검증·속도 제한, 접수·알림, 관리자 인증, 견적 발행, 금액·주문번호 위조 차단과 결제 멱등성을 확인한다.
