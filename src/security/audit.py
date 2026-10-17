import json

from src.database.connection import session_scope
from src.database.models import AuditLogEntry


class AuditLogger:
    def log(
        self,
        call_id: str,
        action: str,
        user: str,
        details: dict | None = None,
        stage: str | None = None,
    ) -> None:
        if stage is not None:
            details = {"stage": stage, **(details or {})}

        entry = AuditLogEntry(
            call_id=call_id,
            action=action,
            user=user,
            details=json.dumps(details) if details is not None else None,
        )

        with session_scope() as session:
            session.add(entry)
