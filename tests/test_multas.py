"""Pruebas de multas por ejemplares perdidos y su efecto en el socio.

Cubren el cierre del préstamo como perdido, la multa generada, el bloqueo
del socio mientras la deuda está pendiente y las dos formas de levantarlo:
registrar el pago o anular la multa.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Ejemplar, Multa, Prestamo, Socio
from app.services import multas, permisos, prestamos, socios


# ------------------------------------------------------------------ helpers
def _ejemplares(libro_id: int, cantidad: int = 1) -> list[int]:
    """Ids de ejemplares de un libro, en orden estable."""
    with sesion() as db:
        return list(
            db.scalars(
                select(Ejemplar.id)
                .where(Ejemplar.libro_id == libro_id)
                .order_by(Ejemplar.id)
                .limit(cantidad)
            )
        )


def _socio(
    documento: str = "30111222",
    nombre: str = "Socio de Prueba",
    tipo: str = config.TIPO_EXTERNO,
) -> dict:
    """Inserta un socio sin pasar por el servicio ni por los permisos."""
    with sesion() as db:
        socio = Socio(nombre=nombre, documento=documento, tipo=tipo)
        db.add(socio)
        db.flush()
        return {"id": socio.id, "nombre": socio.nombre, "documento": socio.documento}


def _registro(prestamo_id: int) -> Prestamo:
    with sesion() as db:
        prestamo = db.get(Prestamo, prestamo_id)
        assert prestamo is not None
        return prestamo


def _multa(multa_id: int) -> Multa:
    with sesion() as db:
        multa = db.get(Multa, multa_id)
        assert multa is not None
        return multa


def _estado_ejemplar(ejemplar_id: int) -> str:
    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        assert ejemplar is not None
        return ejemplar.estado


def _prestamo_perdido(
    libro_demo: Callable[[str], dict],
    monto_centavos: int = 1_000_000,
    *,
    titulo: str = "Ficciones",
    indice: int = 0,
) -> tuple[dict, int, int]:
    """Deja un préstamo marcado como perdido y devuelve socio, ejemplar y préstamo."""
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo(titulo)["id"])[indice]
    ok, mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    assert ok, mensaje
    assert prestamo_id is not None

    ok, mensaje = prestamos.marcar_perdido(prestamo_id, monto_centavos)
    assert ok, mensaje
    return socio, ejemplar_id, prestamo_id


# ------------------------------------------------------------------- pérdida
def test_marcar_perdido_cierra_el_prestamo_y_genera_la_multa(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    ok, mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    assert ok, mensaje and prestamo_id is not None

    ok, mensaje = prestamos.marcar_perdido(
        prestamo_id, 1_000_000, "Se perdió en un viaje"
    )

    assert ok and mensaje == ""
    registro = _registro(prestamo_id)
    assert registro.estado == config.PRESTAMO_PERDIDO
    assert registro.fecha_devolucion == date.today()
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_PERDIDO

    lista = multas.listar_multas(socio_id=socio["id"])
    assert len(lista) == 1
    assert lista[0]["monto_centavos"] == 1_000_000
    assert lista[0]["monto"] == "$ 10.000,00"
    assert lista[0]["estado"] == config.MULTA_PENDIENTE
    assert lista[0]["prestamo_id"] == prestamo_id
    assert "EJ-" in lista[0]["concepto"]
    assert "Ficciones" in lista[0]["concepto"]
    assert lista[0]["notas"] == "Se perdió en un viaje"


def test_marcar_perdido_sin_monto_no_genera_multa(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    assert ok and prestamo_id is not None

    ok, _mensaje = prestamos.marcar_perdido(prestamo_id, 0)

    assert ok
    assert multas.listar_multas(socio_id=socio["id"]) == []
    assert socios.situacion(socio["id"])["puede"] is True


def test_no_se_puede_marcar_dos_veces_el_mismo_prestamo(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, prestamo_id = _prestamo_perdido(
        libro_demo, 500_000
    )

    ok, mensaje = prestamos.marcar_perdido(prestamo_id, 500_000)

    assert not ok
    assert "ya figura como perdido" in mensaje
    assert len(multas.listar_multas(socio_id=socio["id"])) == 1


def test_no_se_puede_marcar_perdido_un_prestamo_ya_devuelto(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    assert ok and prestamo_id is not None
    ok, _mensaje = prestamos.devolver(prestamo_id)
    assert ok

    ok, mensaje = prestamos.marcar_perdido(prestamo_id)

    assert not ok
    assert "ya está cerrado" in mensaje


# --------------------------------------------------------------- bloqueo
def test_la_multa_pendiente_bloquea_nuevos_prestamos(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, _prestamo_id = _prestamo_perdido(libro_demo, 500_000)
    otro_ejemplar = _ejemplares(libro_demo("El principito")["id"])[0]

    situacion = socios.situacion(socio["id"])
    assert situacion is not None
    assert situacion["puede"] is False
    assert "multa pendiente" in situacion["motivo"]
    assert situacion["deuda_centavos"] == 500_000
    assert situacion["multas_pendientes"] == 1

    ok, mensaje, nuevo_id = prestamos.prestar(socio["id"], otro_ejemplar)

    assert not ok
    assert nuevo_id is None
    assert "multa" in mensaje.lower()


def test_pagar_la_multa_desbloquea_al_socio(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, _prestamo_id = _prestamo_perdido(libro_demo, 750_000)
    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]

    ok, mensaje = multas.registrar_pago(multa_id)

    assert ok and mensaje == ""
    registro = _multa(multa_id)
    assert registro.estado == config.MULTA_PAGADA
    assert registro.fecha_pago == date.today()

    situacion = socios.situacion(socio["id"])
    assert situacion is not None and situacion["puede"] is True

    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None
    assert ficha["multas_pendientes"] == 0
    assert ficha["deuda_centavos"] == 0


def test_anular_la_multa_la_deja_sin_efecto(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, _prestamo_id = _prestamo_perdido(libro_demo, 300_000)
    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]

    ok, mensaje = multas.anular_multa(multa_id, "Apareció el ejemplar")

    assert ok and mensaje == ""
    registro = _multa(multa_id)
    assert registro.estado == config.MULTA_ANULADA
    assert registro.fecha_pago is None
    assert "Apareció el ejemplar" in (registro.notas or "")
    assert socios.situacion(socio["id"])["puede"] is True


def test_no_se_puede_cobrar_una_multa_anulada(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, _prestamo_id = _prestamo_perdido(libro_demo, 200_000)
    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]
    assert multas.anular_multa(multa_id)[0]

    ok, mensaje = multas.registrar_pago(multa_id)

    assert not ok
    assert "anulada" in mensaje


def test_no_se_puede_anular_una_multa_pagada(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, _prestamo_id = _prestamo_perdido(libro_demo, 200_000)
    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]
    assert multas.registrar_pago(multa_id)[0]

    ok, mensaje = multas.anular_multa(multa_id)

    assert not ok
    assert "pagada" in mensaje


def test_una_multa_anulada_no_suma_a_la_deuda(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, _prestamo_id = _prestamo_perdido(libro_demo, 400_000)
    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]
    assert multas.anular_multa(multa_id)[0]

    deuda = multas.deuda_pendiente(socio["id"])

    assert deuda["cantidad"] == 0
    assert deuda["total_centavos"] == 0


# ------------------------------------------------------------------ ficha
def test_la_ficha_del_socio_muestra_la_multa_y_el_prestamo_perdido(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 650_000)

    ficha = socios.obtener_socio(socio["id"])

    assert ficha is not None
    assert ficha["multas_pendientes"] == 1
    assert ficha["deuda_centavos"] == 650_000
    assert ficha["deuda"] == "$ 6.500,00"
    assert len(ficha["multas"]) == 1
    assert ficha["multas"][0]["estado_legible"] == "Pendiente"
    assert ficha["multas"][0]["prestamo_id"] == prestamo_id
    assert ficha["historial"][0]["estado"] == config.PRESTAMO_PERDIDO
    assert ficha["situacion"]["puede"] is False
    assert "multa pendiente" in ficha["situacion"]["motivo"]


def test_el_listado_marca_los_socios_con_multas_pendientes(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, _prestamo_id = _prestamo_perdido(libro_demo, 100_000)

    listado = socios.listar_socios()

    fila = next(s for s in listado if s["id"] == socio["id"])
    assert fila["multas"] == 1
    assert socios.estadisticas()["con_multas"] == 1


# ------------------------------------------------------- filtros y contadores
def test_el_filtro_perdidos_y_los_contadores_del_modulo(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    _socio, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 100_000)

    perdidos = prestamos.listar_prestamos(filtro="perdidos")
    devueltos = prestamos.listar_prestamos(filtro="devueltos")
    stats = prestamos.estadisticas()

    assert [p["id"] for p in perdidos] == [prestamo_id]
    assert all(p["estado"] == config.PRESTAMO_PERDIDO for p in perdidos)
    assert all(p["devuelto"] is not None for p in perdidos)
    assert devueltos == []
    assert stats["perdidos"] == 1
    assert stats["devueltos"] == 0
    assert stats["activos"] == 0
    assert stats["vencidos"] == 0


# ------------------------------------------------------------------ permisos
def test_sin_sesion_no_se_puede_marcar_perdido_ni_cobrar() -> None:
    assert prestamos.marcar_perdido(1)[1] == permisos.SIN_PERMISO
    assert multas.registrar_pago(1)[1] == permisos.SIN_PERMISO
    assert multas.anular_multa(1)[1] == permisos.SIN_PERMISO


def test_el_auxiliar_puede_marcar_perdido_pero_no_cobrar_la_multa(
    como_auxiliar: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    assert ok and prestamo_id is not None

    ok, _mensaje = prestamos.marcar_perdido(prestamo_id, 250_000)
    assert ok

    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]
    ok, mensaje = multas.registrar_pago(multa_id)
    assert not ok
    assert mensaje == permisos.SIN_PERMISO


# ------------------------------------------------------------------- formato
@pytest.mark.parametrize(
    ("centavos", "texto"),
    [
        (0, "$ 0,00"),
        (50, "$ 0,50"),
        (1_000_000, "$ 10.000,00"),
        (123_456_789, "$ 1.234.567,89"),
    ],
)
def test_formatear_monto(centavos: int, texto: str) -> None:
    assert multas.formatear_monto(centavos) == texto
