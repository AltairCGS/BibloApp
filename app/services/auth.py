"""Autenticación y registro de movimientos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Empleado, Movimiento
from app.security import verificar_password


class SesionActual:
    """Empleado logueado en esta ejecución de la app."""

    def __init__(self) -> None:
        self.empleado: Empleado | None = None

    @property
    def autenticado(self) -> bool:
        return self.empleado is not None

    @property
    def nombre(self) -> str:
        return self.empleado.nombre if self.empleado else ""

    @property
    def rol(self) -> str:
        return self.empleado.rol if self.empleado else ""

    @property
    def rol_legible(self) -> str:
        return config.ROLES.get(self.rol, self.rol)

    def puede(self, permiso: str) -> bool:
        return bool(self.empleado) and config.puede(self.rol, permiso)

    def iniciar(self, empleado: Empleado) -> None:
        self.empleado = empleado

    def cerrar(self) -> None:
        self.empleado = None


sesion_actual = SesionActual()


def autenticar(usuario: str, password: str) -> tuple[bool, str, Empleado | None]:
    """Valida credenciales.

    Devuelve (exito, mensaje, empleado).
    """
    usuario = (usuario or "").strip()
    if not usuario or not password:
        return False, "Ingresa tu usuario y contraseña.", None

    with sesion() as db:
        empleado = db.scalar(select(Empleado).where(Empleado.usuario == usuario))
        if empleado is None:
            return False, "Usuario o contraseña incorrectos.", None

        if not empleado.activo:
            return False, "La cuenta está deshabilitada. Contacta al administrador.", None

        if not verificar_password(password, empleado.pass_hash):
            return False, "Usuario o contraseña incorrectos.", None

        empleado.ultimo_acceso = datetime.now()
        db.add(
            Movimiento(
                empleado_id=empleado.id,
                accion="inicio_sesion",
                entidad="empleado",
                entidad_id=empleado.id,
                detalle=f"{empleado.usuario} inició sesión",
            )
        )
        db.flush()
        db.refresh(empleado)
        return True, "", empleado


def registrar_movimiento(
    accion: str, entidad: str, entidad_id: int | None = None, detalle: str | None = None
) -> None:
    """Deja rastro de una acción en la tabla de auditoría."""
    with sesion() as db:
        empleado_id = sesion_actual.empleado.id if sesion_actual.empleado else None
        db.add(
            Movimiento(
                empleado_id=empleado_id,
                accion=accion,
                entidad=entidad,
                entidad_id=entidad_id,
                detalle=detalle,
            )
        )
