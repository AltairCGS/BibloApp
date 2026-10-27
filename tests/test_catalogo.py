"""Pruebas del servicio de catálogo: búsqueda, altas y reglas de borrado."""

from __future__ import annotations

from collections.abc import Callable

from app import config
from app.db.database import sesion
from app.db.models import Ejemplar
from app.services import catalogo


def _marcar_prestado(ejemplar_id: int) -> None:
    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        assert ejemplar is not None
        ejemplar.estado = config.EJEMPLAR_PRESTADO


def _ejemplares_de(libro_id: int) -> list[dict]:
    ficha = catalogo.obtener_libro(libro_id)
    assert ficha is not None
    return ficha["ejemplares"]


# ------------------------------------------------------------------ lectura
def test_la_busqueda_ignora_las_tildes() -> None:
    titulos = [l["titulo"] for l in catalogo.listar_libros("garcia")]

    assert "Cien años de soledad" in titulos
    assert "El amor en los tiempos del cólera" in titulos


def test_la_busqueda_ignora_mayusculas_y_tildes() -> None:
    assert [l["titulo"] for l in catalogo.listar_libros("AÑOS")] == [
        "Cien años de soledad"
    ]


def test_la_busqueda_mira_las_palabras_clave() -> None:
    assert [l["titulo"] for l in catalogo.listar_libros("macondo")] == [
        "Cien años de soledad"
    ]


def test_la_busqueda_encuentra_por_isbn() -> None:
    assert [l["titulo"] for l in catalogo.listar_libros("9780307474728")] == [
        "Cien años de soledad"
    ]


def test_la_busqueda_sin_resultados_devuelve_lista_vacia() -> None:
    assert catalogo.listar_libros("título que no existe") == []


def test_el_filtro_por_categoria() -> None:
    novelas = catalogo.listar_libros(categoria="Novela")

    assert len(novelas) == 4
    assert all(l["categoria"] == "Novela" for l in novelas)


def test_el_filtro_solo_disponibles_excluye_libros_sin_copias_libres(
    libro_demo: Callable[[str], dict],
) -> None:
    ficciones = libro_demo("Ficciones")
    for ejemplar in _ejemplares_de(ficciones["id"]):
        _marcar_prestado(ejemplar["id"])

    disponibles = [l["titulo"] for l in catalogo.listar_libros(solo_disponibles=True)]

    assert "Ficciones" not in disponibles
    assert len(disponibles) == 5


def test_la_ficha_incluye_codigo_y_ubicacion_de_cada_ejemplar(
    libro_demo: Callable[[str], dict],
) -> None:
    ficha = catalogo.obtener_libro(libro_demo("El principito")["id"])

    assert ficha is not None
    assert len(ficha["ejemplares"]) == 4
    primero = ficha["ejemplares"][0]
    assert primero["codigo"].startswith("EJ-")
    assert primero["ubicacion"] != ""
    assert primero["estado"] == config.EJEMPLAR_DISPONIBLE


def test_una_ficha_inexistente_devuelve_none() -> None:
    assert catalogo.obtener_libro(999_999) is None


# ---------------------------------------------------------------- escritura
def test_no_se_puede_crear_un_libro_sin_titulo(como_admin: None) -> None:
    ok, mensaje, libro_id = catalogo.crear_libro({"titulo": "   "})

    assert not ok
    assert mensaje == "El título es obligatorio."
    assert libro_id is None


def test_el_libro_creado_se_normaliza_y_aparece_en_el_listado(como_admin: None) -> None:
    ok, mensaje, libro_id = catalogo.crear_libro(
        {"titulo": "  La invención de Morel  ", "autores": "Adolfo Bioy Casares"}
    )
    assert ok, mensaje

    ficha = catalogo.obtener_libro(libro_id)
    assert ficha is not None
    assert ficha["titulo"] == "La invención de Morel"
    assert [l["id"] for l in catalogo.listar_libros("morel")] == [libro_id]


def test_un_anio_cero_se_guarda_como_sin_dato(como_admin: None) -> None:
    ok, _, libro_id = catalogo.crear_libro({"titulo": "Sin año", "anio": 0})

    assert ok
    assert catalogo.obtener_libro(libro_id)["anio"] is None


def test_el_codigo_de_inventario_continua_la_serie() -> None:
    assert catalogo.siguiente_codigo_inventario() == "EJ-00016"


def test_no_se_puede_repetir_un_codigo_de_inventario(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Ficciones")

    ok, mensaje, ejemplar_id = catalogo.agregar_ejemplar(
        libro["id"], {"codigo_inventario": "ej-00001"}
    )

    assert not ok
    assert "Ya existe un ejemplar" in mensaje
    assert ejemplar_id is None


def test_el_ejemplar_nuevo_guarda_su_ubicacion(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Ficciones")
    ubicacion = catalogo.listar_ubicaciones()[0]

    ok, mensaje, ejemplar_id = catalogo.agregar_ejemplar(
        libro["id"], {"codigo_inventario": "EJ-99999", "ubicacion_id": ubicacion["id"]}
    )
    assert ok, mensaje

    agregado = next(
        e for e in _ejemplares_de(libro["id"]) if e["id"] == ejemplar_id
    )
    assert agregado["codigo"] == "EJ-99999"
    assert agregado["ubicacion"] == ubicacion["codigo"]
    assert agregado["ubicacion_detalle"] == ubicacion["detalle"]


def test_actualizar_un_libro_cambia_sus_datos(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Rayuela")

    ok, mensaje = catalogo.actualizar_libro(
        libro["id"], {"titulo": "Rayuela (edición revisada)", "categoria": "Novela"}
    )

    assert ok, mensaje
    assert catalogo.obtener_libro(libro["id"])["titulo"] == "Rayuela (edición revisada)"


def test_actualizar_un_libro_inexistente_falla(como_admin: None) -> None:
    ok, mensaje = catalogo.actualizar_libro(999_999, {"titulo": "Fantasma"})

    assert not ok
    assert "ya no existe" in mensaje


def test_se_puede_eliminar_un_libro_sin_prestamos(como_admin: None) -> None:
    _, _, libro_id = catalogo.crear_libro({"titulo": "Libro descartable"})

    ok, mensaje = catalogo.eliminar_libro(libro_id)

    assert ok, mensaje
    assert catalogo.obtener_libro(libro_id) is None


def test_no_se_puede_eliminar_un_libro_con_prestamos(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar: Callable[..., int],
) -> None:
    libro = libro_demo("Ficciones")
    prestar(_ejemplares_de(libro["id"])[0]["id"])

    ok, mensaje = catalogo.eliminar_libro(libro["id"])

    assert not ok
    assert "préstamos registrados" in mensaje
    assert catalogo.obtener_libro(libro["id"]) is not None


def test_no_se_puede_eliminar_un_ejemplar_prestado(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Ficciones")
    ejemplar_id = _ejemplares_de(libro["id"])[0]["id"]
    _marcar_prestado(ejemplar_id)

    ok, mensaje = catalogo.eliminar_ejemplar(ejemplar_id)

    assert not ok
    assert "está prestado" in mensaje


def test_no_se_puede_eliminar_un_ejemplar_con_historial(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar: Callable[..., int],
) -> None:
    libro = libro_demo("Ficciones")
    ejemplar_id = _ejemplares_de(libro["id"])[0]["id"]
    prestar(ejemplar_id, estado=config.PRESTAMO_DEVUELTO, devuelto=True)

    ok, mensaje = catalogo.eliminar_ejemplar(ejemplar_id)

    assert not ok
    assert "historial de préstamos" in mensaje


def test_el_formulario_no_puede_cambiar_el_estado_de_un_ejemplar_prestado(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Ficciones")
    ejemplar = _ejemplares_de(libro["id"])[0]
    _marcar_prestado(ejemplar["id"])

    ok, mensaje = catalogo.actualizar_ejemplar(
        ejemplar["id"],
        {"codigo_inventario": ejemplar["codigo"], "estado": config.EJEMPLAR_DISPONIBLE},
    )

    assert ok, mensaje
    actualizado = next(
        e for e in _ejemplares_de(libro["id"]) if e["id"] == ejemplar["id"]
    )
    assert actualizado["estado"] == config.EJEMPLAR_PRESTADO


def test_las_estadisticas_coinciden_con_la_semilla() -> None:
    assert catalogo.estadisticas() == {
        "libros": 6,
        "ejemplares": 15,
        "disponibles": 15,
    }
