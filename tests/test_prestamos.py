"""Pruebas del servicio de préstamos: salidas, devoluciones y renovaciones.

Los vencimientos se simulan moviendo la fecha de inicio hacia atrás con el
fixture `prestar_a`, así no hay que esperar días reales.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Configuracion, Ejemplar, Prestamo, Socio
from app.services import permisos, prestamos, reglas


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
    estado: str = config.SOCIO_ACTIVO,
) -> dict:
    """Inserta un socio sin pasar por el servicio ni por los permisos."""
    with sesion() as db:
        socio = Socio(nombre=nombre, documento=documento, tipo=tipo, estado=estado)
        db.add(socio)
        db.flush()
        return {"id": socio.id, "nombre": socio.nombre, "documento": socio.documento}


def _config(clave: str, valor: str) -> None:
    with sesion() as db:
        fila = db.get(Configuracion, clave)
        if fila is None:
            db.add(Configuracion(clave=clave, valor=valor))
        else:
            fila.valor = valor


def _registro(prestamo_id: int) -> Prestamo:
    with sesion() as db:
        prestamo = db.get(Prestamo, prestamo_id)
        assert prestamo is not None
        return prestamo


def _estado_ejemplar(ejemplar_id: int) -> str:
    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        assert ejemplar is not None
        return ejemplar.estado


# ------------------------------------------------------------------ altas
def test_prestar_un_ejemplar_disponible_lo_marca_prestado(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]

    ok, mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    assert ok and mensaje == "" and prestamo_id is not None

    registro = _registro(prestamo_id)
    assert registro.socio_id == socio["id"]
    assert registro.ejemplar_id == ejemplar_id
    assert registro.estado == config.PRESTAMO_ACTIVO
    assert registro.fecha_prestamo == date.today()
    assert registro.fecha_vencimiento == date.today() + timedelta(days=5)
    assert registro.fecha_devolucion is None
    assert registro.renovaciones == 0
    assert registro.empleado_id is not None
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_PRESTADO


def test_el_plazo_depende_del_tipo_de_socio(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    docente = _socio("30111222", "Docente", tipo=config.TIPO_DOCENTE)
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]

    ok, _mensaje, prestamo_id = prestamos.prestar(docente["id"], ejemplar_id)

    assert ok and prestamo_id is not None
    assert _registro(prestamo_id).fecha_vencimiento == date.today() + timedelta(days=15)


def test_no_se_puede_prestar_un_ejemplar_que_ya_esta_prestado(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio()
    otro = _socio("30999888", "Otro Socio")
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    prestar_a(otro["id"], ejemplar_id)

    ok, mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    assert not ok
    assert "ya está prestado" in mensaje
    assert prestamo_id is None


def test_no_se_puede_prestar_un_ejemplar_en_reparacion(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        assert ejemplar is not None
        ejemplar.estado = config.EJEMPLAR_REPARACION

    ok, mensaje, _prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    assert not ok
    assert "en reparación" in mensaje


def test_no_se_puede_prestar_a_un_socio_suspendido(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio(estado=config.SOCIO_SUSPENDIDO)
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]

    ok, mensaje, _prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    assert not ok
    assert "suspendido" in mensaje


def test_no_se_puede_prestar_a_un_socio_dado_de_baja(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio(estado=config.SOCIO_BAJA)
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]

    ok, mensaje, _prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    assert not ok
    assert "baja" in mensaje


def test_no_se_puede_prestar_a_un_socio_con_atraso_fuera_de_gracia(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio()
    libro = libro_demo("El principito")
    primero, segundo = _ejemplares(libro["id"], 2)
    prestar_a(socio["id"], primero, dias_vencimiento=3, dias_desde=10)

    ok, mensaje, _prestamo_id = prestamos.prestar(socio["id"], segundo)

    assert not ok
    assert "Bloqueado" in mensaje


def test_el_limite_de_ejemplares_bloquea_la_salida(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplares = _ejemplares(libro_demo("El principito")["id"], 4)

    for ejemplar_id in ejemplares[:3]:
        ok, mensaje, _prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
        assert ok, mensaje

    ok, mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplares[3])

    assert not ok
    assert "3 de 3" in mensaje
    assert prestamo_id is None


def test_prestar_un_ejemplar_inexistente_falla(como_admin: None) -> None:
    socio = _socio()

    ok, mensaje, _prestamo_id = prestamos.prestar(socio["id"], 999_999)

    assert not ok
    assert "ejemplar" in mensaje


def test_prestar_a_un_socio_inexistente_falla(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]

    ok, mensaje, _prestamo_id = prestamos.prestar(999_999, ejemplar_id)

    assert not ok
    assert "socio" in mensaje


# ------------------------------------------------------------- devoluciones
def test_devolver_cierra_el_prestamo_y_libera_el_ejemplar(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    ok, mensaje = prestamos.devolver(prestamo_id)

    assert ok and mensaje == ""

    registro = _registro(prestamo_id)
    assert registro.fecha_devolucion == date.today()
    assert registro.estado == config.PRESTAMO_DEVUELTO
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_DISPONIBLE


def test_devolver_en_reparacion_no_libera_el_ejemplar(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    ok, _mensaje = prestamos.devolver(
        prestamo_id, estado_ejemplar=config.EJEMPLAR_REPARACION
    )

    assert ok
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_REPARACION


def test_no_se_puede_devolver_dos_veces(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    prestamo_id = prestar_a(socio["id"], ejemplar_id, devuelto=True)

    ok, mensaje = prestamos.devolver(prestamo_id)

    assert not ok
    assert "ya figura como devuelto" in mensaje


def test_devolver_un_prestamo_inexistente_falla(como_admin: None) -> None:
    ok, mensaje = prestamos.devolver(999_999)

    assert not ok
    assert "no existe" in mensaje


# ------------------------------------------------------------- renovaciones
def test_renovar_extiende_el_vencimiento_y_cuenta_la_renovacion(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    vencimiento_original = _registro(prestamo_id).fecha_vencimiento

    ok, mensaje = prestamos.renovar(prestamo_id)

    assert ok and mensaje == ""

    registro = _registro(prestamo_id)
    assert registro.renovaciones == 1
    assert registro.fecha_vencimiento == vencimiento_original + timedelta(
        days=reglas.dias_renovacion()
    )


def test_no_se_puede_renovar_un_prestamo_devuelto(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    prestamos.devolver(prestamo_id)

    ok, mensaje = prestamos.renovar(prestamo_id)

    assert not ok
    assert "devuelto" in mensaje


def test_no_se_puede_renovar_un_prestamo_vencido(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    prestamo_id = prestar_a(
        socio["id"], ejemplar_id, dias_vencimiento=3, dias_desde=10
    )

    ok, mensaje = prestamos.renovar(prestamo_id)

    assert not ok
    assert "vencido" in mensaje


def test_no_se_puede_renovar_mas_veces_que_el_maximo(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    assert prestamos.renovar(prestamo_id)[0]

    ok, mensaje = prestamos.renovar(prestamo_id)

    assert not ok
    assert "ya se renovó 1 vez" in mensaje
    assert "máximo permitido es 1" in mensaje


def test_la_renovacion_respeta_la_configuracion(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    _config("dias_renovacion", "10")
    _config("max_renovaciones", "2")
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)
    original = _registro(prestamo_id).fecha_vencimiento

    assert prestamos.renovar(prestamo_id)[0]
    assert prestamos.renovar(prestamo_id)[0]
    ok, mensaje = prestamos.renovar(prestamo_id)

    assert not ok
    assert "ya se renovó 2 veces" in mensaje

    registro = _registro(prestamo_id)
    assert registro.renovaciones == 2
    assert registro.fecha_vencimiento == original + timedelta(days=20)


def test_sin_renovaciones_configuradas_no_se_puede_renovar(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    _config("max_renovaciones", "0")
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    ok, mensaje = prestamos.renovar(prestamo_id)

    assert not ok
    assert "deshabilitadas" in mensaje


def test_no_se_renueva_si_el_socio_esta_suspendido(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    with sesion() as db:
        registro_socio = db.get(Socio, socio["id"])
        assert registro_socio is not None
        registro_socio.estado = config.SOCIO_SUSPENDIDO

    ok, mensaje = prestamos.renovar(prestamo_id)

    assert not ok
    assert "suspendido" in mensaje
    assert prestamos.listar_prestamos()[0]["renovable"] is False


def test_no_se_renueva_con_otros_prestamos_fuera_de_gracia(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio()
    libro = libro_demo("El principito")
    primero, segundo = _ejemplares(libro["id"], 2)
    _ok, _mensaje, prestamo_id = prestamos.prestar(socio["id"], primero)
    prestar_a(socio["id"], segundo, dias_vencimiento=3, dias_desde=10)

    ok, mensaje = prestamos.renovar(prestamo_id)

    assert not ok
    assert "fuera del plazo de gracia" in mensaje


# ------------------------------------------------------------------ consultas
def test_listar_prestamos_incluye_libro_socio_y_estado(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio(nombre="Ana Pérez")
    libro = libro_demo("Ficciones")
    ejemplar_id = _ejemplares(libro["id"])[0]
    prestar_a(socio["id"], ejemplar_id)

    fila = prestamos.listar_prestamos()[0]

    assert fila["libro"] == libro["titulo"]
    assert fila["socio"] == "Ana Pérez"
    assert fila["documento"] == "30111222"
    assert fila["estado"] == config.PRESTAMO_ACTIVO
    assert fila["atraso"] == 0
    assert fila["renovable"] is True


def test_listar_prestamos_los_vencidos_primero_y_con_atraso(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    al_dia = _socio("30111222", "Al Día")
    atrasado = _socio("30999888", "Atrasado")
    libro = libro_demo("El principito")
    ejemplares = _ejemplares(libro["id"], 2)

    prestar_a(al_dia["id"], ejemplares[0])
    prestar_a(atrasado["id"], ejemplares[1], dias_vencimiento=3, dias_desde=10)

    filas = prestamos.listar_prestamos()

    assert filas[0]["socio"] == "Atrasado"
    assert filas[0]["estado"] == config.PRESTAMO_VENCIDO
    assert filas[0]["atraso"] == 7
    assert filas[0]["renovable"] is False
    assert filas[1]["estado"] == config.PRESTAMO_ACTIVO


def test_listar_prestamos_filtra_por_estado(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    libro = libro_demo("El principito")
    ejemplares = _ejemplares(libro["id"], 3)
    activo = _socio("30111222", "Activo")
    vencido = _socio("30999888", "Vencido")
    devuelto = _socio("30777666", "Devuelto")

    prestar_a(activo["id"], ejemplares[0])
    prestar_a(vencido["id"], ejemplares[1], dias_vencimiento=3, dias_desde=10)
    prestar_a(devuelto["id"], ejemplares[2], devuelto=True)

    assert [p["socio"] for p in prestamos.listar_prestamos(filtro="activos")] == [
        "Activo"
    ]
    assert [p["socio"] for p in prestamos.listar_prestamos(filtro="vencidos")] == [
        "Vencido"
    ]
    assert [p["socio"] for p in prestamos.listar_prestamos(filtro="devueltos")] == [
        "Devuelto"
    ]
    assert len(prestamos.listar_prestamos()) == 3


def test_listar_prestamos_busca_por_libro_socio_y_ejemplar(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio(nombre="Ana Pérez")
    libro = libro_demo("Ficciones")
    ejemplar_id = _ejemplares(libro["id"])[0]
    prestar_a(socio["id"], ejemplar_id)
    codigo = prestamos.listar_prestamos()[0]["ejemplar"]

    assert len(prestamos.listar_prestamos("ana perez")) == 1
    assert len(prestamos.listar_prestamos("FICCIONES")) == 1
    assert len(prestamos.listar_prestamos(codigo.lower())) == 1
    assert prestamos.listar_prestamos("rayuela") == []


def test_estadisticas_cuentan_activos_vencidos_y_devueltos(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    libro = libro_demo("El principito")
    ejemplares = _ejemplares(libro["id"], 3)
    prestar_a(_socio("30111222", "Activo")["id"], ejemplares[0])
    prestar_a(
        _socio("30999888", "Vencido")["id"],
        ejemplares[1],
        dias_vencimiento=3,
        dias_desde=10,
    )
    prestar_a(_socio("30777666", "Devuelto")["id"], ejemplares[2], devuelto=True)

    stats = prestamos.estadisticas()

    assert stats["total"] == 3
    assert stats["activos"] == 1
    assert stats["vencidos"] == 1
    assert stats["devueltos"] == 1


def test_ejemplares_disponibles_excluye_los_no_disponibles(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    libro = libro_demo("El principito")
    prestado, reparacion, libre = _ejemplares(libro["id"], 3)
    prestar_a(_socio()["id"], prestado)
    with sesion() as db:
        ejemplar = db.get(Ejemplar, reparacion)
        assert ejemplar is not None
        ejemplar.estado = config.EJEMPLAR_REPARACION

    disponibles = [e["id"] for e in prestamos.ejemplares_disponibles()]

    assert libre in disponibles
    assert prestado not in disponibles
    assert reparacion not in disponibles


def test_obtener_prestamo_inexistente_es_nulo() -> None:
    assert prestamos.obtener_prestamo(999_999) is None


# ------------------------------------------------------------------ permisos
@pytest.mark.parametrize(
    "accion",
    [
        lambda socio_id: prestamos.prestar(socio_id, 1),
        lambda _socio_id: prestamos.devolver(1),
        lambda _socio_id: prestamos.renovar(1),
    ],
)
def test_sin_sesion_iniciada_no_se_puede_escribir(
    accion: Callable[[int], tuple[bool, str, int | None] | tuple[bool, str]],
) -> None:
    resultado = accion(1)

    assert resultado[0] is False
    assert resultado[1] == permisos.SIN_PERMISO


def test_el_auxiliar_puede_registrar_un_prestamo(
    como_auxiliar: None, libro_demo: Callable[[str], dict]
) -> None:
    socio = _socio()
    ejemplar_id = _ejemplares(libro_demo("Ficciones")["id"])[0]

    ok, mensaje, prestamo_id = prestamos.prestar(socio["id"], ejemplar_id)

    assert ok, mensaje
    assert prestamo_id is not None
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_PRESTADO
