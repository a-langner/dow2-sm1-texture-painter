import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "texture-painter.spec"
MAKEFILE_PATH = PROJECT_ROOT / "Makefile"


class PyInstallerSpecTests(unittest.TestCase):
    def test_authoritative_spec_exists_and_has_valid_python_syntax(self):
        self.assertTrue(SPEC_PATH.is_file())
        ast.parse(SPEC_PATH.read_text(encoding="utf-8"), filename=str(SPEC_PATH))

    def test_spec_configures_entry_point_name_icon_and_package_resources(self):
        contents = SPEC_PATH.read_text(encoding="utf-8")

        self.assertIn('APP_NAME = "dow2-sm1-texture-painter-0.1"', contents)
        self.assertIn('PROJECT_ROOT / "src" / "frame_main.py"', contents)
        self.assertIn('PROJECT_ROOT / "src" / "resources" / "icon_64x64.ico"', contents)
        self.assertIn('collect_data_files("src.resources")', contents)
        self.assertIn("console=False", contents)

    def test_spec_does_not_bundle_mutable_or_test_data(self):
        contents = SPEC_PATH.read_text(encoding="utf-8")
        excluded_names = (
            "user_patterns.json",
            "settings.json",
            "application.log",
            ".pattern.json",
            ".pattern-collection.json",
            '"tests"',
        )

        for excluded_name in excluded_names:
            with self.subTest(excluded_name=excluded_name):
                self.assertNotIn(excluded_name, contents)

    def test_makefile_uses_only_the_authoritative_spec(self):
        contents = MAKEFILE_PATH.read_text(encoding="utf-8")

        self.assertIn("BUILD_SPEC := texture-painter.spec", contents)
        self.assertIn("-m PyInstaller --clean --noconfirm $(BUILD_SPEC)", contents)
        self.assertNotIn("build-bin-folder", contents)
        self.assertNotIn("build-bin-file", contents)
        self.assertNotIn("--add-data", contents)


if __name__ == "__main__":
    unittest.main()
