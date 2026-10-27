"""Reglas de préstamo leídas de la tabla de configuración.

Los valores se pueden cambiar desde la pantalla de Configuración; si una
clave no existe o tiene basura, se usa el valor por defecto de `config`.
"""

from __future__ import annotations

from app import config
from app.db.database import sesion
from app.db.models import Configuracion


def _leer_entero(clave: str, por_defecto: int) -> int:
    with sesion() as db:
        fila = db.get(Configuracion, clave)

    if fila is None:
        return por_defecto

    try:
        return max(0, int(fila.valor))
    except (TypeError, ValueError):
        return por_defecto


def dias_prestamo(tipo: str) -> int:
    """Días de préstamo que corresponden a un tipo de socio."""
    por_defecto = config.DIAS_PRESTAMO.get(
        tipo, config.DIAS_PRESTAMO[config.TIPO_EXTERNO]
    )
    return _leer_entero(f"dias_prestamo_{tipo}", por_defecto)


def dias_gracia_bloqueo() -> int:
    """Días de atraso tolerados antes de bloquear al socio."""
    return _leer_entero("dias_gracia_bloqueo", config.DIAS_GRACIA_BLOQUEO)


def limite_ejemplares() -> int:
    """Cantidad de ejemplares que un socio puede tener a la vez."""
    return _leer_entero("limite_ejemplares_socio", config.LIMITE_EJEMPLARES_POR_SOCIO)


def dias_renovacion() -> int:
    """Días que suma cada renovación al vencimiento."""
    return _leer_entero("dias_renovacion", config.DIAS_RENOVACION)


def max_renovaciones() -> int:
    """Cantidad de renovaciones permitidas por préstamo."""
    return _leer_entero("max_renovaciones", config.MAX_RENOVACIONES)


def multa_perdida_centavos() -> int:
    """Monto sugerido de la multa por ejemplar perdido, en centavos."""
    return _leer_entero("multa_perdida_centavos", config.MULTA_PERDIDA_CENTAVOS)
