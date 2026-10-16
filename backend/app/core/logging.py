import json
import logging
import sys
from datetime import date, datetime
from typing import Any

logger = logging.getLogger("erp")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=_json_default, ensure_ascii=False)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, (set, tuple)):
        return list(obj)
    return str(obj)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Quieten noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine.Engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
