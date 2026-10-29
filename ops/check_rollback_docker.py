#!/usr/bin/env python3
"""Exercise real Docker rollback on isolated project and localhost port 18080."""
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request

import poller as p


def main():
    os.umask(0o077)
    p.PROJECT = "outsourcing-rollback-check"
    with tempfile.TemporaryDirectory(prefix="rollback-check-", dir="/var/lib/outsourcing-deploy") as tmp:
        folder = Path(tmp)
        p.ROOT = folder
        old = folder / "old"
        old.mkdir()
        (old / "Caddyfile").write_text(':80 {\n respond "previous-release"\n}\n')
        image = json.loads(p.run(["docker", "image", "inspect", "caddy:2"]))[0]["Id"]
        config = {"services": {"caddy": {"image": image, "ports": ["127.0.0.1:18080:80"],
                  "volumes": [{"type": "bind", "source": str(old / "Caddyfile"),
                               "target": "/etc/caddy/Caddyfile", "read_only": True}]}}}
        p.atomic_json(old / "runtime.json", config)
        p.LEGACY = old / "runtime.json"

        def check_health(**_kwargs):
            for attempt in range(10):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:18080", timeout=5) as response:
                        if response.read().decode() == "previous-release":
                            return
                except OSError:
                    pass
                if attempt < 9:
                    time.sleep(1)
            raise p.DeployError("Previous Caddy config was not restored")

        p.health = check_health
        try:
            p.compose(old / "runtime.json", "up", "-d", "--wait")
            check_health()
            bad = folder / "bad"
            bad.mkdir()
            (bad / "Caddyfile").write_text(':80 {\n respond "bad-release"\n}\n')
            config["services"]["caddy"]["volumes"][0]["source"] = str(bad / "Caddyfile")
            config["services"]["caddy"]["healthcheck"] = {
                "test": ["CMD", "false"], "interval": "1s", "timeout": "1s", "retries": 1}
            p.atomic_json(bad / "runtime.json", config)
            try:
                p.deploy("f" * 40, bad, None)
            except p.DeployError:
                check_health()
                assert not (folder / "pending.json").exists()
                assert not (folder / "state.json").exists()
                print("PASS: unhealthy release rolled back to previous Docker image and Caddy configuration")
            else:
                raise RuntimeError("Intentionally unhealthy deployment unexpectedly succeeded")
        finally:
            p.compose(old / "runtime.json", "down", "--remove-orphans")


if __name__ == "__main__":
    main()
