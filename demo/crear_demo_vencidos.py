"""Crea una base de demostración con préstamos vencidos para probar Vencidos.

Uso:
    .venv\\Scripts\\python.exe demo\\crear_demo_vencidos.py

Genera `demo/vencidos_demo.db`. No toca `data/biblioteca.db`.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

DEMO = Path(__file__).resolve().parent
RAIZ = DEMO.parent
DB = DEMO / "vencidos_demo.db"

# Debe quedar definido antes de importar app.
os.environ["BIBLOAPP_DB"] = str(DB)
sys.path.insert(0, str(RAIZ))

from sqlalchemy import select  # noqa: E402

from app import config  # noqa: E402
from app.db.database import init_db, sesion  # noqa: E402
from app.db.importar import cargar_json, importar  # noqa: E402
from app.db.models import Ejemplar, Prestamo, Socio  # noqa: E402
from app.db.seed import sembrar_datos_iniciales  # noqa: E402
from app.services import reglas  # noqa: E402

CATALOGO = RAIZ / "datos" / "catalogo_ejemplo.json"
ATRASOS = [45, 30, 23, 12, 7, 5, 3, 1]

# Socios de ficción: correos en example.com y teléfonos de la serie 555-01xx,
# reservados para ejemplos y documentación.
SOCIOS = [
    {
        "nombre": "Lucía Fernández",
        "documento": "30000001",
        "email": "lucia.fernandez@example.com",
        "telefono": "555-0101",
        "direccion": "Av. del Parque 100",
        "tipo": config.TIPO_ESTUDIANTE,
    },
    {
        "nombre": "Andrés Gómez",
        "documento": "30000002",
        "email": "andres.gomez@example.com",
        "telefono": "555-0102",
        "direccion": "Calle Rivadavia 210",
        "tipo": config.TIPO_DOCENTE,
    },
    {
        "nombre": "María José Peña",
        "documento": "30000003",
        "email": "maria.pena@example.com",
        "telefono": "555-0103",
        "direccion": "Av. San Martín 320",
        "tipo": config.TIPO_EXTERNO,
    },
    {
        "nombre": "Julián Ramírez",
        "documento": "30000004",
        "email": "julian.ramirez@example.com",
        "telefono": "555-0104",
        "direccion": "Calle Mitre 430",
        "tipo": config.TIPO_ESTUDIANTE,
    },
    {
        "nombre": "Valentina Suárez",
        "documento": "30000005",
        "email": "valentina.suarez@example.com",
        "telefono": "555-0105",
        "direccion": "Av. Belgrano 540",
        "tipo": config.TIPO_DOCENTE,
    },
    {
        "nombre": "Matías Castro",
        "documento": "30000006",
        "email": "matias.castro@example.com",
        "telefono": "555-0106",
        "direccion": "Calle Sarmiento 650",
        "tipo": config.TIPO_EXTERNO,
    },
    {
        "nombre": "Camila Ortega",
        "documento": "30000007",
        "email": "camila.ortega@example.com",
        "telefono": "555-0107",
        "direccion": "Av. Libertad 760",
        "tipo": config.TIPO_ESTUDIANTE,
    },
    {
        "nombre": "Tomás Moretti",
        "documento": "30000008",
        "email": None,
        "telefono": None,
        "direccion": "Calle Moreno 870",
        "tipo": config.TIPO_EXTERNO,
    },
]


def crear() -> None:
    if DB.exists():
        try:
            DB.unlink()
        except OSError as error:
            raise SystemExit(
                "No se pudo reemplazar la base de demostración. "
                f"¿Está abierta la app de demo? Detalle: {error}"
            ) from error

    init_db()
    with sesion() as db:
        sembrar_datos_iniciales(db)

    datos = cargar_json(CATALOGO)
    resumen = importar(datos, reemplazar=True)

    hoy = date.today()
    dias_por_tipo = {tipo: reglas.dias_prestamo(tipo) for tipo in config.TIPOS_SOCIO}

    with sesion() as db:
        for datos in SOCIOS:
            db.add(
                Socio(
                    nombre=datos["nombre"],
                    documento=datos["documento"],
                    email=datos["email"],
                    telefono=datos["telefono"],
                    direccion=datos["direccion"],
                    tipo=datos["tipo"],
                    estado=config.SOCIO_ACTIVO,
                )
            )
        db.flush()

        socios = list(
            db.scalars(
                select(Socio)
                .where(Socio.estado == config.SOCIO_ACTIVO)
                .order_by(Socio.documento)
            )
        )
        ejemplares = list(
            db.scalars(select(Ejemplar).order_by(Ejemplar.codigo_inventario))
        )
        assert len(socios) == 8, "la demo debe crear 8 socios"
        assert len(ejemplares) >= 102, "el catálogo de ejemplo debe traer ejemplares"

        elegidos = [ejemplares[i] for i in (0, 13, 27, 40, 55, 68, 81, 94)]
        for socio, ejemplar, atraso in zip(socios, elegidos, ATRASOS):
            vence = hoy - timedelta(days=atraso)
            inicio = vence - timedelta(days=dias_por_tipo.get(socio.tipo, 7))
            db.add(
                Prestamo(
                    ejemplar_id=ejemplar.id,
                    socio_id=socio.id,
                    fecha_prestamo=inicio,
                    fecha_vencimiento=vence,
                    fecha_devolucion=None,
                    estado=config.PRESTAMO_ACTIVO,
                    renovaciones=0,
                )
            )
            ejemplar.estado = config.EJEMPLAR_PRESTADO

        # Un devuelto y un activo al día: no deben aparecer en Vencidos.
        db.add(
            Prestamo(
                ejemplar_id=ejemplares[100].id,
                socio_id=socios[0].id,
                fecha_prestamo=hoy - timedelta(days=20),
                fecha_vencimiento=hoy - timedelta(days=5),
                fecha_devolucion=hoy - timedelta(days=1),
                estado=config.PRESTAMO_DEVUELTO,
            )
        )
        db.add(
            Prestamo(
                ejemplar_id=ejemplares[101].id,
                socio_id=socios[1].id,
                fecha_prestamo=hoy,
                fecha_vencimiento=hoy + timedelta(days=7),
                estado=config.PRESTAMO_ACTIVO,
            )
        )
        ejemplares[101].estado = config.EJEMPLAR_PRESTADO

    print("Base de demostración creada:", DB)
    print(
        "Catálogo importado:",
        resumen["libros"],
        "libros,",
        resumen["ejemplares"],
        "ejemplares,",
        len(SOCIOS),
        "socios.",
    )
    print("Préstamos vencidos de ejemplo:", len(ATRASOS))
    print("Atrasos en días:", ", ".join(str(d) for d in ATRASOS))
    print("Fuera del plazo de gracia (3 días):", sum(1 for d in ATRASOS if d > 3))


if __name__ == "__main__":
    crear()
