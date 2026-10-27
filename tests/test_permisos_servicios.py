"""Pruebas de la barrera de permisos dentro de los servicios.

La interfaz oculta módulos según el rol, pero eso no alcanza: cada
servicio que escribe vuelve a preguntar quién lo llama.
"""

from __future__ import annotations

from collections.abc import Callable

from app.services import catalogo
from app.services import permisos
from app.services.auth import sesion_actual


def test_el_admin_puede_crear_un_libro(como_admin: None) -> None:
    ok, mensaje, libro_id = catalogo.crear_libro({"titulo": "Libro del admin"})

    assert ok, mensaje
    assert libro_id is not None


def test_el_bibliotecario_puede_crear_un_libro(como_bibliotecario: None) -> None:
    ok, mensaje, _ = catalogo.crear_libro({"titulo": "Libro del bibliotecario"})

    assert ok, mensaje


def test_el_auxiliar_no_puede_crear_un_libro(como_auxiliar: None) -> None:
    ok, mensaje, libro_id = catalogo.crear_libro({"titulo": "Libro no autorizado"})

    assert not ok
    assert mensaje == permisos.SIN_PERMISO
    assert libro_id is None


def test_el_auxiliar_no_puede_editar_ni_eliminar(
    como_auxiliar: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Ficciones")

    assert not catalogo.actualizar_libro(libro["id"], {"titulo": "Cambiado"})[0]
    assert not catalogo.eliminar_libro(libro["id"])[0]
    assert catalogo.obtener_libro(libro["id"])["titulo"] == "Ficciones"


def test_el_auxiliar_no_puede_tocar_ejemplares(
    como_auxiliar: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Ficciones")
    ficha = catalogo.obtener_libro(libro["id"])
    ejemplar_id = ficha["ejemplares"][0]["id"]

    ok, mensaje, _ = catalogo.agregar_ejemplar(
        libro["id"], {"codigo_inventario": "EJ-AUXILIAR"}
    )
    assert not ok and mensaje == permisos.SIN_PERMISO

    assert not catalogo.actualizar_ejemplar(ejemplar_id, {"codigo_inventario": "EJ-1"})[0]
    assert not catalogo.eliminar_ejemplar(ejemplar_id)[0]


def test_sin_sesion_tampoco_se_puede_escribir() -> None:
    assert not sesion_actual.autenticado

    ok, mensaje, _ = catalogo.crear_libro({"titulo": "Sin sesión"})

    assert not ok
    assert mensaje == permisos.SIN_PERMISO


def test_el_auxiliar_si_puede_consultar_el_catalogo(como_auxiliar: None) -> None:
    """Necesita ver los libros para poder registrar un préstamo."""
    assert catalogo.listar_libros()
    assert catalogo.estadisticas()["libros"] > 0


def test_el_permiso_se_verifica_antes_que_los_datos(como_auxiliar: None) -> None:
    """El rechazo llega primero: no se filtran pistas de validación."""
    ok, mensaje, _ = catalogo.crear_libro({})

    assert not ok
    assert mensaje == permisos.SIN_PERMISO
