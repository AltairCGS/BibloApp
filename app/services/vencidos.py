"""Servicio de vencidos: préstamos fuera de plazo y recordatorios.

Un préstamo está vencido cuando sigue abierto (sin fecha de devolución) y su
fecha de vencimiento ya pasó. Es el mismo criterio que usa el filtro
«Vencidos» de Préstamos: un ejemplar perdido o recuperado ya está cerrado y
no aparece en este listado.

La exportación CSV es la herramienta de trabajo del módulo: genera una fila
por préstamo con los datos de contacto del socio para enviar recordatorios.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app import config
from app.db.database import sesion
from app.db.models import Ejemplar, Libro, Prestamo, Socio
from app.services import permisos, reglas
from app.services.auth import registrar_movimiento
from app.services.texto import normalizar

ENCABEZADOS = [
    "Documento",
    "Socio",
    "Teléfono",
    "Correo",
    "Ejemplar",
    "Libro",
    "Prestado",
    "Vence",
    "Días de atraso",
]


# --------------------------------------------------------------------- lectura
def listar_vencidos(
    busqueda: str = "",
    solo_fuera_de_gracia: bool = False,
) -> list[dict]:
    """Préstamos abiertos con el vencimiento anterior a hoy.

    Orden: el más atrasado primero. La búsqueda ignora tildes y mayúsculas y
    mira el socio, su documento y contacto, el libro, sus autores y el código
    del ejemplar.
    """
    hoy = date.today()
    consulta = (
        select(Prestamo, Ejemplar, Libro, Socio)
        .join(Ejemplar, Prestamo.ejemplar_id == Ejemplar.id)
        .join(Libro, Ejemplar.libro_id == Libro.id)
        .join(Socio, Prestamo.socio_id == Socio.id)
        .where(
            Prestamo.fecha_devolucion.is_(None),
            Prestamo.fecha_vencimiento < hoy,
        )
        .order_by(Prestamo.fecha_vencimiento, Prestamo.id)
    )

    with sesion() as db:
        filas = db.execute(consulta).all()

    gracia = reglas.dias_gracia_bloqueo()
    termino = normalizar(busqueda)
    resultado: list[dict] = []

    for prestamo, ejemplar, libro, socio in filas:
        if termino:
            campos = " ".join(
                [
                    socio.nombre or "",
                    socio.documento or "",
                    socio.telefono or "",
                    socio.email or "",
                    libro.titulo or "",
                    libro.autores or "",
                    ejemplar.codigo_inventario or "",
                ]
            )
            if termino not in normalizar(campos):
                continue

        atraso = max(0, (hoy - prestamo.fecha_vencimiento).days)
        en_gracia = atraso <= gracia
        if solo_fuera_de_gracia and en_gracia:
            continue

        resultado.append(
            {
                "id": prestamo.id,
                "prestamo_id": prestamo.id,
                "socio_id": socio.id,
                "socio": socio.nombre,
                "documento": socio.documento,
                "email": socio.email or "",
                "telefono": socio.telefono or "",
                "tipo": socio.tipo,
                "tipo_socio": config.TIPOS_SOCIO.get(socio.tipo, socio.tipo),
                "socio_estado": socio.estado,
                "libro": libro.titulo,
                "autores": libro.autores or "",
                "ejemplar": ejemplar.codigo_inventario,
                "ejemplar_id": ejemplar.id,
                "desde": prestamo.fecha_prestamo,
                "vence": prestamo.fecha_vencimiento,
                "atraso": atraso,
                "dias_atraso": atraso,
                "en_gracia": en_gracia,
                "renovaciones": prestamo.renovaciones,
                "notas": prestamo.notas or "",
            }
        )

    return resultado


def resumen(
    busqueda: str = "",
    solo_fuera_de_gracia: bool = False,
) -> dict[str, int]:
    """Contadores del pie del listado, con los mismos filtros de la tabla."""
    filas = listar_vencidos(busqueda, solo_fuera_de_gracia)
    return {
        "total": len(filas),
        "socios": len({fila["socio_id"] for fila in filas}),
        "maximo_atraso": max((fila["atraso"] for fila in filas), default=0),
        "fuera_de_gracia": sum(1 for fila in filas if not fila["en_gracia"]),
    }


# -------------------------------------------------------------------- escritura
def exportar_csv(
    ruta: str,
    busqueda: str = "",
    solo_fuera_de_gracia: bool = False,
) -> tuple[bool, str]:
    """Escribe los recordatorios en un CSV que Excel abre sin ajustes.

    Usa BOM (`utf-8-sig`), separador `;` y fechas `dd/mm/aaaa`: la
    combinación que Excel en español interpreta sin pedir importación.
    """
    if not permisos.puede("vencidos"):
        return False, permisos.SIN_PERMISO

    filas = listar_vencidos(busqueda, solo_fuera_de_gracia)
    if not filas:
        return False, "No hay préstamos vencidos para exportar."

    try:
        with open(ruta, "w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.writer(archivo, delimiter=";", lineterminator="\r\n")
            escritor.writerow(ENCABEZADOS)
            for fila in filas:
                escritor.writerow(
                    [
                        fila["documento"],
                        fila["socio"],
                        fila["telefono"],
                        fila["email"],
                        fila["ejemplar"],
                        fila["libro"],
                        f"{fila['desde']:%d/%m/%Y}",
                        f"{fila['vence']:%d/%m/%Y}",
                        fila["dias_atraso"],
                    ]
                )
    except OSError as error:
        return False, f"No se pudo escribir el archivo: {error}"

    cantidad = len(filas)
    detalle = (
        f"{cantidad} préstamo vencido"
        if cantidad == 1
        else f"{cantidad} préstamos vencidos"
    )
    detalle += f" exportado{'s' if cantidad != 1 else ''} a {Path(ruta).name}"
    if solo_fuera_de_gracia:
        detalle += " (solo fuera del plazo de gracia)"

    registrar_movimiento("recordatorio", "vencidos", None, detalle)
    return True, ""
