"""Pruebas de la recuperación de ejemplares marcados como perdidos.

Cubren el cambio de estado del préstamo, el reingreso del ejemplar en el
estado elegido, la anulación de la multa pendiente y la advertencia que
queda en la ficha del socio.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Advertencia, Ejemplar, Multa, Prestamo, Socio
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


def _advertencias(socio_id: int) -> list[Advertencia]:
    with sesion() as db:
        return list(
            db.scalars(
                select(Advertencia)
                .where(Advertencia.socio_id == socio_id)
                .order_by(Advertencia.id)
            )
        )


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


# --------------------------------------------------------------- recuperación
def test_recuperar_anula_la_multa_y_deja_una_advertencia(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 1_000_000)
    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]

    ok, mensaje = prestamos.recuperar(prestamo_id)

    assert ok and mensaje == ""
    registro = _registro(prestamo_id)
    assert registro.estado == config.PRESTAMO_RECUPERADO
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_DISPONIBLE

    anulada = _multa(multa_id)
    assert anulada.estado == config.MULTA_ANULADA
    assert anulada.fecha_pago is None
    assert "recuperar el ejemplar" in (anulada.notas or "")
    assert multas.deuda_pendiente(socio["id"])["cantidad"] == 0

    situacion = socios.situacion(socio["id"])
    assert situacion is not None and situacion["puede"] is True

    advertencias = _advertencias(socio["id"])
    assert len(advertencias) == 1
    assert advertencias[0].prestamo_id == prestamo_id
    assert advertencias[0].fecha == date.today()
    assert "Ficciones" in advertencias[0].motivo
    assert "$ 10.000,00" in advertencias[0].motivo


def test_recuperar_con_reparacion_deja_el_ejemplar_en_reparacion(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    _socio_registro, ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 0)

    ok, mensaje = prestamos.recuperar(prestamo_id, config.EJEMPLAR_REPARACION)

    assert ok and mensaje == ""
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_REPARACION
    assert _registro(prestamo_id).estado == config.PRESTAMO_RECUPERADO


def test_recuperar_sin_multa_deja_la_advertencia(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 0)

    ok, _mensaje = prestamos.recuperar(prestamo_id)

    assert ok
    assert multas.listar_multas(socio_id=socio["id"]) == []
    assert len(_advertencias(socio["id"])) == 1
    assert "Se anuló" not in _advertencias(socio["id"])[0].motivo


def test_recuperar_conserva_la_fecha_de_cierre_del_prestamo(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    _socio_registro, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 0)
    cierre = date.today() - timedelta(days=3)
    with sesion() as db:
        registro = db.get(Prestamo, prestamo_id)
        assert registro is not None
        registro.fecha_devolucion = cierre

    ok, _mensaje = prestamos.recuperar(prestamo_id)

    assert ok
    registro = _registro(prestamo_id)
    assert registro.fecha_devolucion == cierre
    ficha = socios.obtener_socio(_socio_registro["id"])
    assert ficha is not None
    assert ficha["historial"][0]["recuperado_el"] == date.today()


def test_el_estado_invalido_al_recuperar_deja_el_ejemplar_disponible(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    _socio_registro, ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 0)

    ok, _mensaje = prestamos.recuperar(prestamo_id, config.EJEMPLAR_PERDIDO)

    assert ok
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_DISPONIBLE


# ------------------------------------------------------------------ controles
def test_solo_se_puede_recuperar_un_prestamo_perdido(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    assert ok and prestamo_id is not None

    ok, mensaje = prestamos.recuperar(prestamo_id)

    assert not ok
    assert "marcado como perdido" in mensaje

    assert prestamos.devolver(prestamo_id)[0]
    ok, mensaje = prestamos.recuperar(prestamo_id)

    assert not ok
    assert "marcado como perdido" in mensaje


def test_no_se_puede_recuperar_dos_veces(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 250_000)
    assert prestamos.recuperar(prestamo_id)[0]

    ok, mensaje = prestamos.recuperar(prestamo_id)

    assert not ok
    assert "ya figura como recuperado" in mensaje
    assert len(_advertencias(socio["id"])) == 1


# -------------------------------------------------------------------- multas
def test_una_multa_pagada_no_se_reintegra(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 500_000)
    multa_id = multas.listar_multas(socio_id=socio["id"])[0]["id"]
    assert multas.registrar_pago(multa_id, "Pagó en mostrador")[0]

    ok, _mensaje = prestamos.recuperar(prestamo_id)

    assert ok
    pagada = _multa(multa_id)
    assert pagada.estado == config.MULTA_PAGADA
    assert pagada.fecha_pago == date.today()
    assert "Pagó en mostrador" in (pagada.notas or "")
    assert len(_advertencias(socio["id"])) == 1
    # La advertencia no anuncia una anulación que no ocurrió.
    assert "Se anuló" not in _advertencias(socio["id"])[0].motivo


# --------------------------------------------------------- filtros y contadores
def test_el_filtro_recuperados_y_los_contadores(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    _socio_registro, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 100_000)
    assert prestamos.recuperar(prestamo_id)[0]

    recuperados = prestamos.listar_prestamos(filtro="recuperados")
    stats = prestamos.estadisticas()

    assert [p["id"] for p in recuperados] == [prestamo_id]
    assert recuperados[0]["estado"] == config.PRESTAMO_RECUPERADO
    assert recuperados[0]["recuperado"] is True
    assert recuperados[0]["recuperado_el"] == date.today()
    assert recuperados[0]["devuelto"] is not None
    assert prestamos.listar_prestamos(filtro="devueltos") == []
    assert prestamos.listar_prestamos(filtro="perdidos") == []
    assert stats["recuperados"] == 1
    assert stats["devueltos"] == 0
    assert stats["perdidos"] == 0
    assert stats["activos"] == 0
    assert stats["vencidos"] == 0


def test_el_ejemplar_recuperado_vuelve_a_prestarse(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 400_000)
    assert prestamos.recuperar(prestamo_id)[0]

    ok, mensaje, nuevo_id = prestamos.prestar(socio["id"], ejemplar_id)

    assert ok, mensaje
    assert nuevo_id is not None
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_PRESTADO
    # La advertencia es informativa: no bloquea nuevas salidas.
    assert len(_advertencias(socio["id"])) == 1


def test_la_ficha_y_el_listado_muestran_la_advertencia(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 300_000)
    assert prestamos.recuperar(prestamo_id)[0]

    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None
    assert len(ficha["advertencias"]) == 1
    assert ficha["advertencias"][0]["prestamo_id"] == prestamo_id
    assert ficha["historial"][0]["estado"] == config.PRESTAMO_RECUPERADO
    assert ficha["historial"][0]["recuperado_el"] == date.today()

    fila = next(s for s in socios.listar_socios() if s["id"] == socio["id"])
    assert fila["advertencias"] == 1
    assert socios.estadisticas()["con_advertencias"] == 1


# ------------------------------------------------------------------ permisos
def test_sin_sesion_no_se_puede_recuperar() -> None:
    assert prestamos.recuperar(1)[1] == permisos.SIN_PERMISO


def test_el_auxiliar_no_puede_recuperar(
    como_auxiliar: None, libro_demo: Callable[[str], dict]
) -> None:
    _socio_registro, _ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 250_000)

    ok, mensaje = prestamos.recuperar(prestamo_id)

    assert not ok
    assert mensaje == permisos.SIN_PERMISO
    assert _registro(prestamo_id).estado == config.PRESTAMO_PERDIDO


def test_el_bibliotecario_puede_recuperar(
    como_bibliotecario: None, libro_demo: Callable[[str], dict]
) -> None:
    _socio_registro, ejemplar_id, prestamo_id = _prestamo_perdido(libro_demo, 250_000)

    ok, mensaje = prestamos.recuperar(prestamo_id)

    assert ok, mensaje
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_DISPONIBLE
