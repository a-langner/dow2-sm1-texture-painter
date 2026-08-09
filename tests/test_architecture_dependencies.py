"""Static regression checks for the application's dependency boundaries."""

import ast
from pathlib import Path
import unittest

import test_support  # noqa: F401 - installs the user-data path redirect

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"

# These modules implement the GUI boundary and may import tkinter directly.
TKINTER_ALLOWED_MODULES = {
    "dialog_gateway.py",
    "frame_main.py",
    "widget.py",
}
SERVICE_MODULES = {
    "batch_processing_service.py",
    "file_selection_service.py",
    "texture_loading_service.py",
}
CONTROLLER_MODULES = {"pattern_controller.py", "preview_controller.py"}
PATTERN_PERSISTENCE_MODULES = {
    "color_pattern_handler.py",
    "pattern_exchange.py",
    "settings_handler.py",
    "user_data.py",
}
IMAGE_PROCESSING_MODULES = {
    "dow1_converter.py",
    "image_process.py",
    "render_settings.py",
    "texture_naming.py",
    "texture_renderer.py",
    "texture_set.py",
}
GUI_MODULES = {
    "src.dialog_gateway",
    "src.frame_main",
    "src.widget",
    "tkinter",
}


def imports_for(module_name):
    tree = ast.parse((SRC_DIRECTORY / module_name).read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def imports_module(imports, forbidden):
    return any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for imported in imports
    )


class ArchitectureDependencyTests(unittest.TestCase):
    def assert_no_forbidden_imports(self, module_name, forbidden_modules):
        imports = imports_for(module_name)
        violations = sorted(
            forbidden
            for forbidden in forbidden_modules
            if imports_module(imports, forbidden)
        )
        self.assertEqual(
            violations,
            [],
            f"src/{module_name} must not import: {', '.join(violations)}",
        )

    def test_only_documented_gui_boundary_modules_import_tkinter(self):
        for source_path in sorted(SRC_DIRECTORY.glob("*.py")):
            if source_path.name in TKINTER_ALLOWED_MODULES:
                continue
            with self.subTest(module=source_path.name):
                self.assert_no_forbidden_imports(source_path.name, {"tkinter"})

    def test_services_and_controllers_do_not_import_gui_modules(self):
        for module_name in sorted(SERVICE_MODULES | CONTROLLER_MODULES):
            with self.subTest(module=module_name):
                self.assert_no_forbidden_imports(module_name, GUI_MODULES)

    def test_widget_does_not_import_composition_root(self):
        self.assert_no_forbidden_imports("widget.py", {"src.frame_main"})

    def test_all_lower_level_modules_avoid_frame_main(self):
        for source_path in sorted(SRC_DIRECTORY.glob("*.py")):
            if source_path.name == "frame_main.py":
                continue
            with self.subTest(module=source_path.name):
                self.assert_no_forbidden_imports(source_path.name, {"src.frame_main"})

    def test_pattern_persistence_does_not_import_gui_modules(self):
        for module_name in sorted(PATTERN_PERSISTENCE_MODULES):
            with self.subTest(module=module_name):
                self.assert_no_forbidden_imports(module_name, GUI_MODULES)

    def test_image_processing_does_not_import_gui_modules(self):
        for module_name in sorted(IMAGE_PROCESSING_MODULES):
            with self.subTest(module=module_name):
                self.assert_no_forbidden_imports(module_name, GUI_MODULES)


if __name__ == "__main__":
    unittest.main()
