"""Simple console logger for IELTS Speaking Practice backend."""
import logging
import os
import sys

IS_RENDER = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))

_loggers = {}


def get_logger(name="ielts"):
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    class Formatter(logging.Formatter):
        def format(self, record):
            return (
                f"[{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}] "
                f"[{record.levelname:5s}] [{record.module}:{record.lineno}] "
                f"{record.getMessage()}"
            )

    formatter = Formatter()

    if IS_RENDER:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    _loggers[name] = logger
    return logger


log = get_logger()
