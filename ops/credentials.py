#!/usr/bin/env python3
"""Run interactively over SSH; never accepts tokens as command arguments."""
import getpass
import os
from pathlib import Path
import tempfile

if os.geteuid() != 0:
    raise SystemExit("sudo 권한으로 실행하세요.")
if not os.isatty(0):
    raise SystemExit("토큰은 대화형 SSH 터미널에서만 입력할 수 있습니다.")
root = Path("/etc/outsourcing-deploy")
root.mkdir(mode=0o700, parents=True, exist_ok=True)
root.chmod(0o700)
for name, label in (("github-api-token", "Fine-grained PAT (Actions/Contents 읽기)"),
                    ("ghcr-token", "PAT classic (read:packages)")):
    value = getpass.getpass(label + ": ").strip()
    if not value or any(c.isspace() for c in value):
        raise SystemExit("빈 토큰 또는 잘못된 입력입니다. 다시 실행하세요.")
    fd, filename = tempfile.mkstemp(dir=root)
    with os.fdopen(fd, "w") as file:
        file.write(value + "\n")
    os.chmod(filename, 0o600)
    os.replace(filename, root / name)
    del value
print("토큰을 root 전용 파일에 저장했습니다. 값은 출력하지 않습니다.")
