# 메인 사이트 기능 설정 (AI 상담 · 문의 알림 · 견적 결제 · 관리 화면)

메인 페이지(`/`)는 서비스 소개, AI 상담봇, 발주서 데모 소개, 진행 방식, 상담 접수 양식으로 구성된다. 회사명 등 문구는 `frontend/src/app/site-config.ts` 한 곳에서 바꾼다.

| 경로 | 용도 |
| --- | --- |
| `/` | 메인 페이지. AI 상담 기록지에서 의뢰 내용·예산·일정을 정리하고 바로 접수 |
| `/admin` | 관리 화면. 접수 목록·상담 요약·대화 기록 확인, 상태·메모, 견적서 링크 발행 |
| `/quote?t=…` | 고객용 견적서. 착수금 결제(토스페이먼츠) |
| `/quote/success`, `/quote/fail` | 결제창에서 돌아오는 주소. 성공 시 서버가 금액·주문번호를 검증하고 승인 |

## 상담봇 지식과 자주 묻는 질문

- 회사 소개·서비스·진행 과정·자주 묻는 질문·결제 후 진행 안내는 `backend/site_knowledge.py`(AI 상담 프롬프트와 메일)와 `frontend/src/app/site-content.ts`(화면) 두 곳에 있다. 문구를 바꿀 때는 함께 맞춘다.
- 상담 기록지의 자주 묻는 질문 버튼은 화면에 있는 답을 바로 보여 준다. AI를 부르지 않으므로 토큰이 들지 않고 API 키가 없어도 동작한다. 자유 질문만 AI가 같은 회사 정보를 바탕으로 답한다.
- 회사 정보 프롬프트는 대화마다 같으므로 프롬프트 캐시를 켜 두었다.

## 고객 메일과 결제 체험

- 상담 접수 시 고객에게 접수 확인 메일, 관리 화면에서 견적서를 만들 때 "메일로 보내기"를 켜 두면 견적서 링크 메일, 착수금 결제가 끝나면 결제 완료와 진행 안내 메일이 간다. 고객 메일의 회신 주소는 `NOTIFY_EMAIL`이다. 견적서 메일에는 `PUBLIC_BASE_URL`이 필요하다.
- 메인과 상담 기록지의 "견적·결제 흐름 체험"은 체험용 견적서를 서버 메모리에만 2시간 만들어 둔다. 관리 화면·DB·메일에 남지 않고, 결제는 토스 테스트 키가 있으면 테스트 결제창, 없거나 실결제(live) 키면 모의 결제로만 진행되어 어떤 경우에도 청구되지 않는다. IP당 시간당 10회로 제한한다.

## 서버 비밀값

EC2의 `/etc/outsourcing-deploy/backend.env`에 넣는다(`backend.env.example` 참고, `chmod 600`). 모든 값은 선택이며 없으면 해당 기능만 꺼진다.

- AI 상담: `ANTHROPIC_API_KEY` (없으면 자주 묻는 질문 버튼과 문의 양식 안내만 동작한다). 비용 상한 `CONSULT_DAILY_LIMIT`, IP당 시간당 40회, 대화당 20턴 제한.
- 알림 메일: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL` (+ `SMTP_FROM`, `PUBLIC_BASE_URL`). Gmail은 2단계 인증 후 앱 비밀번호를 쓴다. EC2는 25번 포트가 막혀 있으므로 587 또는 465를 쓴다.
- 관리 화면: `ADMIN_PASSWORD` (8자 이상). 없으면 관리 화면 로그인이 잠긴다.
- 결제: `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY` (토스페이먼츠 개발자센터의 **API 개별 연동 키**, 결제위젯 키 아님). 로컬에서 키 없이 결제 흐름만 보려면 `PAYMENT_MOCK=1`(운영 서버에는 넣지 않음). `test_` 키는 실제로 청구되지 않으며 견적서에 "테스트 결제" 표시가 나온다. 사업자 계약 후 `live_` 키로 바꾼다.

**반영 시점:** 배포 스크립트가 배포 순간의 `backend.env` 값을 릴리스 설정에 고정한다. 값을 바꾼 뒤에는 다음 main 배포에서 반영된다. 이미 배포한 같은 커밋은 다시 배포하지 않으므로, 값만 바꿨다면 작은 커밋을 하나 main에 올려 배포를 다시 돌린다.

## 데이터

상담·견적·결제 기록은 backend 컨테이너의 `/app/data/site.db`(SQLite)에 저장되고, Compose 볼륨 `outsourcing-site_backend_data`로 배포·롤백과 무관하게 유지된다. 백업은 EC2에서 다음과 같이 한다.

```bash
sudo docker run --rm -v outsourcing-site_backend_data:/data -v "$PWD":/backup alpine cp /data/site.db /backup/site-$(date +%F).db
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
