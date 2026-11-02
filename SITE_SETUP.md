# 메인 사이트 기능 설정 (AI 상담 · 문의 알림 · 견적 결제 · 관리 화면)

메인 페이지(`/`)는 서비스 소개, AI 상담봇, 발주서 데모 소개, 진행 방식, 상담 접수 양식으로 구성된다. 회사명 등 문구는 `frontend/src/app/site-config.ts` 한 곳에서 바꾼다.

| 경로 | 용도 |
| --- | --- |
| `/` | 메인 페이지. AI 상담 기록지에서 의뢰 내용·예산·일정을 정리하고 바로 접수 |
| `/en` | 영문 메인 페이지 (보류 중: 한국어 페이지의 English 버튼을 숨기고 검색 노출을 막아 두었다. 주소로 직접 들어가면 보인다) |
| `/admin` | 관리 화면. 접수 목록·상담 요약·대화 기록 확인, 상태·메모, 견적서 링크 발행 |
| `/quote?t=…` | 고객용 견적서. 실제 계약 대금(착수금 30%·중도금 50%·잔금 20%)은 계약서 작성 후 계좌이체로 받는다. 토스 결제는 체험 견적서에서 결제 연동 예시로 보여 준다 |
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

상담·견적·결제 기록은 backend 컨테이너의 `/app/data/site.db`(SQLite), 첨부 파일은 `/app/data/uploads`에 저장되고, Compose 볼륨 `outsourcing-site_backend_data`로 배포·롤백과 무관하게 유지된다.

### 자동 백업

`ops/backup.sh`가 매일 한국 시간 새벽 3시 20분쯤(systemd 타이머 `outsourcing-backup.timer`) 데이터 폴더 전체를 묶어 `/var/backups/outsourcing-site/site-<UTC 시각>.tar.gz`로 남긴다. DB는 실행 중에도 일관된 사본이 되도록 SQLite 백업 API로 복사한다. 서버 안 사본은 14일 보관한다.

`/etc/outsourcing-deploy/backup.env`(권한 600)에 다음을 넣으면 S3에도 올린다. EC2에는 해당 버킷에 `s3:PutObject`만 허용한 IAM 역할을 붙이고, 서버에 AWS CLI(`sudo snap install aws-cli --classic`)를 설치한다. S3 쪽 보관 기간은 버킷 수명 주기 규칙(예: 90일 후 삭제)으로 정한다.

```bash
BACKUP_S3_URI=s3://<버킷 이름>/site
# 선택: BACKUP_LOCAL_DIR=/var/backups/outsourcing-site  BACKUP_KEEP_DAYS=14
```

설치·수동 실행·확인:

```bash
sudo install -m 755 backup.sh /opt/outsourcing-deploy/backup.sh
sudo install -m 644 outsourcing-backup.service outsourcing-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now outsourcing-backup.timer
sudo systemctl start outsourcing-backup.service && sudo journalctl -u outsourcing-backup.service -n 20
systemctl list-timers outsourcing-backup.timer
```

복원(백업 시점으로 되돌린다. 그 뒤에 들어온 접수는 사라지므로 먼저 현재 상태도 백업한다):

```bash
sudo systemctl start outsourcing-backup.service          # 현재 상태 먼저 백업
mkdir -p /tmp/restore && sudo tar -xzf /var/backups/outsourcing-site/site-<시각>.tar.gz -C /tmp/restore
c=$(sudo docker ps -q --filter label=com.docker.compose.service=backend)
sudo docker stop "$c"
sudo docker cp /tmp/restore/data/. "$c":/app/data/
sudo docker start "$c"
```

개인정보 보유 기간 안내(상담 종료 후 1년)는 `site-config.ts`의 문구와 실제 운영을 맞춘다.

## 방문 분석 (Google Analytics 4)

`site-config.ts`의 `ANALYTICS.ga`에 GA4 측정 ID(`G-`로 시작)를 넣으면 공개 페이지에서만 수집을 시작한다. 비워 두면 스크립트를 아예 불러오지 않는다. 구현은 `frontend/src/app/_site/analytics.tsx`.

- 견적서·계약서·관리 화면(`/quote`, `/contract`, `/admin`)은 주소에 고객별 토큰이 있어 수집하지 않는다. 페이지 조회는 쿼리 문자열을 뺀 경로만 보낸다.
- GA4 관리 → 데이터 스트림 → 향상된 측정에서 **"브라우저 기록 이벤트 기반 페이지 변경"은 끈다.** 켜 두면 GA가 토큰이 붙은 주소를 직접 보낼 수 있다.
- 이름·연락처·상담 내용은 이벤트에 넣지 않는다. 개인정보처리방침 제7조에 수집 내용과 거부 방법을 적어 두었다.

보내는 이벤트(GA4 관리 → 이벤트에서 `inquiry_submit`과 `consult_brief`를 주요 이벤트로 표시하면 전환으로 볼 수 있다):

| 이벤트 | 언제 | 값 |
|---|---|---|
| `cta_click` | 상담·접수로 가는 버튼 | `target`(chat·inquiry), `where`(hero·mobile_bar·maintenance·examples·chat_offline) |
| `faq_click` | 상담창의 자주 묻는 질문 버튼 | `question` |
| `consult_start` | AI 상담에 첫 메시지 | `lang` |
| `consult_brief` | AI가 의뢰 요약을 만듦 | `project_type` |
| `inquiry_submit` | 상담 접수 완료 | `from`(chat·form), `with_chat`, `files` |
| `demo_quote_start` | 견적·결제 체험 시작 | `from` |

## 개인정보처리방침·이용약관·계약 문서

- `/privacy` 개인정보처리방침, `/terms` 이용약관·환불 규정. 운영자 정보와 시행일은 `site-config.ts`의 `OPERATOR`, `POLICY_EFFECTIVE`에서 바꾼다. 메인 하단과 상담 접수 동의 팝업에서 연결된다.
- 수집 항목, 위탁 업체(국외 이전), 보유 기간을 바꾸면 `privacy/page.tsx`와 `site-config.ts`의 `privacy` 안내문, 시행일을 함께 바꾼다.
- 환불 기준을 바꾸면 `terms/page.tsx`, 계약서(`contract/`), `site_knowledge.py`(운영 기준·FAQ), `site-content.ts`(FAQ)를 함께 맞춘다.
- 계약 문서 4종: `/contract`(외주 개발 계약서(안), 견적 토큰 필수), `/contract/nda`, `/contract/completion`, `/contract/maintenance`. 뒤의 셋은 `?t=견적토큰`이 있으면 고객사·과업명·금액을 채우고, 없으면 빈 양식이다. 모두 인쇄·PDF 저장과 Word(.doc) 저장을 지원하고, 관리 화면의 견적서 목록에서 바로 열 수 있다.

## 연락처·유지보수·국외 이전

- 카카오톡 문의 주소(채널 채팅 또는 1:1 오픈채팅)는 `site-config.ts`의 `CONTACT.kakao`에 넣는다. 값이 있으면 상담 접수 옆과 하단에 바로가기가 나오고, 비워 두면 숨긴다.
- 월 구독 유지보수 플랜(이름, 맞는 경우, 포함 내용, 안내 문구)은 `site-content.ts`의 `MAINTENANCE`에서 고친다. 금액은 공개하지 않는다. AI 상담이 쓰는 같은 내용은 `site_knowledge.py`의 `POLICIES`(유지보수 구독)에 있다.
- 상담 접수에는 개인정보 수집·이용 동의(필수)만 받는다. 동의 문구의 '개인정보 수집·이용'을 누르면 수집 항목·목적·보유 기간·처리 위탁(국외 처리 포함) 안내 팝업이 열린다. 국외 처리위탁(Anthropic·Google·AWS)은 개인정보 보호법 제28조의8 제1항 제3호(계약 체결·이행을 위한 처리위탁·보관)에 따라 별도 동의 대신 안내와 개인정보처리방침 공개로 알린다. 문구는 `site-config.ts`의 `privacy`에 있다.
- AI 상담 입력창 아래에는 'AI가 답변하는 상담이며 개인정보를 적지 말라'는 안내만 짧게 둔다.

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
