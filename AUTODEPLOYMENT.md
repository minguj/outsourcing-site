# EC2 자동 배포 운영

> 현재 전환 대상은 [self-hosted runner 방식](RUNNER_DEPLOYMENT.md)이다. 아래 내용은 이전 polling 방식 참고 기록이며, runner 사용 전 polling timer를 중지·비활성화한다. 아래 polling 설치 절차를 다시 실행하지 않는다.

GitHub Actions가 이미지를 빌드·GHCR 게시하고 smoke까지 통과하면, EC2의 systemd timer가 2분마다 확인해 배포한다. AWS 서비스 추가, 고급 기능 활성화, 유료 플랜 전환, SSH 인바운드 변경은 하지 않는다.

## 배포 조건

- 현재 `main` HEAD와 일치하는 `images.yml`의 `push` 실행만 인정한다.
- 실행 전체가 completed/success이고 frontend/backend 빌드 및 smoke 작업도 각각 성공해야 한다.
- 이미지 다운로드 후 HEAD와 실행 결과를 다시 확인한다. 다운로드 도중 main이 바뀌면 해당 배포를 건너뛴다.
- `/var/lib/outsourcing-deploy/state.json`의 성공 SHA와 같으면 건너뛴다.
- systemd oneshot과 flock 잠금으로 중복 실행을 막는다.
- 실패한 SHA는 반복 장애를 줄이기 위해 30분 후 재시도한다. 새 SHA는 다음 2분 주기에 확인한다.

## 토큰 두 개: 서버에서만 입력

1. GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens에서 생성한다. Resource owner는 minguj, Repository access는 **Only select repositories → outsourcing-site**로 한정한다. Repository permissions는 **Actions: Read-only**, **Contents: Read-only**만 설정한다. Metadata 읽기는 기본 포함된다. 합리적인 만료일을 설정한다.
2. Tokens (classic)에서 별도 토큰을 생성한다. **read:packages만** 선택하고 repo, write:packages, delete:packages는 부여하지 않는다. 토큰 계정에 두 GHCR 패키지 읽기 권한이 있어야 한다. 조직 SSO가 적용되면 승인한다.

최소 권한을 분리하기 때문에 토큰이 두 개다. classic repo 토큰 하나로 합치면 저장소 쓰기까지 허용할 수 있어 사용하지 않는다. 토큰을 채팅, 명령행 인자, GitHub Secrets, 저장소 파일에 붙여넣지 않는다.

PC PowerShell에서 대화형 SSH로 접속한다.

```powershell
ssh -i "C:\Users\mingu\OneDrive\Desktop\outsourcing-web-key.pem" ubuntu@16.176.219.121
```

EC2 터미널에서 입력 도구를 실행한다. 입력은 화면에 표시되지 않는다.

```bash
sudo python3 /opt/outsourcing-deploy/credentials.py
```

저장 위치는 `/etc/outsourcing-deploy/github-api-token`, `/etc/outsourcing-deploy/ghcr-token`이다. 폴더 700, 파일 600, 소유자 root로 제한한다. 토큰은 프로세스 인자나 환경변수에 넣지 않는다. GHCR 인증은 root 전용 임시 Docker 설정에만 작성하고 이미지 pull 후 삭제한다. API 인증 헤더와 명령의 stdout/stderr를 로그로 출력하지 않는다. 토큰 만료 시 같은 입력 도구로 교체한다.

## 서버 설치 및 파일

`ops/install.sh`를 root로 실행하면 `/opt/outsourcing-deploy`에 프로그램을 설치하고 timer와 재부팅 복구 서비스를 활성화한다. 토큰이 없으면 배포하지 않고 종료한다. Docker, Compose, Python 3.12, systemd 외의 추가 패키지는 필요 없다.

- 실행 코드: `/opt/outsourcing-deploy/poller.py` (root만 수정 가능)
- 백엔드 환경: `/etc/outsourcing-deploy/backend.env` (현재 앱은 값 불필요)
- 성공 상태·배포 잠금·진행 기록: `/var/lib/outsourcing-deploy/`
- SHA별 설정과 고정 이미지 ID: `/var/lib/outsourcing-deploy/releases/<SHA>/`
- 배포 직전 설정·Caddyfile·이미지 ID: `/var/lib/outsourcing-deploy/backups/<시각>/`

배포 파일은 성공한 SHA에서 compose.yaml과 Caddyfile만 다운로드한다. 저장소의 Python/셸 코드를 자동 실행하지 않는다. 조회 프로그램을 변경한 경우 검토·테스트 후 root 설치를 별도로 갱신한다.

## 최초 배포와 롤백

이전 Caddy 백업 `/home/ubuntu/outsourcing-site-backups/20261028T102154Z-2853`을 확인했다. 최초 배포 전 기존 `web` 컨테이너의 실제 이미지와 Caddyfile, Compose를 다시 저장한다. 전체 실행 서비스가 백업되지 않으면 배포하지 않는다.

새 릴리스는 별도 디렉터리에 준비하고 모든 이미지 pull 및 Caddy 설정 검증을 마친 후 실행 서비스를 전환한다. 기존 ~/outsourcing-site 파일은 덮어쓰지 않는다. Compose 프로젝트명은 outsourcing-site로 유지하며 기존 web 서비스는 새 caddy 서비스로 전환한다. 볼륨은 삭제하지 않는다.

실행 후 컨테이너 health, Caddy reload, `GET /`의 200 응답, `GET /api/health`의 `{"status":"ok"}`를 확인한 뒤 성공 SHA를 원자적으로 기록한다. 교체 중 짧은 서비스 중단이 있을 수 있다.

실패하면 백업한 **실제 이미지 ID**와 **Compose/Caddy 설정**으로 복구한다. 롤백은 pull 없이 로컬 이미지로 실행한다. 최초 Caddy만 있던 상태로 복구할 때는 `/`를, 기존 전체 앱 배포로 복구할 때는 두 경로를 확인한다. 롤백도 실패하면 진행 기록을 보존해 다음 실행에서 다시 복구한다.

재부팅 시 Docker restart policy가 컨테이너를 시작하고 outsourcing-restore.service가 미완료 배포 복구 또는 마지막 성공 설정을 적용한다. timer는 enable되어 있으며 Persistent=true로 놓친 실행을 보완한다. 실제 EC2 재부팅은 별도 수행하지 않았다.

## 상태 확인

```bash
sudo systemctl status outsourcing-poll.timer --no-pager
sudo systemctl list-timers outsourcing-poll.timer --no-pager
sudo journalctl -u outsourcing-poll.service -n 30 --no-pager
sudo cat /var/lib/outsourcing-deploy/state.json
curl -f http://127.0.0.1/
curl -f http://127.0.0.1/api/health
```

성공 상태 파일에는 SHA와 경로만 있으며 토큰은 없다. `/etc/outsourcing-deploy`의 토큰 파일은 cat하거나 로그에 복사하지 않는다.

```bash
# 다음 주기까지 기다리지 않고 즉시 조회
sudo systemctl start outsourcing-poll.service
# 자동 조회 중지(현재 실행 중인 배포를 강제 종료하지 않음)
sudo systemctl stop outsourcing-poll.timer
```

장애 SHA를 수정해 main에 push하면 성공한 새 SHA가 자동 배포된다. 현재 사용 중인 이미지, 직전 롤백 이미지와 releases/backups 디렉터리는 삭제하지 않는다. 30GB EBS에서 이미지가 쌓이므로 디스크 사용량을 주기적으로 확인한다. 폴링은 별도 상주 runner 없이 실행되지만 기존 EC2/EBS/네트워크 사용과 GitHub 요금 한도는 계속 적용된다.

참고: [Actions 조회 권한](https://docs.github.com/en/rest/actions/workflow-runs), [GHCR 인증](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
