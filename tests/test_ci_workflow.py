import tempfile
import unittest
from pathlib import Path

import yaml

import test_support

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"


class GitHubActionsWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contents = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.contents)

    def test_workflow_is_valid_yaml_and_runs_for_pushes_and_pull_requests(self):
        self.assertIsInstance(self.workflow, dict)
        self.assertEqual(self.workflow["name"], "Tests")
        self.assertIn("push", self.workflow["on"])
        self.assertIn("pull_request", self.workflow["on"])

    def test_linux_job_uses_supported_python_and_official_actions(self):
        job = self.workflow["jobs"]["linux-tests"]
        self.assertEqual(job["runs-on"], "ubuntu-latest")
        self.assertEqual(job["timeout-minutes"], 10)
        steps = job["steps"]
        self.assertEqual(steps[0]["uses"], "actions/checkout@v4")
        self.assertEqual(steps[1]["uses"], "actions/setup-python@v5")
        self.assertEqual(steps[1]["with"]["python-version"], "3.10")
        self.assertEqual(steps[1]["with"]["cache"], "pip")

    def test_windows_job_uses_same_python_and_official_actions(self):
        job = self.workflow["jobs"]["windows-tests"]
        self.assertEqual(job["runs-on"], "windows-latest")
        self.assertEqual(job["timeout-minutes"], 15)
        steps = job["steps"]
        self.assertEqual(steps[0]["uses"], "actions/checkout@v4")
        self.assertEqual(steps[1]["uses"], "actions/setup-python@v5")
        self.assertEqual(steps[1]["with"]["python-version"], "3.10")
        self.assertEqual(steps[1]["with"]["cache"], "pip")

    def test_installation_matches_local_development_groups(self):
        for job_name in ("linux-tests", "windows-tests"):
            with self.subTest(job=job_name):
                commands = [
                    step["run"]
                    for step in self.workflow["jobs"][job_name]["steps"]
                    if "run" in step
                ]
                self.assertIn("python -m pip install --upgrade pip", commands)
                self.assertIn("python -m pip install -r requirements.txt", commands)
                self.assertIn("python -m pip install -r requirements-dev.txt", commands)
                self.assertIn("python -m pip install -e .", commands)

    def test_complete_unittest_command_propagates_failures(self):
        for job_name in ("linux-tests", "windows-tests"):
            with self.subTest(job=job_name):
                job = self.workflow["jobs"][job_name]
                test_steps = [
                    step
                    for step in job["steps"]
                    if step.get("name") == "Run complete test suite"
                ]
                self.assertEqual(len(test_steps), 1)
                self.assertEqual(
                    test_steps[0]["run"], "python -m unittest discover -s tests"
                )
                self.assertNotIn("continue-on-error", test_steps[0])
        self.assertNotIn("|| true", self.contents)

    def test_windows_job_builds_and_verifies_the_authoritative_bundle(self):
        steps = self.workflow["jobs"]["windows-tests"]["steps"]
        build_step = next(
            step for step in steps if step.get("name") == "Build Windows application"
        )
        verify_step = next(
            step
            for step in steps
            if step.get("name") == "Verify Windows application bundle"
        )

        self.assertEqual(
            build_step["run"],
            "python -m PyInstaller --clean --noconfirm texture-painter.spec",
        )
        self.assertEqual(verify_step["shell"], "pwsh")
        for expected_path_part in (
            "dow2-texture-painter-0.1.exe",
            "_internal\\src\\resources",
            "army_pattern.json",
            "default_pattern.ini",
            "icon_64x64.ico",
            "icon_64x64.png",
        ):
            self.assertIn(expected_path_part, verify_step["run"])

        self.assertNotIn("continue-on-error", build_step)
        self.assertNotIn("continue-on-error", verify_step)

    def test_tests_redirect_user_data_to_a_temporary_directory(self):
        temporary_root = Path(tempfile.gettempdir()).resolve()
        redirected_path = test_support.TEST_USER_DATA_DIRECTORY.resolve()

        self.assertTrue(redirected_path.is_relative_to(temporary_root))
        self.assertTrue(redirected_path.name.startswith("texture-painter-tests-"))

    def test_workflow_does_not_publish_or_bundle_user_data(self):
        self.assertNotIn("upload-artifact", self.contents)
        self.assertNotIn("secrets.", self.contents)
        for user_data_name in (
            "user_patterns.json",
            "settings.json",
            "application.log",
        ):
            self.assertNotIn(user_data_name, self.contents)


if __name__ == "__main__":
    unittest.main()
