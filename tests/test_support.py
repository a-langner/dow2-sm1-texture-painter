import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

TEST_USER_DATA_DIRECTORY = (
    Path(tempfile.gettempdir()) / f"texture-painter-tests-{uuid4().hex}"
)

# Redirect platformdirs before any application module is imported. The path is
# intentionally not created; individual persistence tests use their own
# TemporaryDirectory instances.
USER_DATA_PATH_PATCHER = patch(
    "platformdirs.user_data_path", return_value=TEST_USER_DATA_DIRECTORY
)
USER_DATA_PATH_PATCHER.start()
