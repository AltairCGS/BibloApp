"""Configuración común de las pruebas automatizadas.

Cada corrida trabaja sobre una base SQLite temporal que se crea en la
carpeta de temporales del sistema. La base real (`data/biblioteca.db`)
nunca se abre: si la ruta no es temporal, la suite se detiene.

El catálogo de demostración se reconstruye antes de cada prueba, así
ninguna prueba depende del orden en que se ejecuten las demás.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Debe quedar definido ANTES de importar app: config lo lee al cargarse.
_DIR_TEMPORAL = Path(tempfile.mkdtemp(prefix="bibloapp_pruebas_"))
os.environ["BIBLOAPP_DB"] = str(_DIR_TEMPORAL / "pruebas.db")

import pytest  # noqa: E402
from sqlalchemy import delete, select, update  # noqa: E402

from app import config  # noqa: E402
from app.db.database import engine, init_db, sesion  # noqa: E402
from app.db.models import (  # noqa: E402
    Advertencia,
    Configuracion,
    Ejemplar,
    Empleado,
    Libro,
    Movimiento,
    Multa,
    Prestamo,
    Socio,
)
from app.db.seed import sembrar_datos_iniciales  # noqa: E402
from app.services import auth  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def base_temporal() -> Iterator[None]:
    """Crea el esquema en la base temporal y lo borra al terminar."""
    if not config.DB_PATH.is_relative_to(_DIR_TEMPORAL):
        pytest.exit(
            f"Las pruebas intentaron usar {config.DB_PATH}, que no es temporal.",
            returncode=1,
        )

    init_db()
    with sesion() as db:
        sembrar_datos_iniciales(db)

    yield

    engine.dispose()
    shutil.rmtree(_DIR_TEMPORAL, ignore_errors=True)


@pytest.fixture(autouse=True)
def base_limpia(base_temporal: None) -> Iterator[None]:
    """Deja el catálogo de demostración intacto antes de cada prueba."""
    with sesion() as db:
        for modelo in (
            Movimiento,
            Advertencia,
            Multa,
            Prestamo,
            Ejemplar,
            Libro,
            Socio,
            Configuracion,
        ):
            db.execute(delete(modelo))
        # Una prueba puede desactivar una cuenta: se restaura sin recargar
        # los hashes (volver a sembrarlos costaría 3 PBKDF2 por prueba).
        db.execute(update(Empleado).values(activo=True))
        sembrar_datos_iniciales(db)

    auth.sesion_actual.cerrar()
    yield
    auth.sesion_actual.cerrar()


def _entrar(usuario: str, password: str) -> None:
    ok, mensaje, empleado = auth.autenticar(usuario, password)
    assert ok, mensaje
    auth.sesion_actual.iniciar(empleado)


@pytest.fixture
def como_admin() -> None:
    """Sesión activa con rol administrador."""
    _entrar("admin", "admin123")


@pytest.fixture
def como_bibliotecario() -> None:
    """Sesión activa con rol bibliotecario."""
    _entrar("bibliotecario", "biblio123")


@pytest.fixture
def como_auxiliar() -> None:
    """Sesión activa con rol auxiliar (sin permiso de catálogo)."""
    _entrar("auxiliar", "aux123")


@pytest.fixture
def libro_demo() -> Callable[[str], dict]:
    """Busca un libro de la semilla por título exacto."""

    def _buscar(titulo: str) -> dict:
        with sesion() as db:
            libro = db.scalar(select(Libro).where(Libro.titulo == titulo))
            assert libro is not None, f"no está en la semilla: {titulo}"
            return {
                "id": libro.id,
                "titulo": libro.titulo,
                "ejemplares": len(libro.ejemplares),
            }

    return _buscar


@pytest.fixture
def crear_socio() -> Callable[..., dict]:
    """Crea un socio suelto y devuelve sus datos mínimos."""

    def _crear(
        documento: str = "30111222",
        nombre: str = "Socio de Prueba",
        **extra: object,
    ) -> dict:
        with sesion() as db:
            socio = Socio(nombre=nombre, documento=documento, **extra)
            db.add(socio)
            db.flush()
            return {"id": socio.id, "nombre": socio.nombre, "documento": socio.documento}

    return _crear


@pytest.fixture
def prestar_a() -> Callable[..., int]:
    """Presta un ejemplar concreto a un socio concreto.

    `dias_desde` mueve la fecha del préstamo hacia atrás, que es la forma
    de simular atrasos sin esperar días reales.
    """

    def _prestar(
        socio_id: int,
        ejemplar_id: int,
        *,
        dias_vencimiento: int = 7,
        devuelto: bool = False,
        dias_desde: int = 0,
    ) -> int:
        hoy = date.today()
        inicio = hoy - timedelta(days=dias_desde)

        with sesion() as db:
            ejemplar = db.get(Ejemplar, ejemplar_id)
            assert ejemplar is not None, f"no existe el ejemplar {ejemplar_id}"

            registro = Prestamo(
                ejemplar_id=ejemplar_id,
                socio_id=socio_id,
                fecha_prestamo=inicio,
                fecha_vencimiento=inicio + timedelta(days=dias_vencimiento),
                fecha_devolucion=hoy if devuelto else None,
                estado=(
                    config.PRESTAMO_DEVUELTO if devuelto else config.PRESTAMO_ACTIVO
                ),
            )
            db.add(registro)

            if not devuelto:
                ejemplar.estado = config.EJEMPLAR_PRESTADO

            db.flush()
            return registro.id

    return _prestar


@pytest.fixture
def prestar() -> Callable[..., int]:
    """Registra un préstamo directo en la base y devuelve su id."""

    def _prestar(
        ejemplar_id: int,
        *,
        estado: str = config.PRESTAMO_ACTIVO,
        devuelto: bool = False,
    ) -> int:
        with sesion() as db:
            socio = Socio(
                nombre=f"Socio del ejemplar {ejemplar_id}",
                documento=f"9{ejemplar_id:07d}",
            )
            db.add(socio)
            db.flush()

            registro = Prestamo(
                ejemplar_id=ejemplar_id,
                socio_id=socio.id,
                fecha_vencimiento=date.today() + timedelta(days=7),
                fecha_devolucion=date.today() if devuelto else None,
                estado=estado,
            )
            db.add(registro)
            db.flush()
            return registro.id

    return _prestar
