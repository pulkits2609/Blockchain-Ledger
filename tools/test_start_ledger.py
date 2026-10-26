"""Check launcher decisions without changing a user's database or configuration."""

import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import start_ledger as launcher


class LauncherTests(unittest.TestCase):
    def test_existing_build_is_always_refreshed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            python.parent.mkdir(parents=True); python.touch()
            (root / "frontend/dist").mkdir(parents=True)
            (root / "frontend/dist/index.html").write_text("old build")
            result = subprocess.CompletedProcess([], 0, stdout="v22.21.1\n")
            with patch.object(launcher.shutil, "which", side_effect=lambda name: "/tools/" + name), \
                 patch.object(launcher.subprocess, "run", return_value=result), patch.object(launcher, "run") as run:
                self.assertEqual(launcher.prepare(root), python)
                self.assertEqual(run.call_count, 3)
                self.assertEqual(run.call_args_list[1].args[0][-1], "ci")
                self.assertEqual(run.call_args_list[2].args[0][-2:], ["run", "build"])

    def test_existing_configuration_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"; path.write_text("existing configuration")
            with patch("builtins.input", side_effect=AssertionError("Unexpected prompt")):
                launcher.create_configuration(Path(folder))
            self.assertEqual(path.read_text(), "existing configuration")

    def test_configuration_encodes_password_and_stays_local(self):
        with tempfile.TemporaryDirectory() as folder:
            answers = ["1", "", "", "", "", "1", ""]
            with patch("builtins.input", side_effect=answers), patch.object(launcher.getpass, "getpass", return_value="p@ss:# word"):
                launcher.create_configuration(Path(folder))
            contents = (Path(folder) / ".env").read_text()
            self.assertIn("p%40ss%3A%23%20word", contents)
            self.assertIn("LEDGER_BIND=127.0.0.1", contents)
            self.assertIn("LEDGER_DEV_MODE=true", contents)
            self.assertNotIn("LEDGER_ADMIN_PASSWORD", contents)

    def test_exit_does_not_start_server(self):
        with patch("builtins.input", return_value="0"), patch.object(launcher, "run") as run:
            launcher.menu(Path("python"))
            run.assert_not_called()

    def test_admin_password_is_only_passed_in_child_environment(self):
        with patch("builtins.input", side_effect=["2", "college_admin", "0"]), \
             patch.object(launcher.getpass, "getpass", return_value="long-admin-password"), patch.object(launcher, "run") as run:
            launcher.menu(Path("python"))
            self.assertEqual(run.call_args.args[0][-1], "--init-admin")
            self.assertNotIn("long-admin-password", str(run.call_args.args))
            self.assertEqual(run.call_args.kwargs["env"]["LEDGER_ADMIN_PASSWORD"], "long-admin-password")

    def test_custom_flags_are_not_a_shell_command(self):
        with patch("builtins.input", side_effect=["5", "--port 8443"]), patch.object(launcher, "run") as run:
            launcher.menu(Path("python"))
            self.assertEqual(run.call_args.args[0][-2:], ["--port", "8443"])

    def test_build_only_needs_no_database_configuration(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launcher, "ROOT", Path(folder)), \
             patch.object(launcher, "prepare", return_value=Path("python")), \
             patch.object(launcher.sys, "argv", ["start_ledger.py", "--build-only"]), patch.object(launcher, "run") as run:
            self.assertEqual(launcher.main(), 0)
            run.assert_not_called()

    def test_automation_without_configuration_fails(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launcher, "ROOT", Path(folder)), \
             patch.object(launcher, "prepare", return_value=Path("python")), \
             patch.object(launcher.sys, "argv", ["start_ledger.py", "--check-db"]), \
             patch.object(launcher.sys, "stdin", io.StringIO()), patch.object(launcher, "run") as run:
            self.assertEqual(launcher.main(), 1)
            run.assert_not_called()


if __name__ == "__main__":
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main()
