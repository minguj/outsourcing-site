#!/usr/bin/env python3
"""Root-owned EC2 pull deployment agent; standard library only."""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = "minguj/outsourcing-site"
PROJECT = "outsourcing-site"
ROOT = Path("/var/lib/outsourcing-deploy")
SECRETS = Path("/etc/outsourcing-deploy")
LEGACY = Path("/home/ubuntu/outsourcing-site/compose.yaml")
SHA = re.compile(r"[0-9a-f]{40}")


class DeployError(Exception):
    pass


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def secret(name):
    path = SECRETS / name
    if path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
        raise DeployError("Credential permissions must be root-owned 600")
    value = path.read_text().strip()
    if not value or any(c.isspace() for c in value):
        raise DeployError("Credential is empty or malformed")
    return value


def api(path):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        headers={"Authorization": "Bearer " + secret("github-api-token"),
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise DeployError(f"GitHub API HTTP {error.code}; check token permissions/expiry") from None
    except (OSError, ValueError):
        raise DeployError("GitHub API unavailable or invalid response") from None


def main_sha():
    value = api("git/ref/heads/main")["object"]["sha"]
    if not SHA.fullmatch(value):
        raise DeployError("Invalid main SHA")
    return value


def verified_run(sha):
    query = urllib.parse.urlencode({"branch": "main", "event": "push", "head_sha": sha,
                                    "per_page": 20})
    runs = api("actions/workflows/images.yml/runs?" + query)["workflow_runs"]
    # A newer failed/in-progress rerun must not be hidden by an older success.
    if not runs:
        return None
    run = max(runs, key=lambda item: (item["run_number"], item["run_attempt"]))
    if (run["head_sha"] != sha or run["head_branch"] != "main" or run["event"] != "push"
            or run["status"] != "completed" or run["conclusion"] != "success"):
        return None
    jobs = []
    page = 1
    while True:
        batch = api(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100&page={page}")["jobs"]
        jobs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    required = {"build (frontend)", "build (backend)", "smoke"}
    successful = {job["name"] for job in jobs
                  if job["status"] == "completed" and job["conclusion"] == "success"}
    return run["id"] if required <= successful else None


def run(command, env=None, timeout=300):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise DeployError("Deployment command unavailable or timed out") from None
    if result.returncode:
        # Never forward command output: Compose/config can include application secrets.
        raise DeployError("Deployment command failed: " + " ".join(command[:3]))
    return result.stdout


def compose(file, *args, docker_config=None, sha=None):
    env = os.environ.copy()
    if sha:
        env["IMAGE_TAG"] = sha
    command = ["docker"]
    if docker_config:
        command += ["--config", str(docker_config)]
    command += ["compose", "--project-name", PROJECT, "-f", str(file), *args]
    return run(command, env=env)


def health(api_required=True, attempts=15):
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen("http://127.0.0.1/", timeout=5) as response:
                if response.status != 200:
                    raise ValueError()
            if api_required:
                with urllib.request.urlopen("http://127.0.0.1/api/health", timeout=5) as response:
                    if response.status != 200 or json.load(response) != {"status": "ok"}:
                        raise ValueError()
            return
        except (OSError, ValueError):
            if attempt + 1 < attempts:
                time.sleep(3)
    raise DeployError("HTTP health verification failed")


def prepare_release(sha, docker_config):
    release = ROOT / "releases" / sha
    release.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("compose.yaml", "Caddyfile"):
        data = api(f"contents/{name}?ref={sha}")
        if data.get("encoding") != "base64":
            raise DeployError("Unsupported deployment file encoding")
        (release / name).write_bytes(base64.b64decode(data["content"]))
    env_file = release / "backend.env"
    if not env_file.exists():
        env_file.symlink_to(SECRETS / "backend.env")
    config = json.loads(compose(release / "compose.yaml", "config", "--format", "json", sha=sha))
    if set(config["services"]) != {"caddy", "frontend", "backend"}:
        raise DeployError("Unexpected Compose service set")
    compose(release / "compose.yaml", "pull", docker_config=docker_config, sha=sha)
    # Pin ALL pulled images (including Caddy) to local image IDs. Rollback never pulls.
    for service in config["services"].values():
        service["image"] = json.loads(run(["docker", "image", "inspect", service["image"]]))[0]["Id"]
    atomic_json(release / "runtime.json", config)
    compose(release / "runtime.json", "run", "--rm", "--no-deps", "caddy", "caddy",
            "validate", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile")
    return release


def snapshot(state):
    folder = ROOT / "backups" / f"{time.time_ns()}"
    folder.mkdir(parents=True, mode=0o700)
    source = Path(state["release"]) / "runtime.json" if state else LEGACY
    config = json.loads(compose(source, "config", "--format", "json"))
    ids = run(["docker", "ps", "--filter", f"label=com.docker.compose.project={PROJECT}", "-q"]).split()
    if not ids:
        raise DeployError("No running project to back up; refuse first deployment")
    containers = json.loads(run(["docker", "inspect", *ids]))
    seen = set()
    caddy_found = False
    for container in containers:
        name = container["Config"]["Labels"]["com.docker.compose.service"]
        if name not in config["services"]:
            raise DeployError("Running services differ from backup Compose")
        seen.add(name)
        service = config["services"][name]
        service["image"] = container["Image"]
        if name in ("web", "caddy"):
            caddy_found = True
            saved = folder / "Caddyfile"
            run(["docker", "cp", f"{container['Id']}:/etc/caddy/Caddyfile", str(saved)])
            saved.chmod(0o600)
            volumes = [v for v in service.get("volumes", []) if v["target"] != "/etc/caddy/Caddyfile"]
            volumes.append({"type": "bind", "source": str(saved),
                            "target": "/etc/caddy/Caddyfile", "read_only": True})
            service["volumes"] = volumes
    if not caddy_found or seen != set(config["services"]):
        raise DeployError("Incomplete running project backup")
    atomic_json(folder / "compose.json", config)
    atomic_json(folder / "state.json", state)
    compose(folder / "compose.json", "config", "--quiet")
    return folder


def rollback(pending):
    folder = Path(pending["backup"])
    old = read_json(folder / "state.json")
    compose(folder / "compose.json", "up", "-d", "--remove-orphans", "--pull", "never",
            "--wait", "--wait-timeout", "180")
    # Previous full deployment requires both paths; initial Caddy only requires /.
    health(api_required=bool(old))
    if old:
        # Reboot must use the snapshot config that was actually restored.
        restored = dict(old, release=str(folder))
        atomic_json(folder / "runtime.json", read_json(folder / "compose.json"))
        atomic_json(ROOT / "state.json", restored)
    else:
        (ROOT / "state.json").unlink(missing_ok=True)
    (ROOT / "pending.json").unlink(missing_ok=True)
    print("Rollback restored previous images and configuration", flush=True)


def deploy(sha, release, state):
    backup = snapshot(state)
    pending = {"sha": sha, "backup": str(backup)}
    atomic_json(ROOT / "pending.json", pending)
    try:
        compose(release / "runtime.json", "up", "-d", "--remove-orphans", "--pull", "never",
                "--wait", "--wait-timeout", "180")
        compose(release / "runtime.json", "exec", "-T", "caddy", "caddy", "reload",
                "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile", "--force")
        health()
        atomic_json(ROOT / "state.json", {"sha": sha, "release": str(release),
                                          "backup": str(backup), "time": int(time.time())})
        (ROOT / "pending.json").unlink()
        (ROOT / "failed.json").unlink(missing_ok=True)
        print(f"Deployed {sha}; / and /api/health verified", flush=True)
    except Exception:
        atomic_json(ROOT / "failed.json", {"sha": sha, "time": int(time.time())})
        print("Deployment failed; restoring snapshot", flush=True)
        rollback(pending)
        raise


def main(target_sha=None):
    # The Actions entry point must never select a different main commit.
    if target_sha is not None and not SHA.fullmatch(target_sha):
        raise DeployError("Expected one full lowercase 40-character commit SHA")
    os.umask(0o077)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (ROOT / "deploy.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if target_sha is not None:
                raise DeployError("Another deployment is running; retry this job after it finishes") from None
            print("Another deployment is running; skipped", flush=True)
            return
        pending = read_json(ROOT / "pending.json")
        if pending:
            print("Recovering interrupted deployment", flush=True)
            rollback(pending)
        # Restore the selected config after reboot; Docker restart policies start containers.
        if target_sha is None and os.environ.get("RESTORE_ONLY") == "1":
            state = read_json(ROOT / "state.json")
            if state:
                compose(Path(state["release"]) / "runtime.json", "up", "-d", "--pull", "never",
                        "--wait", "--wait-timeout", "180")
                health()
            return
        if not (SECRETS / "github-api-token").exists() or not (SECRETS / "ghcr-token").exists():
            if target_sha is not None:
                raise DeployError("Root deployment credentials are not configured")
            print("Credentials not configured; no deployment attempted", flush=True)
            return
        sha = target_sha if target_sha is not None else main_sha()
        state = read_json(ROOT / "state.json")
        if state and state["sha"] == sha:
            if target_sha is not None:
                health()
            print(f"Already deployed {sha}; skipped", flush=True)
            return
        failed = read_json(ROOT / "failed.json", {})
        if target_sha is None and failed.get("sha") == sha and time.time() - failed["time"] < 1800:
            print("Failed release cooldown (30 minutes); skipped", flush=True)
            return
        # Actions supplies eligibility through successful prerequisite jobs. Its
        # workflow is still in progress here, so do not require whole-run success.
        if target_sha is None and not verified_run(sha):
            print("Latest main has no fully successful build/smoke push run; skipped", flush=True)
            return
        with tempfile.TemporaryDirectory(prefix="registry-", dir=ROOT) as temporary:
            auth = base64.b64encode(("minguj:" + secret("ghcr-token")).encode()).decode()
            atomic_json(Path(temporary) / "config.json", {"auths": {"ghcr.io": {"auth": auth}}})
            release = prepare_release(sha, temporary)
        # Do not roll out a stale main when a push arrived during image downloads.
        if target_sha is None and (main_sha() != sha or not verified_run(sha)):
            print("Main or workflow state changed while preparing; skipped", flush=True)
            return
        deploy(sha, release, state)


def interrupted(_number, _frame):
    raise DeployError("Deployment interrupted")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--sha", help="Deploy only this Actions commit, without polling main")
        arguments = parser.parse_args()
        main(target_sha=arguments.sha)
    except Exception as error:
        # Unexpected exceptions may embed credentials; expose only vetted messages.
        print(str(error) if isinstance(error, DeployError) else "Deployment agent error; inspect configuration", flush=True)
        raise SystemExit(1)
