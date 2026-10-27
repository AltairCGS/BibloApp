"""Servicio de multas: deudas de los socios y registro de pagos.

Las multas se generan al marcar un ejemplar como perdido. Una multa
pendiente bloquea nuevas salidas del socio (lo consulta `socios.situacion`);
al pagarse o anularse, el bloqueo desaparece.

El monto se guarda en centavos y se muestra con formato de pesos.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Ejemplar, Libro, Multa, Prestamo, Socio
from app.services import permisos


# --------------------------------------------------------------------- lectura
def formatear_monto(centavos: int) -> str:
    """Devuelve el monto con formato $ 10.000,00."""
    valor = int(centavos or 0)
    signo = "-" if valor < 0 else ""
    entero, resto = divmod(abs(valor), 100)
    miles = f"{entero:,}".replace(",", ".")
    return f"{signo}$ {miles},{resto:02d}"


def listar_multas(
    socio_id: int | None = None,
    estado: str | None = None,
    prestamo_id: int | None = None,
) -> list[dict]:
    """Multas registradas, con los datos que muestra la ficha del socio.

    Las pendientes van primero; dentro de cada estado, las más recientes.
    """
    consulta = (
        select(Multa, Socio, Prestamo, Ejemplar, Libro)
        .join(Socio, Multa.socio_id == Socio.id)
        .outerjoin(Prestamo, Multa.prestamo_id == Prestamo.id)
        .outerjoin(Ejemplar, Prestamo.ejemplar_id == Ejemplar.id)
        .outerjoin(Libro, Ejemplar.libro_id == Libro.id)
        .order_by(
            (Multa.estado == config.MULTA_PENDIENTE).desc(),
            Multa.fecha.desc(),
            Multa.id.desc(),
        )
    )

    if socio_id is not None:
        consulta = consulta.where(Multa.socio_id == socio_id)
    if prestamo_id is not None:
        consulta = consulta.where(Multa.prestamo_id == prestamo_id)
    if estado:
        consulta = consulta.where(Multa.estado == estado)

    with sesion() as db:
        filas = db.execute(consulta).all()

    return [_armar(multa, socio, prestamo, ejemplar, libro)
            for multa, socio, prestamo, ejemplar, libro in filas]


def deuda_pendiente(socio_id: int) -> dict:
    """Cantidad y total de las multas pendientes de un socio."""
    with sesion() as db:
        montos = db.scalars(
            select(Multa.monto_centavos).where(
                Multa.socio_id == socio_id,
                Multa.estado == config.MULTA_PENDIENTE,
            )
        ).all()

    total = sum(montos)
    return {
        "cantidad": len(montos),
        "total_centavos": total,
        "total": formatear_monto(total),
    }


# -------------------------------------------------------------------- escritura
def registrar_pago(multa_id: int, notas: str = "") -> tuple[bool, str]:
    """Marca una multa pendiente como pagada, con la fecha de hoy."""
    if not permisos.puede("socios"):
        return False, permisos.SIN_PERMISO

    with sesion() as db:
        multa = db.get(Multa, multa_id)
        if multa is None:
            return False, "La multa ya no existe."

        if multa.estado == config.MULTA_PAGADA:
            return False, "Esta multa ya figura como pagada."
        if multa.estado == config.MULTA_ANULADA:
            return False, "Esta multa está anulada: no se puede cobrar."

        multa.estado = config.MULTA_PAGADA
        multa.fecha_pago = date.today()
        _agregar_nota(multa, notas)
        return True, ""


def anular_multa(multa_id: int, motivo: str = "") -> tuple[bool, str]:
    """Anula una multa pendiente (por ejemplo, si el ejemplar apareció)."""
    if not permisos.puede("socios"):
        return False, permisos.SIN_PERMISO

    with sesion() as db:
        multa = db.get(Multa, multa_id)
        if multa is None:
            return False, "La multa ya no existe."

        if multa.estado == config.MULTA_PAGADA:
            return False, "Esta multa ya fue pagada: no se puede anular."
        if multa.estado == config.MULTA_ANULADA:
            return False, "Esta multa ya figura como anulada."

        multa.estado = config.MULTA_ANULADA
        _agregar_nota(multa, motivo)
        return True, ""


# -------------------------------------------------------------------- internos
def _armar(
    multa: Multa,
    socio: Socio,
    prestamo: Prestamo | None,
    ejemplar: Ejemplar | None,
    libro: Libro | None,
) -> dict:
    return {
        "id": multa.id,
        "socio_id": socio.id,
        "socio": socio.nombre,
        "documento": socio.documento,
        "prestamo_id": prestamo.id if prestamo is not None else None,
        "concepto": multa.concepto,
        "monto_centavos": multa.monto_centavos,
        "monto": formatear_monto(multa.monto_centavos),
        "estado": multa.estado,
        "estado_legible": config.ESTADOS_MULTA.get(multa.estado, multa.estado),
        "fecha": multa.fecha,
        "fecha_pago": multa.fecha_pago,
        "notas": multa.notas or "",
        "ejemplar": ejemplar.codigo_inventario if ejemplar is not None else "",
        "libro": libro.titulo if libro is not None else "",
    }


def _agregar_nota(multa: Multa, nota: str) -> None:
    texto = (nota or "").strip()
    if not texto:
        return
    multa.notas = f"{multa.notas}\n{texto}" if multa.notas else texto
