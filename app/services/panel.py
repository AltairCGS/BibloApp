"""Consultas de lectura para las pantallas."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app import config
from app.db.database import sesion
from app.db.models import Ejemplar, Libro, Prestamo, Socio, Ubicacion


def resumen_panel() -> dict[str, int]:
    """Contadores que alimentan las tarjetas del panel principal."""
    hoy = date.today()
    with sesion() as db:
        return {
            "libros": db.scalar(select(func.count()).select_from(Libro)) or 0,
            "ejemplares": db.scalar(select(func.count()).select_from(Ejemplar)) or 0,
            "disponibles": db.scalar(
                select(func.count())
                .select_from(Ejemplar)
                .where(Ejemplar.estado == config.EJEMPLAR_DISPONIBLE)
            )
            or 0,
            "prestamos_activos": db.scalar(
                select(func.count())
                .select_from(Prestamo)
                .where(Prestamo.estado == config.PRESTAMO_ACTIVO)
            )
            or 0,
            "vencidos": db.scalar(
                select(func.count())
                .select_from(Prestamo)
                .where(
                    Prestamo.estado == config.PRESTAMO_ACTIVO,
                    Prestamo.fecha_vencimiento < hoy,
                )
            )
            or 0,
            "socios_activos": db.scalar(
                select(func.count())
                .select_from(Socio)
                .where(Socio.estado == config.SOCIO_ACTIVO)
            )
            or 0,
        }


def prestamos_activos(limite: int = 100) -> list[dict]:
    """Préstamos sin devolver, con los datos que se muestran en la tabla."""
    hoy = date.today()
    with sesion() as db:
        filas = db.execute(
            select(Prestamo, Ejemplar, Libro, Socio, Ubicacion)
            .join(Ejemplar, Prestamo.ejemplar_id == Ejemplar.id)
            .join(Libro, Ejemplar.libro_id == Libro.id)
            .join(Socio, Prestamo.socio_id == Socio.id)
            .outerjoin(Ubicacion, Ejemplar.ubicacion_id == Ubicacion.id)
            .where(Prestamo.estado == config.PRESTAMO_ACTIVO)
            .order_by(Prestamo.fecha_vencimiento)
            .limit(limite)
        ).all()

        resultado = []
        for prestamo, ejemplar, libro, socio, ubicacion in filas:
            atraso = max(0, (hoy - prestamo.fecha_vencimiento).days)
            resultado.append(
                {
                    "id": prestamo.id,
                    "ejemplar": ejemplar.codigo_inventario,
                    "libro": libro.titulo,
                    "socio": socio.nombre,
                    "documento": socio.documento,
                    "vence": prestamo.fecha_vencimiento,
                    "dias_atraso": atraso,
                    "estado": "vencido" if atraso > 0 else "activo",
                    "ubicacion": ubicacion.codigo if ubicacion else "",
                }
            )
        return resultado
