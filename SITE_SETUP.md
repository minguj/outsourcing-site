# 메인 사이트 기능 설정 (AI 상담 · 문의 알림 · 견적 결제 · 관리 화면)

메인 페이지(`/`)는 서비스 소개, AI 상담봇, 발주서 데모 소개, 진행 방식, 상담 접수 양식으로 구성된다. 회사명 등 문구는 `frontend/src/app/site-config.ts` 한 곳에서 바꾼다.

| 경로 | 용도 |
| --- | --- |
| `/` | 메인 페이지. AI 상담 기록지에서 의뢰 내용·예산·일정을 정리하고 바로 접수 |
| `/admin` | 관리 화면. 접수 목록·상담 요약·대화 기록 확인, 상태·메모, 견적서 링크 발행 |
| `/quote?t=…` | 고객용 견적서. 착수금 결제(토스페이먼츠) |
| `/quote/success`, `/quote/fail` | 결제창에서 돌아오는 주소. 성공 시 서버가 금액·주문번호를 검증하고 승인 |

## 서버 비밀값

EC2의 `/etc/outsourcing-deploy/backend.env`에 넣는다(`backend.env.example` 참고, `chmod 600`). 모든 값은 선택이며 없으면 해당 기능만 꺼진다.

- AI 상담: `ANTHROPIC_API_KEY` (없으면 예시 대화와 문의 양식 안내가 보인다). 비용 상한 `CONSULT_DAILY_LIMIT`, IP당 시간당 40회, 대화당 20턴 제한.
- 알림 메일: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL` (+ `SMTP_FROM`, `PUBLIC_BASE_URL`). Gmail은 2단계 인증 후 앱 비밀번호를 쓴다. EC2는 25번 포트가 막혀 있으므로 587 또는 465를 쓴다.
- 관리 화면: `ADMIN_PASSWORD` (8자 이상). 없으면 관리 화면 로그인이 잠긴다.
- 결제: `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY` (토스페이먼츠 개발자센터의 **API 개별 연동 키**). `test_` 키는 실제로 청구되지 않으며 견적서에 "테스트 결제" 표시가 나온다. 사업자 계약 후 `live_` 키로 바꾼다.

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
