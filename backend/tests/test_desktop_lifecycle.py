from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from desktop_lifecycle import Lifecycle, validate_runtime


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lifecycle = Lifecycle(Path(self.temp.name) / "Dock", "fixture", Path(self.temp.name) / "status.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_runtime_is_not_adopted(self):
        with self.assertRaisesRegex(RuntimeError, "preserving"):
            validate_runtime("communication", {"runtime": "unrelated", "ready": True})

    def test_wrong_execution_mode_is_not_adopted(self):
        with self.assertRaises(RuntimeError):
            validate_runtime("motion", {"runtime": "motion", "ready": True, "execution_authority": True})

    def test_not_ready_is_not_success(self):
        self.assertFalse(validate_runtime("motion", {"runtime": "motion", "ready": False, "execution_authority": False}))

    def test_existing_communication_attaches_without_spawn(self):
        health = {"runtime": "communication", "ready": True, "execution_authority": False,
                  "process_instance_id": "fixture-instance", "professional_foundation": {"validated": True, "sha256": "fixture-hash"}}
        with patch("desktop_lifecycle.occupied", return_value=True), patch("desktop_lifecycle.request", return_value=health), \
             patch.object(self.lifecycle, "dock_alive", return_value=True), patch.object(self.lifecycle, "spawn") as spawn:
            self.lifecycle.runtime("communication")
        spawn.assert_not_called()
        self.assertFalse(self.lifecycle.state["services"]["communication"]["owned"])

    def test_unknown_port_owner_is_preserved(self):
        with patch("desktop_lifecycle.occupied", return_value=True), patch("desktop_lifecycle.request", return_value={"runtime": "wrong"}), \
             patch.object(self.lifecycle, "spawn") as spawn:
            with self.assertRaisesRegex(RuntimeError, "preserving port"):
                self.lifecycle.runtime("communication")
        spawn.assert_not_called()

    def test_dock_loss_aborts_startup(self):
        with patch.object(self.lifecycle, "dock_alive", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Owning Dock"):
                self.lifecycle.wait(lambda: True)

    def test_cleanup_does_not_stop_shared_model(self):
        with patch("desktop_lifecycle.request", side_effect=OSError("Unavailable")) as request:
            self.lifecycle.stop()
        self.assertEqual(self.lifecycle.children, [])
        self.assertFalse(any(call.args[0] == 16520 for call in request.call_args_list))

    def test_failed_memory_review_preserves_owned_communication(self):
        child = Mock()
        child.poll.return_value = None
        self.lifecycle.children = [("communication", child)]
        self.lifecycle.communication_instance = "fixture"
        with patch("desktop_lifecycle.request", side_effect=OSError("Persistence unavailable")), \
             patch.object(self.lifecycle, "token", return_value="fixture-only"):
            self.lifecycle.stop()
        child.terminate.assert_not_called()
        child.kill.assert_not_called()
        self.assertIn("preserved", self.lifecycle.state["cleanup_warning"])


if __name__ == "__main__":
    unittest.main()
