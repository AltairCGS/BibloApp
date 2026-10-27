"""Pruebas del servicio de socios: fichas, situación, historial y reglas.

«Estado» es lo que dice la ficha; «situación» es la conclusión operativa
(puede o no retirar material) y depende también de los vencimientos.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Configuracion, Ejemplar, Socio
from app.services import permisos, reglas, socios


# ------------------------------------------------------------------ helpers
def _ejemplares(libro_id: int, cantidad: int = 1) -> list[int]:
    """Ids de ejemplares disponibles de un libro, en orden estable."""
    with sesion() as db:
        return list(
            db.scalars(
                select(Ejemplar.id)
                .where(Ejemplar.libro_id == libro_id)
                .order_by(Ejemplar.id)
                .limit(cantidad)
            )
        )


def _codigo(ejemplar_id: int) -> str:
    """Código de inventario del ejemplar (los ids no son el código)."""
    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        assert ejemplar is not None
        return ejemplar.codigo_inventario


def _socio(documento: str, nombre: str = "Socio de Prueba", **extra: object) -> dict:
    ok, mensaje, socio_id = socios.crear_socio(
        {"nombre": nombre, "documento": documento, **extra}
    )
    assert ok, mensaje
    return {"id": socio_id, "nombre": nombre, "documento": documento}


def _socio_directo(
    documento: str = "30111222", nombre: str = "Socio de Prueba", **extra: object
) -> dict:
    """Inserta un socio sin pasar por el servicio ni por los permisos."""
    with sesion() as db:
        socio = Socio(nombre=nombre, documento=documento, **extra)
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


# ------------------------------------------------------------------ validación
def test_crear_socio_valido_devuelve_id_y_persiste(como_admin: None) -> None:
    ok, mensaje, socio_id = socios.crear_socio(
        {
            "nombre": "  Ana Pérez  ",
            "documento": "30111222",
            "email": "  ANA@EJEMPLO.COM ",
            "telefono": "  555-1234 ",
            "direccion": "Calle 1",
            "tipo": config.TIPO_DOCENTE,
            "estado": config.SOCIO_ACTIVO,
            "observaciones": "  Docente de historia  ",
        }
    )

    assert ok and mensaje == "" and socio_id is not None

    ficha = socios.obtener_socio(socio_id)
    assert ficha is not None
    assert ficha["nombre"] == "Ana Pérez"
    assert ficha["documento"] == "30111222"
    assert ficha["email"] == "ana@ejemplo.com"
    assert ficha["telefono"] == "555-1234"
    assert ficha["tipo"] == config.TIPO_DOCENTE
    assert ficha["observaciones"] == "Docente de historia"


def test_el_documento_acepta_puntos_y_espacios(como_admin: None) -> None:
    ok, mensaje, socio_id = socios.crear_socio(
        {"nombre": "Luis Gómez", "documento": " 30.111.222 "}
    )

    assert ok, mensaje
    ficha = socios.obtener_socio(socio_id)
    assert ficha is not None
    assert ficha["documento"] == "30111222"


@pytest.mark.parametrize("nombre", ["", " ", "A"])
def test_el_nombre_es_obligatorio(como_admin: None, nombre: str) -> None:
    ok, mensaje, socio_id = socios.crear_socio(
        {"nombre": nombre, "documento": "30111222"}
    )

    assert not ok
    assert socio_id is None
    assert "nombre" in mensaje.lower()


@pytest.mark.parametrize("documento", ["12345", "1234567890123", "abc", ""])
def test_el_documento_debe_tener_entre_6_y_12_digitos(
    como_admin: None, documento: str
) -> None:
    ok, mensaje, _ = socios.crear_socio({"nombre": "Ana", "documento": documento})

    assert not ok
    assert "documento" in mensaje.lower()


@pytest.mark.parametrize("email", ["sin-arroba", "a@b", "a b@c.com", "@ejemplo.com"])
def test_el_email_invalido_se_rechaza(como_admin: None, email: str) -> None:
    ok, mensaje, _ = socios.crear_socio(
        {"nombre": "Ana", "documento": "30111222", "email": email}
    )

    assert not ok
    assert "email" in mensaje.lower()


def test_los_opcionales_vacios_se_guardan_como_nulos(como_admin: None) -> None:
    ok, mensaje, socio_id = socios.crear_socio(
        {
            "nombre": "Ana",
            "documento": "30111222",
            "email": "",
            "telefono": "   ",
            "direccion": "",
            "observaciones": "  ",
        }
    )

    assert ok, mensaje
    with sesion() as db:
        socio = db.get(Socio, socio_id)
        assert socio is not None
        assert socio.email is None
        assert socio.telefono is None
        assert socio.direccion is None
        assert socio.observaciones is None


def test_tipo_y_estado_invalidos_caen_en_los_valores_por_defecto(
    como_admin: None,
) -> None:
    ok, mensaje, socio_id = socios.crear_socio(
        {
            "nombre": "Ana",
            "documento": "30111222",
            "tipo": "inventado",
            "estado": "inventado",
        }
    )

    assert ok, mensaje
    with sesion() as db:
        socio = db.get(Socio, socio_id)
        assert socio is not None
        assert socio.tipo == config.TIPO_EXTERNO
        assert socio.estado == config.SOCIO_ACTIVO


def test_no_se_puede_repetir_el_documento(como_admin: None) -> None:
    _socio("30111222", "Primero")

    ok, mensaje, socio_id = socios.crear_socio(
        {"nombre": "Segundo", "documento": "30111222"}
    )

    assert not ok
    assert socio_id is None
    assert "30111222" in mensaje


# ------------------------------------------------------------------ edición
def test_actualizar_socio_cambia_los_campos(como_admin: None) -> None:
    socio = _socio("30111222", "Nombre Viejo")

    ok, mensaje = socios.actualizar_socio(
        socio["id"],
        {
            "nombre": "Nombre Nuevo",
            "documento": "30111222",
            "email": "nuevo@ejemplo.com",
            "tipo": config.TIPO_ESTUDIANTE,
        },
    )

    assert ok, mensaje
    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None
    assert ficha["nombre"] == "Nombre Nuevo"
    assert ficha["email"] == "nuevo@ejemplo.com"
    assert ficha["tipo"] == config.TIPO_ESTUDIANTE


def test_actualizar_puede_conservar_el_mismo_documento(como_admin: None) -> None:
    socio = _socio("30111222")

    ok, mensaje = socios.actualizar_socio(
        socio["id"], {"nombre": "Otro Nombre", "documento": "30111222"}
    )

    assert ok, mensaje


def test_actualizar_no_permite_pisar_el_documento_de_otro(
    como_admin: None,
) -> None:
    primero = _socio("30111222", "Primero")
    segundo = _socio("30999888", "Segundo")

    ok, mensaje = socios.actualizar_socio(
        segundo["id"], {"nombre": "Segundo", "documento": primero["documento"]}
    )

    assert not ok
    assert "30111222" in mensaje


def test_actualizar_un_socio_inexistente_falla(como_admin: None) -> None:
    ok, mensaje = socios.actualizar_socio(
        999_999, {"nombre": "Fantasma", "documento": "30111222"}
    )

    assert not ok
    assert "existe" in mensaje


def test_actualizar_no_borra_la_ficha_si_los_datos_son_invalidos(
    como_admin: None,
) -> None:
    socio = _socio("30111222", "Nombre Original")

    ok, mensaje = socios.actualizar_socio(
        socio["id"], {"nombre": "", "documento": "30111222"}
    )

    assert not ok
    assert mensaje
    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None
    assert ficha["nombre"] == "Nombre Original"


# ------------------------------------------------------------------ estado
def test_cambiar_estado_a_suspendido(como_admin: None) -> None:
    socio = _socio("30111222")

    ok, mensaje = socios.cambiar_estado(socio["id"], config.SOCIO_SUSPENDIDO)

    assert ok, mensaje
    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None
    assert ficha["estado"] == config.SOCIO_SUSPENDIDO
    assert ficha["situacion"]["puede"] is False


def test_cambiar_a_un_estado_invalido_falla(como_admin: None) -> None:
    socio = _socio("30111222")

    ok, mensaje = socios.cambiar_estado(socio["id"], "desconocido")

    assert not ok
    assert "válido" in mensaje


def test_cambiar_estado_de_un_socio_inexistente_falla(como_admin: None) -> None:
    ok, mensaje = socios.cambiar_estado(999_999, config.SOCIO_BAJA)

    assert not ok
    assert "existe" in mensaje


# ------------------------------------------------------------------ borrado
def test_eliminar_socio_sin_prestamos(como_admin: None) -> None:
    socio = _socio("30111222")

    ok, mensaje = socios.eliminar_socio(socio["id"])

    assert ok, mensaje
    assert socios.obtener_socio(socio["id"]) is None


def test_no_se_puede_eliminar_un_socio_con_historial(
    como_admin: None, libro_demo: Callable[[str], dict], prestar_a: Callable[..., int]
) -> None:
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    prestar_a(socio["id"], _ejemplares(libro["id"])[0], devuelto=True)

    ok, mensaje = socios.eliminar_socio(socio["id"])

    assert not ok
    assert "Baja" in mensaje
    assert socios.obtener_socio(socio["id"]) is not None


def test_eliminar_un_socio_inexistente_falla(como_admin: None) -> None:
    ok, mensaje = socios.eliminar_socio(999_999)

    assert not ok
    assert "existe" in mensaje


# ------------------------------------------------------------------ permisos
def test_el_auxiliar_no_puede_crear_socios(como_auxiliar: None) -> None:
    ok, mensaje, socio_id = socios.crear_socio(
        {"nombre": "Ana", "documento": "30111222"}
    )

    assert not ok
    assert mensaje == permisos.SIN_PERMISO
    assert socio_id is None


def test_el_auxiliar_no_puede_editar_socios(como_auxiliar: None) -> None:
    socio = _socio_directo()

    ok, mensaje = socios.actualizar_socio(
        socio["id"], {"nombre": "Cambiado", "documento": "30111222"}
    )

    assert not ok
    assert mensaje == permisos.SIN_PERMISO


def test_el_auxiliar_no_puede_cambiar_el_estado(como_auxiliar: None) -> None:
    socio = _socio_directo()

    ok, mensaje = socios.cambiar_estado(socio["id"], config.SOCIO_BAJA)

    assert not ok
    assert mensaje == permisos.SIN_PERMISO


def test_el_auxiliar_no_puede_eliminar_socios(como_auxiliar: None) -> None:
    socio = _socio_directo()

    ok, mensaje = socios.eliminar_socio(socio["id"])

    assert not ok
    assert mensaje == permisos.SIN_PERMISO


def test_el_auxiliar_si_puede_consultar_la_ficha(como_auxiliar: None) -> None:
    # La lectura queda abierta a propósito: el auxiliar registra préstamos
    # y necesita ver la situación del socio antes de entregar material.
    socio = _socio_directo()

    assert [s["id"] for s in socios.listar_socios()] == [socio["id"]]

    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None

    situacion = socios.situacion(socio["id"])
    assert situacion is not None and situacion["puede"] is True

    assert socios.estadisticas()["socios"] == 1


def test_el_bibliotecario_puede_administrar_socios(
    como_bibliotecario: None,
) -> None:
    ok, mensaje, socio_id = socios.crear_socio(
        {"nombre": "Ana", "documento": "30111222"}
    )

    assert ok, mensaje
    assert socio_id is not None


# ------------------------------------------------------------------ listado
def test_la_busqueda_ignora_tildes_y_mayusculas(como_admin: None) -> None:
    _socio("30111222", "María Muñoz")

    assert [s["nombre"] for s in socios.listar_socios("maria munoz")] == [
        "María Muñoz"
    ]
    assert [s["nombre"] for s in socios.listar_socios("MUÑOZ")] == ["María Muñoz"]


def test_la_busqueda_mira_documento_email_y_telefono(como_admin: None) -> None:
    _socio(
        "30111222",
        "María Muñoz",
        email="maria@ejemplo.com",
        telefono="555-9876",
    )

    assert len(socios.listar_socios("30111222")) == 1
    assert len(socios.listar_socios("maria@ejemplo")) == 1
    assert len(socios.listar_socios("9876")) == 1
    assert socios.listar_socios("no-existe") == []


def test_listado_filtra_por_tipo(como_admin: None) -> None:
    _socio("30111222", "Docente Uno", tipo=config.TIPO_DOCENTE)
    _socio("30999888", "Estudiante Uno", tipo=config.TIPO_ESTUDIANTE)

    docentes = socios.listar_socios(tipo=config.TIPO_DOCENTE)

    assert [s["nombre"] for s in docentes] == ["Docente Uno"]


def test_listado_filtra_por_estado(como_admin: None) -> None:
    _socio("30111222", "Activo Uno")
    suspendido = _socio("30999888", "Suspendido Uno")
    socios.cambiar_estado(suspendido["id"], config.SOCIO_SUSPENDIDO)

    suspendidos = socios.listar_socios(estado=config.SOCIO_SUSPENDIDO)

    assert [s["nombre"] for s in suspendidos] == ["Suspendido Uno"]


def test_listado_cuenta_activos_y_vencidos(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio("30111222", "Con Préstamos")
    libro = libro_demo("Cien años de soledad")
    ejemplares = _ejemplares(libro["id"], 2)

    prestar_a(socio["id"], ejemplares[0], dias_vencimiento=3, dias_desde=10)
    prestar_a(socio["id"], ejemplares[1])

    fila = socios.listar_socios()[0]

    assert fila["activos"] == 2
    assert fila["vencidos"] == 1


def test_listado_solo_vencidos(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    al_dia = _socio("30111222", "Al Día")
    atrasado = _socio("30999888", "Atrasado")
    libro = libro_demo("Cien años de soledad")
    ejemplares = _ejemplares(libro["id"], 2)

    prestar_a(al_dia["id"], ejemplares[0])
    prestar_a(atrasado["id"], ejemplares[1], dias_vencimiento=3, dias_desde=10)

    solo_vencidos = socios.listar_socios(solo_vencidos=True)

    assert [s["nombre"] for s in solo_vencidos] == ["Atrasado"]


def test_listado_ordena_por_nombre(como_admin: None) -> None:
    for documento, nombre in [
        ("30111223", "Zulema"),
        ("30111222", "Ana"),
        ("30111224", "María"),
    ]:
        _socio(documento, nombre)

    assert [s["nombre"] for s in socios.listar_socios()] == ["Ana", "María", "Zulema"]


def test_listado_incluye_las_etiquetas_legibles(como_admin: None) -> None:
    _socio("30111222", "Ana", tipo=config.TIPO_DOCENTE)

    fila = socios.listar_socios()[0]

    assert fila["tipo_legible"] == "Docente"
    assert fila["estado_legible"] == "Activo"


# ------------------------------------------------------------------ ficha
def test_ficha_de_un_socio_inexistente_es_nula() -> None:
    assert socios.obtener_socio(999_999) is None
    assert socios.situacion(999_999) is None


def test_la_ficha_incluye_los_dias_de_prestamo_del_tipo(como_admin: None) -> None:
    docente = _socio("30111222", "Docente", tipo=config.TIPO_DOCENTE)
    externo = _socio("30999888", "Externo", tipo=config.TIPO_EXTERNO)

    ficha_docente = socios.obtener_socio(docente["id"])
    ficha_externo = socios.obtener_socio(externo["id"])

    assert ficha_docente is not None and ficha_docente["dias_prestamo"] == 15
    assert ficha_externo is not None and ficha_externo["dias_prestamo"] == 5


def test_un_socio_sin_prestamos_tiene_historial_vacio(como_admin: None) -> None:
    socio = _socio("30111222")

    ficha = socios.obtener_socio(socio["id"])

    assert ficha is not None
    assert ficha["historial"] == []
    assert ficha["total_prestamos"] == 0
    assert ficha["activos"] == 0
    assert ficha["vencidos"] == 0


def test_el_historial_ordena_lo_mas_reciente_primero(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    viejo, nuevo = _ejemplares(libro["id"], 2)

    prestar_a(socio["id"], viejo, dias_desde=20, devuelto=True)
    prestar_a(socio["id"], nuevo, dias_desde=1)

    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None

    assert [p["ejemplar"] for p in ficha["historial"]] == [
        _codigo(nuevo),
        _codigo(viejo),
    ]


def test_el_historial_marca_devuelto_activo_y_vencido(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    devuelto, activo, vencido = _ejemplares(libro["id"], 3)

    prestar_a(socio["id"], devuelto, dias_desde=30, devuelto=True)
    prestar_a(socio["id"], activo)
    prestar_a(socio["id"], vencido, dias_vencimiento=3, dias_desde=10)

    ficha = socios.obtener_socio(socio["id"])
    assert ficha is not None

    estados = {p["ejemplar"]: p["estado"] for p in ficha["historial"]}

    assert estados[_codigo(devuelto)] == config.PRESTAMO_DEVUELTO
    assert estados[_codigo(activo)] == config.PRESTAMO_ACTIVO
    assert estados[_codigo(vencido)] == config.PRESTAMO_VENCIDO
    assert ficha["activos"] == 2
    assert ficha["vencidos"] == 1
    assert ficha["atraso_maximo"] == 7
    assert ficha["total_prestamos"] == 3


# ------------------------------------------------------------------ situación
def test_un_socio_activo_sin_prestamos_puede_retirar(como_admin: None) -> None:
    socio = _socio("30111222", "Ana", tipo=config.TIPO_ESTUDIANTE)

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is True
    assert situacion["tono"] == "exito"
    assert "7 días" in situacion["motivo"]


def test_un_prestamo_dentro_del_plazo_no_bloquea(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    prestar_a(socio["id"], _ejemplares(libro["id"])[0], dias_vencimiento=10)

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is True
    assert situacion["tono"] == "exito"


def test_un_vencido_dentro_de_la_gracia_avisa_pero_no_bloquea(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    # Vence hace 3 días: el plazo de gracia es 3, así que todavía pasa.
    prestar_a(
        socio["id"], _ejemplares(libro["id"])[0], dias_vencimiento=4, dias_desde=7
    )

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is True
    assert situacion["tono"] == "aviso"
    assert "gracia" in situacion["motivo"]


def test_un_vencido_fuera_de_la_gracia_bloquea(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    prestar_a(
        socio["id"], _ejemplares(libro["id"])[0], dias_vencimiento=3, dias_desde=10
    )

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is False
    assert situacion["tono"] == "peligro"
    assert "7 días de atraso" in situacion["motivo"]


def test_solo_cuenta_los_prestamos_sin_devolver(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    prestar_a(
        socio["id"],
        _ejemplares(libro["id"])[0],
        dias_vencimiento=3,
        dias_desde=30,
        devuelto=True,
    )

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is True
    assert situacion["tono"] == "exito"


def test_un_socio_suspendido_no_puede_retirar(como_admin: None) -> None:
    socio = _socio("30111222")
    socios.cambiar_estado(socio["id"], config.SOCIO_SUSPENDIDO)

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is False
    assert "suspendido" in situacion["motivo"]


def test_un_socio_dado_de_baja_no_puede_retirar(como_admin: None) -> None:
    socio = _socio("30111222")
    socios.cambiar_estado(socio["id"], config.SOCIO_BAJA)

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is False
    assert "baja" in situacion["motivo"]


def test_el_plazo_de_gracia_se_puede_configurar(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    _config("dias_gracia_bloqueo", "5")
    socio = _socio("30111222")
    libro = libro_demo("Cien años de soledad")
    # Vence hace 4 días: con gracia de 3 bloquearía; con gracia de 5 no.
    prestar_a(
        socio["id"], _ejemplares(libro["id"])[0], dias_vencimiento=3, dias_desde=7
    )

    situacion = socios.situacion(socio["id"])

    assert situacion is not None
    assert situacion["puede"] is True
    assert situacion["tono"] == "aviso"


# ------------------------------------------------------------------ reglas
def test_las_reglas_por_defecto_salen_de_la_configuracion() -> None:
    assert reglas.dias_prestamo(config.TIPO_ESTUDIANTE) == 7
    assert reglas.dias_prestamo(config.TIPO_DOCENTE) == 15
    assert reglas.dias_prestamo(config.TIPO_EXTERNO) == 5
    assert reglas.dias_gracia_bloqueo() == 3
    assert reglas.limite_ejemplares() == 3


def test_las_reglas_se_pueden_sobrescribir() -> None:
    _config("dias_prestamo_externo", "12")
    _config("dias_gracia_bloqueo", "6")
    _config("limite_ejemplares_socio", "5")

    assert reglas.dias_prestamo(config.TIPO_EXTERNO) == 12
    assert reglas.dias_gracia_bloqueo() == 6
    assert reglas.limite_ejemplares() == 5


def test_una_regla_con_basura_usa_el_valor_por_defecto() -> None:
    _config("dias_prestamo_docente", "quince")
    _config("limite_ejemplares_socio", "")

    assert reglas.dias_prestamo(config.TIPO_DOCENTE) == 15
    assert reglas.limite_ejemplares() == 3


def test_un_tipo_desconocido_usa_el_plazo_del_externo() -> None:
    assert reglas.dias_prestamo("inventado") == reglas.dias_prestamo(
        config.TIPO_EXTERNO
    )


# ------------------------------------------------------------------ estadísticas
def test_estadisticas_cuentan_socios_estados_y_vencidos(
    como_admin: None,
    libro_demo: Callable[[str], dict],
    prestar_a: Callable[..., int],
) -> None:
    _socio("30111222", "Activo Uno")
    _socio("30111223", "Activo Dos")
    suspendido = _socio("30111224", "Suspendido")
    atrasado = _socio("30111225", "Atrasado")
    socios.cambiar_estado(suspendido["id"], config.SOCIO_SUSPENDIDO)

    libro = libro_demo("Cien años de soledad")
    prestar_a(
        atrasado["id"],
        _ejemplares(libro["id"])[0],
        dias_vencimiento=3,
        dias_desde=10,
    )

    stats = socios.estadisticas()

    assert stats["socios"] == 4
    assert stats["activos"] == 3
    assert stats["suspendidos"] == 1
    assert stats["con_vencidos"] == 1
