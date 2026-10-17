from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.utils.config import load_config

_engine: Engine | None = None
_session_factories: dict[int, sessionmaker] = {}


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    cfg = load_config(require_provider_key=False)
    db_path = Path(cfg.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path.resolve()}")

    key = cfg.db_encryption_key
    if key:
        # Spec: PRAGMA key listener when DB_ENCRYPTION_KEY is set.
        # Stock SQLite ignores this pragma; SQLCipher would consume it.
        @event.listens_for(_engine, "connect")
        def _set_pragma_key(dbapi_conn, _connection_record) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute(f"PRAGMA key = {_pragma_quote(key)}")
            cursor.close()

    return _engine


def init_db() -> None:
    from src.database.models import Base

    with get_engine().begin() as conn:
        names = inspect(conn).get_table_names()
        if "call_analyses" in names and "call_records" not in names:
            conn.exec_driver_sql("ALTER TABLE call_analyses RENAME TO call_records")
    Base.metadata.create_all(bind=get_engine())
    with get_engine().begin() as conn:
        columns = {item["name"] for item in inspect(conn).get_columns("call_records")}
        if "status" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE call_records ADD COLUMN status VARCHAR NOT NULL DEFAULT 'completed'"
            )
            conn.exec_driver_sql(
                "UPDATE call_records SET status='flagged_for_review' WHERE call_id IN (SELECT call_id FROM audit_log WHERE action='flagged_for_review')"
            )
        if "audio_filename" not in columns:
            conn.exec_driver_sql("ALTER TABLE call_records ADD COLUMN audio_filename VARCHAR")
        for operation in ("UPDATE", "DELETE"):
            conn.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS audit_log_no_{operation.lower()} "
                f"BEFORE {operation} ON audit_log BEGIN "
                "SELECT RAISE(ABORT, 'Audit log is append-only'); END"
            )


def get_session() -> Session:
    engine = get_engine()
    eid = id(engine)
    factory = _session_factories.get(eid)
    if factory is None:
        factory = sessionmaker(bind=engine)
        _session_factories[eid] = factory
    return factory()


@contextmanager
def session_scope():
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _reset_engine_state() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factories.clear()


def _pragma_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
