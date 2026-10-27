"""Conexión a SQLite, sesiones y respaldos."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.db.models import Base

config.asegurar_directorios()

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    future=True,
    echo=False,
)


@event.listens_for(engine, "connect")
def _activar_claves_foraneas(dbapi_connection, _connection_record) -> None:
    """SQLite no valida las claves foráneas por defecto."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Crea todas las tablas si no existen."""
    Base.metadata.create_all(engine)


@contextmanager
def sesion() -> Iterator[Session]:
    """Sesión con commit/rollback automático."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def respaldar() -> str | None:
    """Copia la base de datos a data/respaldo con marca de tiempo."""
    if not config.DB_PATH.exists():
        return None

    config.asegurar_directorios()
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = config.BACKUP_DIR / f"biblioteca_{marca}.db"
    shutil.copy2(config.DB_PATH, destino)
    return str(destino)
