import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.user_data import get_user_data_file_path

LOG_DIRECTORY_NAME = "logs"
LOG_FILENAME = "application.log"
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_APPLICATION_HANDLER_MARKER = "_texture_painter_application_handler"


def get_application_log_path(data_directory=None) -> Path:
    """Return the application log path without creating its directory."""
    return get_user_data_file_path(
        Path(LOG_DIRECTORY_NAME) / LOG_FILENAME,
        data_directory=data_directory,
    )


def _get_application_handler(root_logger):
    return next(
        (
            handler
            for handler in root_logger.handlers
            if getattr(handler, _APPLICATION_HANDLER_MARKER, False)
        ),
        None,
    )


def _mark_application_handler(handler):
    setattr(handler, _APPLICATION_HANDLER_MARKER, True)
    return handler


def configure_application_logging(data_directory=None) -> Path | None:
    """Configure one rotating application log, with a stderr fallback."""
    root_logger = logging.getLogger()
    existing_handler = _get_application_handler(root_logger)
    if existing_handler is not None:
        base_filename = getattr(existing_handler, "baseFilename", None)
        return Path(base_filename).resolve() if base_filename else None

    formatter = logging.Formatter(LOG_FORMAT)
    log_path = get_application_log_path(data_directory).resolve()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        root_logger.addHandler(_mark_application_handler(handler))
        root_logger.setLevel(logging.INFO)
        logging.captureWarnings(True)
        root_logger.exception(
            "Could not configure the persistent application log at %s",
            log_path,
        )
        return None

    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    root_logger.addHandler(_mark_application_handler(handler))
    root_logger.setLevel(logging.INFO)
    logging.captureWarnings(True)
    return log_path
