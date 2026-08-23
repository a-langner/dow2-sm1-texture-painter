import unittest

from src.app_identity import APP_NAME, APP_VERSION, BUILD_NAME, PACKAGE_NAME


class AppIdentityTests(unittest.TestCase):
    def test_release_identity_is_centralized(self):
        self.assertEqual(APP_NAME, "Army Painter")
        self.assertEqual(APP_VERSION, "1.0")
        self.assertEqual(PACKAGE_NAME, "dow2-sm1-texture-painter")
        self.assertEqual(BUILD_NAME, "dow2-sm1-texture-painter-1.0")


if __name__ == "__main__":
    unittest.main()
