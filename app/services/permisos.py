"""Comprobación de permisos dentro de los servicios.

La interfaz ya oculta los módulos que el rol no puede usar, pero eso es
comodidad visual: no es una barrera. Un servicio que escribe datos vuelve
a preguntar quién lo está llamando, así un error de la interfaz (o una
llamada desde un script) no termina modificando la base.

Solo se protegen las operaciones de escritura. Las lecturas quedan
abiertas a propósito: el auxiliar no administra el catálogo, pero sí
necesita consultarlo para registrar un préstamo.
"""

from __future__ import annotations

from app.services.auth import sesion_actual

SIN_PERMISO = "No tenés permiso para realizar esta acción."


def puede(permiso: str) -> bool:
    """Indica si la sesión activa tiene el permiso indicado."""
    return sesion_actual.puede(permiso)
