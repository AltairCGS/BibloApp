"""Pruebas de la capa de base de datos: transacciones, claves foráneas y respaldos."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import database
from app.db.database import sesion
from app.db.models import Ejemplar, Libro


def test_la_sesion_confirma_los_cambios_al_salir() -> None:
    with sesion() as db:
        db.add(Libro(titulo="Libro confirmado", autores="Prueba"))

    with sesion() as db:
        assert db.scalar(select(func.count()).select_from(Libro)) == 7


def test_la_sesion_revierte_todo_si_hay_un_error() -> None:
    with pytest.raises(RuntimeError):
        with sesion() as db:
            db.add(Libro(titulo="Libro fantasma", autores="Prueba"))
            db.flush()
            raise RuntimeError("falla simulada")

    with sesion() as db:
        escritos = db.scalar(
            select(func.count())
            .select_from(Libro)
            .where(Libro.titulo == "Libro fantasma")
        )

    assert escritos == 0


def test_las_claves_foraneas_estan_activas() -> None:
    """SQLite las ignora si no se activan en cada conexión."""
    with pytest.raises(IntegrityError):
        with sesion() as db:
            db.add(Ejemplar(libro_id=999_999, codigo_inventario="EJ-FANTASMA"))


def test_respaldar_copia_la_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path)

    destino = database.respaldar()

    assert destino is not None
    archivo = Path(destino)
    assert archivo.exists()
    assert archivo.name.startswith("biblioteca_")
    assert archivo.suffix == ".db"


def test_respaldar_sin_base_devuelve_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "no-existe.db")

    assert database.respaldar() is None
