import json
import logging
import os


class EventFormatter(logging.Formatter):
    def format(self, record):
        fields = {"level": record.levelname, "logger": record.name, "event": record.getMessage()}
        for name in ("node", "call_id", "duration_ms", "error_type", "attempt", "model"):
            if hasattr(record, name):
                fields[name] = getattr(record, name)
        return json.dumps(fields)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(
        EventFormatter()
        if os.getenv("LOG_FORMAT", "json") == "json"
        else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), handlers=[handler], force=True)
    for name in ("httpx", "httpcore", "huggingface_hub"):
        logging.getLogger(name).setLevel(logging.WARNING)
