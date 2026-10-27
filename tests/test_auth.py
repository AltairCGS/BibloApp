"""Pruebas de autenticación, sesión activa y auditoría."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Empleado, Movimiento
from app.services import auth
from app.services.auth import sesion_actual


def test_el_login_correcto_devuelve_el_empleado() -> None:
    ok, mensaje, empleado = auth.autenticar("admin", "admin123")

    assert ok
    assert mensaje == ""
    assert empleado is not None
    assert empleado.usuario == "admin"
    assert empleado.rol == config.ROL_ADMIN


def test_el_login_queda_registrado_en_la_auditoria() -> None:
    auth.autenticar("admin", "admin123")

    with sesion() as db:
        acciones = db.scalars(select(Movimiento.accion)).all()

    assert "inicio_sesion" in acciones


def test_el_login_actualiza_el_ultimo_acceso() -> None:
    _, _, empleado = auth.autenticar("auxiliar", "aux123")

    assert empleado.ultimo_acceso is not None


def test_usuario_inexistente_y_clave_erronea_dan_el_mismo_mensaje() -> None:
    """No se revela si la cuenta existe."""
    _, mensaje_usuario, _ = auth.autenticar("no-existe", "lo-que-sea")
    _, mensaje_clave, _ = auth.autenticar("admin", "incorrecta")

    assert mensaje_usuario == mensaje_clave


def test_una_cuenta_desactivada_no_puede_entrar() -> None:
    with sesion() as db:
        empleado = db.scalar(select(Empleado).where(Empleado.usuario == "auxiliar"))
        assert empleado is not None
        empleado.activo = False

    ok, mensaje, empleado = auth.autenticar("auxiliar", "aux123")

    assert not ok
    assert empleado is None
    assert "deshabilitada" in mensaje


@pytest.mark.parametrize(
    "usuario,password",
    [("", ""), ("admin", ""), ("   ", "x"), ("", "x")],
)
def test_las_credenciales_incompletas_se_rechazan(
    usuario: str, password: str
) -> None:
    ok, _, empleado = auth.autenticar(usuario, password)

    assert not ok
    assert empleado is None


def test_la_sesion_guarda_y_limpia_el_empleado_activo() -> None:
    _, _, empleado = auth.autenticar("bibliotecario", "biblio123")

    assert not sesion_actual.autenticado

    sesion_actual.iniciar(empleado)
    assert sesion_actual.autenticado
    assert sesion_actual.nombre == "Bibliotecaria"
    assert sesion_actual.rol == config.ROL_BIBLIOTECARIO
    assert sesion_actual.rol_legible == "Bibliotecario"

    sesion_actual.cerrar()
    assert not sesion_actual.autenticado


@pytest.mark.parametrize(
    "rol,permiso,esperado",
    [
        (config.ROL_ADMIN, "catalogo", True),
        (config.ROL_ADMIN, "empleados", True),
        (config.ROL_BIBLIOTECARIO, "catalogo", True),
        (config.ROL_BIBLIOTECARIO, "empleados", False),
        (config.ROL_AUXILIAR, "prestamos", True),
        (config.ROL_AUXILIAR, "vencidos", True),
        (config.ROL_AUXILIAR, "catalogo", False),
        (config.ROL_AUXILIAR, "reportes", False),
    ],
)
def test_la_matriz_de_permisos_por_rol(
    rol: str, permiso: str, esperado: bool
) -> None:
    assert config.puede(rol, permiso) is esperado


def test_registrar_movimiento_guarda_quien_lo_hizo() -> None:
    _, _, empleado = auth.autenticar("admin", "admin123")
    sesion_actual.iniciar(empleado)

    auth.registrar_movimiento("alta_libro", "libro", 99, "libro de prueba")

    with sesion() as db:
        movimiento = db.scalar(
            select(Movimiento).where(Movimiento.accion == "alta_libro")
        )

    assert movimiento is not None
    assert movimiento.entidad == "libro"
    assert movimiento.entidad_id == 99
    assert movimiento.empleado_id == empleado.id
