"""Pruebas del importador de catálogo JSON."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import func, select

from app import config
from app.db import importar
from app.db.database import sesion
from app.db.models import Ejemplar, Libro, Socio


def datos_ejemplo() -> dict:
    return {
        "libros": [
            {
                "titulo": "Libro importado A",
                "autores": ["Autora A"],
                "editorial": "Editorial A",
                "anio": 2001,
                "categoria": "Novela",
                "dewey": "863",
                "sinopsis": "Sinopsis del libro A.",
                "palabras_clave": ["clave1", "clave2"],
                "ejemplares": 2,
            },
            {
                "titulo": "Libro importado B",
                "autores": ["Autor B", "Autora B"],
                "categoria": "Cuento",
                "dewey": "863",
                "ejemplares": 1,
            },
        ],
        "socios": [
            {
                "nombre": "Socia Importada",
                "documento": "40111222",
                "email": "socia@ejemplo.com",
                "tipo": config.TIPO_DOCENTE,
            }
        ],
    }


def _contar(modelo: type) -> int:
    with sesion() as db:
        return db.scalar(select(func.count()).select_from(modelo)) or 0


def test_importa_libros_ejemplares_y_socios() -> None:
    resumen = importar.importar(datos_ejemplo())

    assert resumen["libros"] == 2
    assert resumen["ejemplares"] == 3
    assert resumen["socios"] == 1
    assert _contar(Libro) == 8
    assert _contar(Ejemplar) == 18
    assert _contar(Socio) == 1


def test_arma_autores_y_palabras_clave() -> None:
    importar.importar(datos_ejemplo())

    with sesion() as db:
        libro = db.scalar(select(Libro).where(Libro.titulo == "Libro importado B"))

    assert libro is not None
    assert libro.autores == "Autor B; Autora B"
    assert libro.idioma == "es"


def test_la_segunda_importacion_no_duplica_nada() -> None:
    importar.importar(datos_ejemplo())

    resumen = importar.importar(datos_ejemplo())

    assert resumen == {"libros": 0, "ejemplares": 0, "socios": 0, "omitidos": 2}
    assert _contar(Libro) == 8
    assert _contar(Ejemplar) == 18


def test_reemplazar_borra_el_catalogo_anterior() -> None:
    resumen = importar.importar(datos_ejemplo(), reemplazar=True)

    assert resumen["libros"] == 2
    assert _contar(Libro) == 2
    assert _contar(Ejemplar) == 3


def test_reemplazar_se_niega_si_hay_prestamos(
    libro_demo: Callable[[str], dict],
    prestar: Callable[..., int],
) -> None:
    with sesion() as db:
        ejemplar = db.scalars(select(Ejemplar)).first()

    assert ejemplar is not None
    prestar(ejemplar.id)

    with pytest.raises(SystemExit) as salida:
        importar.importar(datos_ejemplo(), reemplazar=True)

    assert "préstamo" in str(salida.value) or "prestamo" in str(salida.value)
    assert _contar(Libro) == 6


def test_los_codigos_de_inventario_siguen_la_serie() -> None:
    importar.importar(datos_ejemplo())

    with sesion() as db:
        codigos = set(db.scalars(select(Ejemplar.codigo_inventario)).all())

    assert {"EJ-00016", "EJ-00017", "EJ-00018"} <= codigos
