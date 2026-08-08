import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any


class StructuredLogger:
    def __init__(self, name: str, level: str | None = None) -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO))
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
        self.logger.propagate = False

    def info(self, message: str, **context: Any) -> None:
        self._emit("INFO", message, **context)

    def warning(self, message: str, **context: Any) -> None:
        self._emit("WARNING", message, **context)

    def error(self, message: str, **context: Any) -> None:
        self._emit("ERROR", message, **context)

    def _emit(self, level: str, message: str, **context: Any) -> None:
        payload = {"timestamp": datetime.now(UTC).isoformat(), "level": level, "message": message}
        payload.update(context)
        self.logger.info(json.dumps(payload, default=str))


def get_structured_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)
