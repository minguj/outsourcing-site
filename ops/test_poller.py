import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("poller", Path(__file__).with_name("poller.py"))
p = importlib.util.module_from_spec(spec)
if os.name == "nt":
    # Windows can verify orchestration with a mock; Linux CI uses real flock.
    fake_fcntl = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=Mock())
    with patch.dict(sys.modules, {"fcntl": fake_fcntl}):
        spec.loader.exec_module(p)
else:
    spec.loader.exec_module(p)
COMMIT = "a" * 40


class PollerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(p, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def workflow(self, conclusion="success", event="push"):
        return {"id": 7, "run_number": 2, "run_attempt": 1, "head_sha": COMMIT,
                "head_branch": "main", "event": event, "status": "completed", "conclusion": conclusion}

    def credentials(self):
        folder = self.root / "secrets"
        folder.mkdir()
        for name in ("github-api-token", "ghcr-token"):
            (folder / name).touch()
        return folder

    def test_actions_deploys_exact_sha_without_querying_main_or_workflow(self):
        secrets = self.credentials()
        with patch.object(p, "SECRETS", secrets), patch.object(p, "main_sha") as latest, \
                patch.object(p, "verified_run") as verified, \
                patch.object(p, "secret", return_value="test-placeholder"), \
                patch.object(p, "prepare_release", return_value=self.root) as prepare, \
                patch.object(p, "deploy") as deploy:
            p.main(target_sha=COMMIT)
        latest.assert_not_called()
        verified.assert_not_called()
        self.assertEqual(prepare.call_args.args[0], COMMIT)
        deploy.assert_called_once_with(COMMIT, self.root, None)

    def test_actions_already_deployed_verifies_health_and_skips(self):
        secrets = self.credentials()
        p.atomic_json(self.root / "state.json", {"sha": COMMIT})
        with patch.object(p, "SECRETS", secrets), patch.object(p, "health") as health, \
                patch.object(p, "main_sha") as latest, patch.object(p, "deploy") as deploy:
            p.main(target_sha=COMMIT)
        health.assert_called_once_with()
        latest.assert_not_called()
        deploy.assert_not_called()

    def test_actions_rejects_invalid_sha_before_side_effects(self):
        for sha in ("main", "a" * 39, "A" * 40, COMMIT + ";id", "--help"):
            with self.subTest(sha=sha), patch.object(p, "snapshot") as snapshot:
                with self.assertRaises(p.DeployError):
                    p.main(target_sha=sha)
                snapshot.assert_not_called()

    def test_actions_lock_contention_is_failure_not_false_success(self):
        with patch.object(p.fcntl, "flock", side_effect=BlockingIOError):
            with self.assertRaises(p.DeployError):
                p.main(target_sha=COMMIT)

    def test_actions_missing_credentials_is_failure(self):
        with patch.object(p, "SECRETS", self.root / "missing"):
            with self.assertRaises(p.DeployError):
                p.main(target_sha=COMMIT)

    def test_actions_explicit_retry_bypasses_polling_failure_cooldown(self):
        secrets = self.credentials()
        p.atomic_json(self.root / "failed.json", {"sha": COMMIT, "time": p.time.time()})
        with patch.object(p, "SECRETS", secrets), patch.object(p, "secret", return_value="test-placeholder"), \
                patch.object(p, "prepare_release", return_value=self.root), patch.object(p, "deploy") as deploy:
            p.main(target_sha=COMMIT)
        deploy.assert_called_once_with(COMMIT, self.root, None)

    def test_only_full_success_is_eligible(self):
        jobs = [{"name": name, "status": "completed", "conclusion": "success"}
                for name in ("build (frontend)", "build (backend)", "smoke")]
        with patch.object(p, "api", side_effect=[{"workflow_runs": [self.workflow()]}, {"jobs": jobs}]):
            self.assertEqual(p.verified_run(COMMIT), 7)
        jobs[-1]["conclusion"] = "skipped"
        with patch.object(p, "api", side_effect=[{"workflow_runs": [self.workflow()]}, {"jobs": jobs}]):
            self.assertIsNone(p.verified_run(COMMIT))

    def test_failed_and_manual_workflows_are_rejected(self):
        for workflow in (self.workflow("failure"), self.workflow(event="workflow_dispatch")):
            with patch.object(p, "api", return_value={"workflow_runs": [workflow]}):
                self.assertIsNone(p.verified_run(COMMIT))

    def test_latest_failed_rerun_cannot_fall_back_to_old_success(self):
        older = self.workflow()
        newer = dict(self.workflow("failure"), run_attempt=2)
        with patch.object(p, "api", return_value={"workflow_runs": [older, newer]}):
            self.assertIsNone(p.verified_run(COMMIT))

    def test_already_deployed_sha_does_not_download_or_deploy(self):
        secrets = self.root / "secrets"
        secrets.mkdir()
        for name in ("github-api-token", "ghcr-token"):
            (secrets / name).touch()
        p.atomic_json(self.root / "state.json", {"sha": COMMIT})
        with patch.object(p, "SECRETS", secrets), patch.object(p, "main_sha", return_value=COMMIT), \
                patch.object(p, "prepare_release") as prepare, patch.object(p, "deploy") as deploy:
            p.main()
            prepare.assert_not_called()
            deploy.assert_not_called()

    def test_failure_restores_snapshot_and_preserves_previous_sha(self):
        backup = self.root / "backup"
        backup.mkdir()
        old = {"sha": "b" * 40, "release": "old"}
        p.atomic_json(backup / "state.json", old)
        p.atomic_json(backup / "compose.json", {"services": {}})
        with patch.object(p, "snapshot", return_value=backup), patch.object(p, "compose") as compose, \
                patch.object(p, "health", side_effect=[p.DeployError("failed"), None]):
            with self.assertRaises(p.DeployError):
                p.deploy(COMMIT, self.root, old)
            self.assertIn("--pull", compose.call_args_list[-1].args)
            self.assertEqual(p.read_json(self.root / "state.json")["sha"], old["sha"])
            self.assertFalse((self.root / "pending.json").exists())

    def test_rollback_failure_retains_recovery_record(self):
        backup = self.root / "backup"
        backup.mkdir()
        p.atomic_json(backup / "state.json", None)
        pending = {"sha": COMMIT, "backup": str(backup)}
        p.atomic_json(self.root / "pending.json", pending)
        with patch.object(p, "compose", side_effect=p.DeployError("docker failed")):
            with self.assertRaises(p.DeployError):
                p.rollback(pending)
        self.assertEqual(p.read_json(self.root / "pending.json"), pending)

    def test_interrupted_transaction_is_recovered_before_any_github_call(self):
        pending = {"sha": COMMIT, "backup": "snapshot"}
        p.atomic_json(self.root / "pending.json", pending)
        with patch.dict(p.os.environ, {"RESTORE_ONLY": "1"}), \
                patch.object(p, "rollback") as rollback, patch.object(p, "api") as api:
            p.main()
            rollback.assert_called_once_with(pending)
            api.assert_not_called()

    def test_snapshot_pins_running_image_and_caddy_config(self):
        config = {"services": {"web": {"image": "caddy:2"}}}
        container = {"Id": "container", "Image": "sha256:old-image",
                     "Config": {"Labels": {"com.docker.compose.service": "web"}}}

        def command(args, **kwargs):
            if args[1] == "ps":
                return "container\n"
            if args[1] == "inspect":
                return json.dumps([container])
            if args[1] == "cp":
                Path(args[-1]).write_text(":80 { respond ok }")
                return ""
            self.fail("Unexpected command")

        with patch.object(p, "compose", side_effect=[json.dumps(config), ""]), patch.object(p, "run", side_effect=command):
            backup = p.snapshot(None)
        saved = p.read_json(backup / "compose.json")["services"]["web"]
        self.assertEqual(saved["image"], "sha256:old-image")
        self.assertEqual(saved["volumes"][0]["source"], str(backup / "Caddyfile"))
        self.assertTrue(saved["volumes"][0]["read_only"])


if __name__ == "__main__":
    unittest.main()
