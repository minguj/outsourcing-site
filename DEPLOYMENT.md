# Docker 배포

## 배포 흐름

main PR은 Linux amd64 이미지 빌드를 검증한다. main push 또는 main에서 수동 실행하면 Actions가 GHCR에 두 이미지를 게시한다. 태그는 전체 커밋 SHA다. frontend/backend 빌드와 smoke 작업이 모두 성공한 SHA만 배포한다. smoke 작업은 게시된 이미지를 받아 Caddy 및 두 경로를 실제 실행 검증한다.

- `ghcr.io/minguj/outsourcing-site-frontend:<SHA>`
- `ghcr.io/minguj/outsourcing-site-backend:<SHA>`

EC2에서는 빌드하지 않는다. Caddy만 호스트 80 포트를 열며 `/api`와 `/api/*`는 경로를 보존해 backend:8000으로, 나머지는 frontend:3000으로 전달한다. Next.js 기존 설정에 standalone 출력만 추가했다. RAM 제한은 frontend 512MiB, backend 256MiB, Caddy 96MiB다. OS 여유가 적으므로 docker stats로 관찰한다. 로그는 서비스별 약 30MB로 순환한다.

현재 구현은 GitHub 호스팅 러너에서 이미지 게시와 smoke까지 수행한다. EC2 자동 배포는 아래 AWS 제약과 대안을 확인한 후 별도 연결해야 한다. AWS 액세스 키나 SSH 개인키를 GitHub에 등록하지 않는다.

## AWS (new) 무료 플랜과 자동 배포

AWS 공식 Free Tier 프로젝트 SCP에는 `DenyIAMRestrictedActions`의 `iam:*Provider*` 거부가 있다. GitHub OIDC 공급자 생성인 `iam:CreateOpenIDConnectProvider`도 거부 대상이므로 **새 공급자를 만들어 OIDC + SSM을 설정하는 방식은 현재 제약 아래 사용할 수 없다.** SSM 자체는 지원 서비스이고 EC2 Run Command는 추가 요금이 없지만, 이것이 OIDC 공급자 생성 가능성을 의미하지 않는다. 실제 계정의 기존 공급자/역할 유무는 별도 확인이 필요하다. 고급 기능 활성화나 유료 전환은 하지 않는다.

근거: [Free Tier 프로젝트 SCP](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html), [지원 서비스](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html), [EC2 Run Command 요금](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html).

가능한 대안은 다음과 같다. 아직 서버에 설치하거나 활성화하지 않았다.

| 대안 | 필요한 설정 | 특성 |
| --- | --- | --- |
| EC2 systemd timer가 성공한 Actions 실행을 조회하고 SHA 이미지 pull | EC2 전용 GitHub 읽기 토큰(Actions/Contents), private GHCR read:packages 인증, timer/배포 스크립트 | 권장. runner 상주 없이 수분 이내 자동 반영. main push 실행 전체 성공 및 최신 main SHA 일치 확인 후 배포해야 함 |
| EC2 배포 전용 self-hosted Actions runner | private 저장소 runner 등록, ubuntu systemd 서비스, smoke에 의존하는 main 전용 deploy job | GitHub 작업 결과에 EC2 배포 성공까지 표시 가능. 1GB RAM에서 runner 메모리 확인 필요. PR/빌드는 호스팅 러너에서만 실행 |

두 대안 모두 EC2에서 GitHub/GHCR로 나가는 HTTPS를 사용하므로 SSH 22번 전체 공개나 추가 AWS 서비스가 필요 없다. 기존 EC2/EBS/네트워크 사용은 계속되며 무료 플랜 잔여 크레딧과 GitHub Actions/Packages 한도는 확인한다. 신규 유료 네트워크 리소스나 플랜 업그레이드는 구성하지 않는다.

## GitHub 설정

1. 변경 사항을 검토해 minguj/outsourcing-site의 main에 push한다. 기본 브랜치가 다르면 workflow의 main 조건도 맞춘다.
2. Settings → Actions → General에서 Actions 및 사용한 Docker Actions 실행이 허용되는지 확인한다.
3. Actions의 Container images에서 두 이미지 빌드와 smoke 작업 모두 성공했는지 확인하고 전체 40자리 SHA를 복사한다.
4. GHCR 패키지 공개 여부와 저장소 접근 권한을 확인한다. 기존 동명 패키지가 있다면 이 저장소에 Actions 쓰기 권한을 부여한다.

**GitHub Secrets 추가는 필요 없다.** 내장 GITHUB_TOKEN과 workflow의 packages: write로 게시한다. Private GHCR 이미지를 EC2에서 받으려면 GitHub PAT (classic)의 read:packages 권한과 계정의 패키지 읽기 권한이 필요하다. 조직 SSO가 있다면 승인도 필요하다. 이 PAT는 EC2 로그인에만 사용한다. 공개 이미지는 로그인 없이 pull 가능하다.

## 기존 서버 확인 및 파일 전송

서버 접속이나 파일 변경은 아직 실행하지 않았다. 아래 `<SSH_KEY>` 등은 실제 값으로 바꾼다. PC PowerShell에서 접속한다.

```powershell
ssh -i <SSH_KEY> ubuntu@16.176.219.121
```

EC2에서 기존 설정을 확인하고 백업한다.

```bash
cd ~/outsourcing-site
docker compose ls
docker compose config
docker compose ps
docker compose version
cp -p compose.yaml compose.yaml.before-apps
test ! -f Caddyfile || cp -p Caddyfile Caddyfile.before-apps
```

더 확실한 백업은 새 파일 전송 전에 PC PowerShell에서 아래를 실행한다. 실제 실행 중인 Caddyfile과 볼륨 마운트 정보도 권한 제한된 서버 백업 폴더에 저장한다. 이 명령이 성공하기 전에는 새 Compose/Caddyfile을 전송하지 않는다.

```powershell
Get-Content -Raw scripts/backup-caddy.sh | ssh -i <SSH_KEY> ubuntu@16.176.219.121 'bash -s -- /home/ubuntu/outsourcing-site'
```

기존 Caddyfile 경로가 다르면 실제 마운트된 파일을 백업한다. 새 compose.yaml과 기존 프로젝트명, Caddy 서비스명, 볼륨, 마운트, 포트를 비교한다. 새 파일은 caddy 서비스와 caddy_data/caddy_config 볼륨을 사용한다. 기존 볼륨 이름이 다르면 새 파일에 기존 이름을 반영한다. 별도 Compose 프로젝트가 80 포트를 점유 중이면 먼저 구성을 맞춘다. 두 Caddy를 동시에 실행하지 않으며 `down -v`를 실행하지 않는다.

검토 후 PC의 프로젝트 루트에서 운영 파일만 전송한다. 서버에 Git 체크아웃은 필요 없다.

```powershell
ssh -i <SSH_KEY> ubuntu@16.176.219.121 "mkdir -p ~/outsourcing-site/scripts"
scp -i <SSH_KEY> compose.yaml Caddyfile .env.example backend.env.example ubuntu@16.176.219.121:~/outsourcing-site/
scp -i <SSH_KEY> scripts/deploy.sh ubuntu@16.176.219.121:~/outsourcing-site/scripts/
```

## EC2 최초 설정

ubuntu 사용자가 sudo 없이 Docker를 실행할 수 있어야 한다. 그룹 권한 변경 시 재로그인한다. Compose v2의 up --wait 및 --wait-timeout 지원을 확인한다. curl, python3, flock(util-linux)이 필요하다.

```bash
cd ~/outsourcing-site
umask 077
cp backend.env.example backend.env
chmod 600 backend.env
```

현재 backend.env에는 비밀값이 필요 없다. 추후 비밀값은 이 파일에만 기록한다. Private GHCR일 때만 다음을 실행한다.

```bash
read -rsp 'GHCR read:packages PAT: ' GHCR_TOKEN; echo
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u minguj --password-stdin
unset GHCR_TOKEN
chmod 700 ~/.docker
chmod 600 ~/.docker/config.json
```

credential helper가 없으면 토큰은 Docker 설정에 인코딩되어 저장되므로 서버 계정 접근을 제한한다. 비밀값은 이미지 빌드 인자나 NEXT_PUBLIC_*에 넣지 않는다. 브라우저 API 요청은 상대 경로 `/api/...`를 사용한다. 서버 컴포넌트에서 내부 API 호출이 필요해지면 서버 전용 주소를 별도로 설정한다.

보안 그룹은 TCP 80을 서비스 대상에 열고 TCP 22는 본인 IP만 유지한다. 3000/8000은 열지 않는다. 현재는 도메인 없는 HTTP이므로 443 및 인증서 설정은 하지 않는다. IP 유지가 필요하면 Elastic IP 연결 여부를 확인한다.

## 배포 및 롤백

```bash
cd ~/outsourcing-site
bash scripts/deploy.sh <SUCCESSFUL_FULL_COMMIT_SHA>
docker compose ps
curl -f http://127.0.0.1/
curl -f http://127.0.0.1/api/health
```

외부에서도 http://16.176.219.121/ 및 http://16.176.219.121/api/health 를 확인한다. health 응답은 `{"status":"ok"}`여야 한다.

스크립트는 이미지 pull, 임시 컨테이너에서 Caddy 설정 검증, 컨테이너 health 대기, Caddy 강제 reload, 두 프록시 경로 확인 후 `.env`에 성공 SHA를 기록한다. 두 앱 이미지 pull이 끝나기 전에는 컨테이너를 변경하지 않는다. 동시 배포는 flock으로 막는다.

교체 중 짧은 중단이 발생할 수 있다. 자동 롤백은 없으며 실행 단계 실패 시 일부 컨테이너가 새 버전일 수 있다. `.env`는 마지막 성공 SHA이므로 실제 실행 이미지는 docker compose ps로 확인한다. 실패하면 로그를 확인하고 직전 성공 SHA로 다시 배포한다. 운영 파일 변경도 되돌려야 하면 백업한 Compose/Caddyfile을 먼저 복원한다.

```bash
docker compose logs --tail=100 caddy frontend backend
docker stats --no-stream
df -h
bash scripts/deploy.sh <PREVIOUS_SUCCESSFUL_FULL_COMMIT_SHA>
```

최초 배포 실패로 .env가 없다면 진단 명령 앞에 `IMAGE_TAG=<시도한_SHA>`를 지정한다. 스크립트는 롤백용 이미지를 자동 삭제하지 않는다. 30GB 디스크에서 이미지가 쌓이면 현재 버전과 롤백할 SHA를 확인하고 불필요한 이미지만 선택적으로 삭제한다.

## 검증 범위

로컬에 Docker가 없으면 Linux 이미지 빌드, Compose 실행, Caddy 프록시 통합 검증을 수행할 수 없다. Actions에서 이미지 빌드를, EC2 배포 스크립트에서 컨테이너와 프록시 health를 검증한다. 현재 프런트엔드는 Google Fonts 다운로드를 위해 빌드 시 외부 연결이 필요하다.

참고: [GHCR 인증](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [Actions 이미지 게시](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [Caddy 경로 처리](https://caddyserver.com/docs/caddyfile/directives/handle), [Compose health 대기](https://docs.docker.com/reference/cli/docker/compose/up/).
