"""Pruebas del módulo Vencidos: listado, filtros, resumen, CSV y acciones.

Los atrasos se simulan moviendo la fecha del préstamo hacia atrás con el
fixture `prestar_a`, así no hay que esperar días reales. El criterio de
«vencido» es el mismo de Préstamos: abierto y con vencimiento anterior a hoy.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Configuracion, Ejemplar, Movimiento, Multa, Prestamo
from app.services import permisos, prestamos, vencidos


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


def _config(clave: str, valor: str) -> None:
    with sesion() as db:
        db.merge(Configuracion(clave=clave, valor=valor))


def _estado_ejemplar(ejemplar_id: int) -> str:
    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        assert ejemplar is not None
        return ejemplar.estado


def _cerrado(ejemplar_id: int, socio_id: int, estado: str) -> int:
    """Préstamo cerrado a mano (perdido o recuperado) con vencimiento viejo."""
    hoy = date.today()
    with sesion() as db:
        registro = Prestamo(
            ejemplar_id=ejemplar_id,
            socio_id=socio_id,
            fecha_prestamo=hoy - timedelta(days=30),
            fecha_vencimiento=hoy - timedelta(days=23),
            fecha_devolucion=hoy,
            estado=estado,
        )
        db.add(registro)
        db.flush()
        return registro.id


def _movimientos(accion: str) -> list[Movimiento]:
    with sesion() as db:
        return list(
            db.scalars(
                select(Movimiento)
                .where(Movimiento.accion == accion)
                .order_by(Movimiento.id)
            )
        )


def _multas(prestamo_id: int) -> list[Multa]:
    with sesion() as db:
        return list(
            db.scalars(select(Multa).where(Multa.prestamo_id == prestamo_id))
        )


# ------------------------------------------------------------------ listado
def test_solo_aparecen_los_prestamos_abiertos_y_vencidos(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = crear_socio("30111222", "Ana Vencida")
    otro = crear_socio("30999888", "Otro Socio")
    ejemplares = _ejemplares(libro_demo("El principito")["id"], 4) + _ejemplares(
        libro_demo("Ficciones")["id"], 1
    )

    vencido = prestar_a(socio["id"], ejemplares[0], dias_desde=30, dias_vencimiento=7)
    prestar_a(socio["id"], ejemplares[1], dias_desde=30, devuelto=True)
    prestar_a(otro["id"], ejemplares[2], dias_desde=2, dias_vencimiento=7)
    _cerrado(ejemplares[3], socio["id"], config.PRESTAMO_PERDIDO)
    _cerrado(ejemplares[4], otro["id"], config.PRESTAMO_RECUPERADO)

    filas = vencidos.listar_vencidos()

    assert [fila["id"] for fila in filas] == [vencido]
    assert filas[0]["atraso"] == 23
    assert filas[0]["dias_atraso"] == 23


def test_el_mas_atrasado_aparece_primero(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = crear_socio("30111222", "Ana Vencida")
    ejemplares = _ejemplares(libro_demo("El principito")["id"], 3)

    prestar_a(socio["id"], ejemplares[0], dias_desde=9, dias_vencimiento=7)
    prestar_a(socio["id"], ejemplares[1], dias_desde=37, dias_vencimiento=7)
    prestar_a(socio["id"], ejemplares[2], dias_desde=17, dias_vencimiento=7)

    filas = vencidos.listar_vencidos()

    assert [fila["atraso"] for fila in filas] == [30, 10, 2]


def test_la_busqueda_ignora_tildes_y_mayusculas_en_todos_los_campos(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = crear_socio(
        "30111222",
        "García, Ana",
        tipo=config.TIPO_DOCENTE,
        telefono="11 5555-1234",
        email="ana@ejemplo.com",
    )
    ejemplar_id = _ejemplares(libro_demo("El principito")["id"], 1)[0]
    prestar_a(socio["id"], ejemplar_id, dias_desde=30, dias_vencimiento=7)
    codigo = next(
        fila["ejemplar"] for fila in vencidos.listar_vencidos()
    )

    for termino in (
        "garcia",
        "GARCÍA",
        "3011",
        "11 5555",
        "ANA@EJEMPLO",
        "principito",
        codigo.lower(),
    ):
        assert len(vencidos.listar_vencidos(busqueda=termino)) == 1, termino

    assert vencidos.listar_vencidos(busqueda="no existe") == []


def test_la_fila_trae_contacto_y_tipo_de_socio(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = crear_socio(
        "30111222",
        "García, Ana",
        tipo=config.TIPO_DOCENTE,
        telefono="11 5555-1234",
        email="ana@ejemplo.com",
    )
    ejemplar_id = _ejemplares(libro_demo("El principito")["id"], 1)[0]
    prestar_a(socio["id"], ejemplar_id, dias_desde=30, dias_vencimiento=7)

    fila = vencidos.listar_vencidos()[0]

    assert fila["socio"] == "García, Ana"
    assert fila["documento"] == "30111222"
    assert fila["telefono"] == "11 5555-1234"
    assert fila["email"] == "ana@ejemplo.com"
    assert fila["tipo_socio"] == "Docente"
    assert fila["libro"] == "El principito"
    assert fila["prestamo_id"] == fila["id"]
    assert fila["socio_id"] == socio["id"]


def test_la_gracia_se_lee_de_la_configuracion_y_filtra_el_listado(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = crear_socio("30111222", "Ana Vencida")
    ejemplar_id = _ejemplares(libro_demo("El principito")["id"], 1)[0]
    prestar_a(socio["id"], ejemplar_id, dias_desde=30, dias_vencimiento=7)

    fila = vencidos.listar_vencidos()[0]
    assert fila["atraso"] == 23
    assert fila["en_gracia"] is False
    assert len(vencidos.listar_vencidos(solo_fuera_de_gracia=True)) == 1

    _config("dias_gracia_bloqueo", "30")

    fila = vencidos.listar_vencidos()[0]
    assert fila["en_gracia"] is True
    assert vencidos.listar_vencidos(solo_fuera_de_gracia=True) == []


def test_resumen_cuenta_total_socios_maximo_y_fuera_de_gracia(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    ana = crear_socio("30111222", "Ana Vencida")
    bruno = crear_socio("30999888", "Bruno Atrasado")
    ejemplares = _ejemplares(libro_demo("El principito")["id"], 3)

    prestar_a(ana["id"], ejemplares[0], dias_desde=17, dias_vencimiento=7)
    prestar_a(ana["id"], ejemplares[1], dias_desde=37, dias_vencimiento=7)
    prestar_a(bruno["id"], ejemplares[2], dias_desde=27, dias_vencimiento=7)

    resumen = vencidos.resumen()

    assert resumen == {
        "total": 3,
        "socios": 2,
        "maximo_atraso": 30,
        "fuera_de_gracia": 3,
    }

    resumen_ana = vencidos.resumen(busqueda="ana")
    assert resumen_ana == {
        "total": 2,
        "socios": 1,
        "maximo_atraso": 30,
        "fuera_de_gracia": 2,
    }


# ------------------------------------------------------------------ CSV
def test_exportar_csv_escribe_bom_encabezado_y_una_fila_por_prestamo(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
    tmp_path,
) -> None:
    socio = crear_socio(
        "30111222",
        "García, Ana",
        telefono="11 5555-1234",
        email="ana@ejemplo.com",
    )
    ejemplares = _ejemplares(libro_demo("El principito")["id"], 2)
    primero = prestar_a(socio["id"], ejemplares[0], dias_desde=37, dias_vencimiento=7)
    prestar_a(socio["id"], ejemplares[1], dias_desde=17, dias_vencimiento=7)
    ruta = tmp_path / "vencidos.csv"

    ok, mensaje = vencidos.exportar_csv(str(ruta))

    assert ok and mensaje == ""
    assert ruta.exists()

    crudo = ruta.read_bytes()
    assert crudo.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in crudo

    lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    assert lineas[0] == (
        "Documento;Socio;Teléfono;Correo;Ejemplar;Libro;Prestado;Vence;Días de atraso"
    )
    assert len(lineas) == 3

    filas = vencidos.listar_vencidos()
    esperada = ";".join(
        [
            filas[0]["documento"],
            filas[0]["socio"],
            filas[0]["telefono"],
            filas[0]["email"],
            filas[0]["ejemplar"],
            filas[0]["libro"],
            f"{filas[0]['desde']:%d/%m/%Y}",
            f"{filas[0]['vence']:%d/%m/%Y}",
            str(filas[0]["dias_atraso"]),
        ]
    )
    assert lineas[1] == esperada
    assert lineas[1].endswith(";30")
    assert lineas[2].endswith(";10")
    assert filas[0]["id"] == primero


def test_exportar_csv_sin_filas_avisa(
    como_admin: None, tmp_path
) -> None:
    ruta = tmp_path / "vacios.csv"

    ok, mensaje = vencidos.exportar_csv(str(ruta))

    assert not ok
    assert "No hay préstamos vencidos" in mensaje
    assert not ruta.exists()


def test_exportar_csv_sin_sesion_no_escribe(tmp_path) -> None:
    ruta = tmp_path / "sin_permiso.csv"

    ok, mensaje = vencidos.exportar_csv(str(ruta))

    assert not ok
    assert mensaje == permisos.SIN_PERMISO
    assert not ruta.exists()


def test_exportar_csv_deja_un_movimiento_recordatorio(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
    tmp_path,
) -> None:
    socio = crear_socio("30111222", "Ana Vencida")
    ejemplar_id = _ejemplares(libro_demo("El principito")["id"], 1)[0]
    prestar_a(socio["id"], ejemplar_id, dias_desde=30, dias_vencimiento=7)
    ruta = tmp_path / "recordatorio.csv"

    ok, _mensaje = vencidos.exportar_csv(str(ruta), solo_fuera_de_gracia=True)

    assert ok
    movimientos = _movimientos("recordatorio")
    assert len(movimientos) == 1
    assert movimientos[0].entidad == "vencidos"
    assert movimientos[0].entidad_id is None
    assert movimientos[0].empleado_id is not None
    assert "1 préstamo vencido" in movimientos[0].detalle
    assert ruta.name in movimientos[0].detalle
    assert "gracia" in movimientos[0].detalle


# ------------------------------------------------------------------ acciones
def test_devolver_un_vencido_lo_saca_del_listado_y_libera_el_ejemplar(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = crear_socio("30111222", "Ana Vencida")
    ejemplar_id = _ejemplares(libro_demo("El principito")["id"], 1)[0]
    prestamo_id = prestar_a(
        socio["id"], ejemplar_id, dias_desde=30, dias_vencimiento=7
    )
    assert len(vencidos.listar_vencidos()) == 1

    ok, mensaje = prestamos.devolver(prestamo_id)

    assert ok and mensaje == ""
    assert vencidos.listar_vencidos() == []
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_DISPONIBLE


def test_marcar_perdido_un_vencido_lo_saca_del_listado_y_genera_la_multa(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    crear_socio: Callable[..., dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = crear_socio("30111222", "Ana Vencida")
    ejemplar_id = _ejemplares(libro_demo("El principito")["id"], 1)[0]
    prestamo_id = prestar_a(
        socio["id"], ejemplar_id, dias_desde=30, dias_vencimiento=7
    )

    ok, mensaje = prestamos.marcar_perdido(prestamo_id, 500_000)

    assert ok and mensaje == ""
    assert vencidos.listar_vencidos() == []
    assert _estado_ejemplar(ejemplar_id) == config.EJEMPLAR_PERDIDO

    multas = _multas(prestamo_id)
    assert len(multas) == 1
    assert multas[0].estado == config.MULTA_PENDIENTE
    assert multas[0].monto_centavos == 500_000
