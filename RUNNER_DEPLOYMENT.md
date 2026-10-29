# self-hosted runner 배포 전환

이번 작업은 로컬 수정·검증만 수행한다. 아래 서버 명령은 아직 실행하지 않았다. 이전 polling 코드와 설정 파일은 보존한다.

## 실행 흐름

테스트, 이미지 빌드·GHCR 게시, smoke는 기존처럼 GitHub-hosted ubuntu-latest에서 실행한다. 같은 워크플로의 deploy job만 `[self-hosted, Linux, X64, outsourcing-deploy]`를 사용한다. 등록된 runner 이름은 outsourcing-ec2-deploy, 실행 사용자는 ubuntu다.

deploy는 deployment-agent, build, smoke가 모두 성공한 **main push**에서만 실행한다. PR과 workflow_dispatch에서는 실행하지 않는다. 워크플로와 deploy job은 진행 중인 실행을 새 push 때문에 취소하지 않는다. GitHub concurrency는 FIFO를 보장하지 않으며 대기 실행이 교체될 수 있으므로, 모든 중간 커밋이 반드시 배포되는 것은 아니다.

EC2 job에는 checkout, 빌드, 패키지 설치, 토큰 읽기가 없다. github.sha만 받아 고정된 root 소유 명령을 실행한다.

```bash
sudo -n /usr/local/sbin/outsourcing-deploy-sha "$DEPLOY_SHA"
```

진입점은 40자리 소문자 SHA 하나만 허용하며 `/opt/outsourcing-deploy/poller.py --sha <SHA>`를 호출한다. 이 모드는 최신 main을 조회하지 않고, 전달받은 SHA의 이미지와 Compose/Caddy 설정만 사용한다. deploy가 실행 중이면 워크플로 전체는 아직 완료되지 않았으므로 전체 워크플로 성공을 다시 조회하지 않는다. 선행 job 성공 여부는 workflow needs로 보장한다.

## 재사용하는 기능

- 기존 deploy.lock과 상태·백업·pending 기록을 공유한다. 잠금 충돌은 Actions 성공으로 처리하지 않고 실패를 반환한다.
- 이미 성공한 SHA는 두 HTTP 경로 health 확인 후 재배포를 건너뛴다.
- 배포 직전 실제 이미지 ID와 Compose·Caddy 설정을 저장한다.
- 배포 후 `/`의 200 응답과 `/api/health`의 `{"status":"ok"}`를 확인한다.
- 실패하면 이전 이미지와 설정으로 pull 없이 롤백한다. 최초 Caddy만 있던 상태는 `/`를 확인한다.
- 중단된 배포는 pending 기록으로 복구한다. 기존 재부팅 복구 서비스는 유지한다.
- Actions 명시적 재시도에는 polling용 30분 실패 cooldown을 적용하지 않는다.

## 필요한 서버 설정

검토한 파일을 별도로 서버에 전달한 뒤 관리자 터미널에서 아래를 실행한다. `<검토한_소스_경로>`는 실제 경로로 바꾼다. runner 작업에서 자동으로 배포 도구를 root 설치하지 않는다.

### 1. polling 중지와 진행 중 작업 확인

```bash
sudo systemctl disable --now outsourcing-poll.timer
sudo systemctl is-active outsourcing-poll.service
sudo systemctl is-active outsourcing-restore.service
```

서비스가 active/activating이면 **완료될 때까지 기다린다**. 진행 중인 배포를 강제로 중지하지 않는다. inactive일 때 다음 단계로 간다. is-active는 inactive일 때 종료 코드 3을 반환하므로 위 명령은 수동 확인용이다.

기존 Caddy 백업 `/home/ubuntu/outsourcing-site-backups/20261028T102154Z-2853`과 `/var/lib/outsourcing-deploy/backups`는 유지한다.

### 2. root 소유 코드 갱신

```bash
cd <검토한_소스_경로>
sudo bash ops/install-runner.sh
```

이 스크립트는 poller.py와 deploy-sha.sh만 root 소유로 설치한다. 서버에서 앱 빌드나 패키지 설치를 하지 않고 토큰 권한도 변경하지 않는다. polling이 실행 중이면 설치를 거부한다.

**기존 ops/install.sh는 polling 설치용이므로 실행하지 않는다.** 실행하면 timer가 다시 활성화된다. root 진입점도 polling timer가 active이면 배포를 거부한다.

### 3. 제한된 sudo 허용

```bash
sudo visudo -cf ops/outsourcing-deploy.sudoers
sudo install -o root -g root -m 440 ops/outsourcing-deploy.sudoers /etc/sudoers.d/outsourcing-deploy
sudo visudo -c
sudo -l -U ubuntu
```

허용 규칙은 아래 명령 하나로 제한하고, 인자는 root 소유 진입점에서 검증한다.

```sudoers
ubuntu ALL=(root) NOPASSWD: NOSETENV: /usr/local/sbin/outsourcing-deploy-sha *
```

sudo python3, sudo env 또는 runner workspace의 스크립트를 임의로 실행하는 규칙을 추가하지 않는다. /opt/outsourcing-deploy와 설치한 진입점을 ubuntu가 수정할 수 없도록 유지한다. 기존 ubuntu 계정에 광범위한 sudo 권한이 있다면 이 규칙이 그 권한을 회수하지는 않는다.

### 4. root 전용 토큰 유지

`/etc/outsourcing-deploy`는 root 소유 700, 토큰 파일은 root 소유 600을 유지한다. ubuntu에 그룹 읽기, ACL, 토큰 복사본을 제공하지 않는다.

- github-api-token: Fine-grained PAT, outsourcing-site 저장소의 **Contents: Read-only**. 해당 SHA의 설정 다운로드용이다. 기존 polling용 Actions 읽기 권한은 runner 방식에 필요 없다.
- ghcr-token: PAT classic의 **read:packages**만 부여하고 두 비공개 패키지 읽기 접근을 허용한다.

기존 유효한 토큰은 그대로 사용한다. 교체가 필요할 때만 관리자 SSH 터미널의 숨김 입력 도구를 사용한다. 채팅·Git·명령행 인자에는 토큰을 넣지 않는다.

```bash
sudo python3 /opt/outsourcing-deploy/credentials.py
```

진입점은 root로 기존 토큰을 읽고 임시 registry 설정을 사용한다. ubuntu가 토큰을 직접 읽을 필요가 없으며 deploy job의 GITHUB_TOKEN 권한도 빈 맵이다. /etc/outsourcing-deploy/backend.env와 기존 상태 폴더도 유지한다.

## 이후 확인 — 이번 작업에서는 실행하지 않음

서버 설정과 commit/push는 사용자가 별도로 진행한다. 이후 main push에서 hosted 작업 성공 및 self-hosted deploy 결과를 확인한다.

```bash
sudo systemctl is-enabled outsourcing-poll.timer
sudo systemctl is-enabled outsourcing-restore.service
sudo cat /var/lib/outsourcing-deploy/state.json
curl -f http://127.0.0.1/
curl -f http://127.0.0.1/api/health
```

poll timer는 disabled, 재부팅 복구 서비스는 enabled여야 한다. runner도 systemd 서비스로 설치되어 재부팅 후 자동 시작되는지 확인한다. 토큰 파일은 cat하지 않는다.

로컬 Windows에서는 fcntl을 mock해 오케스트레이션 테스트를 실행한다. Linux CI에서는 실제 fcntl 및 별도 Docker 프로젝트의 장애·롤백을 검증한다. 이번 작업에서는 SSH, 서버 설정, Actions 실행 및 실제 배포를 수행하지 않았다.
