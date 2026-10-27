"""Datos iniciales de BibloApp.

Solo se ejecuta cuando la base está vacía. Crea:
  - Empleados de demostración (uno por rol).
  - Ubicaciones físicas de ejemplo.
  - Un catálogo mínimo de demostración.
  - Valores por defecto de configuración.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.db.models import (
    Configuracion,
    Ejemplar,
    Empleado,
    Libro,
    Ubicacion,
)
from app.security import hashear_password

# Usuarios de demostración: cambiar la contraseña antes de usar en producción.
EMPLEADOS_DEMO = [
    ("Administrador", "admin", "admin123", config.ROL_ADMIN),
    ("Bibliotecaria", "bibliotecario", "biblio123", config.ROL_BIBLIOTECARIO),
    ("Auxiliar", "auxiliar", "aux123", config.ROL_AUXILIAR),
]

UBICACIONES_DEMO = [
    # (sala, estanteria, baldas)
    ("Sala General", "A", 5),
    ("Sala General", "B", 5),
    ("Sala de Referencia", "R", 3),
    ("Sala Infantil", "I", 4),
]

LIBROS_DEMO = [
    {
        "titulo": "Cien años de soledad",
        "autores": "Gabriel García Márquez",
        "editorial": "Sudamericana",
        "anio": 1967,
        "categoria": "Novela",
        "dewey": "863",
        "isbn": "9780307474728",
        "sinopsis": ("La saga de la familia Buendía en el pueblo de Macondo, "
                     "obra central del realismo mágico latinoamericano."),
        "palabras_clave": "realismo magico, familia, macondo, colombia",
        "ejemplares": 3,
    },
    {
        "titulo": "El amor en los tiempos del cólera",
        "autores": "Gabriel García Márquez",
        "editorial": "Sudamericana",
        "anio": 1985,
        "categoria": "Novela",
        "dewey": "863",
        "isbn": "9780307387264",
        "sinopsis": ("La historia de un amor que espera más de medio siglo para "
                     "concretarse en una ciudad del Caribe."),
        "palabras_clave": "amor, espera, caribe, vejez",
        "ejemplares": 2,
    },
    {
        "titulo": "Ficciones",
        "autores": "Jorge Luis Borges",
        "editorial": "Sur",
        "anio": 1944,
        "categoria": "Cuento",
        "dewey": "863",
        "isbn": "9780802130303",
        "sinopsis": ("Colección de cuentos que fundaron la literatura fantástica "
                     "del siglo XX: laberintos, bibliotecas infinitas y espejos."),
        "palabras_clave": "cuento, laberinto, fantastico, argentina",
        "ejemplares": 2,
    },
    {
        "titulo": "Rayuela",
        "autores": "Julio Cortazar",
        "editorial": "Sudamericana",
        "anio": 1963,
        "categoria": "Novela",
        "dewey": "863",
        "isbn": "9788437604572",
        "sinopsis": ("Novela que puede leerse en dos órdenes distintos, con la "
                     "historia de Horacio Oliveira entre París y Buenos Aires."),
        "palabras_clave": "novela, paris, buenos aires, experimentacion",
        "ejemplares": 2,
    },
    {
        "titulo": "Pedro Páramo",
        "autores": "Juan Rulfo",
        "editorial": "Fondo de Cultura Económica",
        "anio": 1955,
        "categoria": "Novela",
        "dewey": "863",
        "isbn": "9788437604183",
        "sinopsis": ("El viaje de Juan Preciado a Comala, pueblo de voces y "
                     "fantasmas, en una de las obras clave del siglo XX."),
        "palabras_clave": "comala, fantasma, mexico, muerte",
        "ejemplares": 2,
    },
    {
        "titulo": "El principito",
        "autores": "Antoine de Saint-Exupéry",
        "editorial": "Salamandra",
        "anio": 1943,
        "categoria": "Infantil",
        "dewey": "843",
        "isbn": "9788478887194",
        "sinopsis": ("Un piloto perdido en el desierto conoce a un pequeño "
                     "príncipe que viene de otro planeta."),
        "palabras_clave": "infantil, amistad, desierto, clasico",
        "ejemplares": 4,
    },
]

CONFIG_INICIAL = {
    "dias_prestamo_estudiante": str(config.DIAS_PRESTAMO[config.TIPO_ESTUDIANTE]),
    "dias_prestamo_docente": str(config.DIAS_PRESTAMO[config.TIPO_DOCENTE]),
    "dias_prestamo_externo": str(config.DIAS_PRESTAMO[config.TIPO_EXTERNO]),
    "limite_ejemplares_socio": str(config.LIMITE_EJEMPLARES_POR_SOCIO),
    "dias_gracia_bloqueo": str(config.DIAS_GRACIA_BLOQUEO),
    "dias_renovacion": str(config.DIAS_RENOVACION),
    "max_renovaciones": str(config.MAX_RENOVACIONES),
    "multa_perdida_centavos": str(config.MULTA_PERDIDA_CENTAVOS),
}


def _sembrar_empleados(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Empleado)):
        return

    for nombre, usuario, password, rol in EMPLEADOS_DEMO:
        db.add(
            Empleado(
                nombre=nombre,
                usuario=usuario,
                pass_hash=hashear_password(password),
                rol=rol,
                activo=True,
            )
        )


def _sembrar_ubicaciones(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Ubicacion)):
        return

    for sala, estanteria, baldas in UBICACIONES_DEMO:
        for balda in range(1, baldas + 1):
            codigo = f"{estanteria}-{balda:02d}"
            db.add(
                Ubicacion(
                    codigo=codigo,
                    sala=sala,
                    estanteria=estanteria,
                    balda=str(balda),
                    referencia=f"{sala}, estanteria {estanteria}, balda {balda}",
                )
            )


def _sembrar_libros(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Libro)):
        return

    ubicaciones = list(db.scalars(select(Ubicacion).order_by(Ubicacion.codigo)))
    if not ubicaciones:
        return

    correlativo = 1
    for i, datos in enumerate(LIBROS_DEMO):
        libro = Libro(
            titulo=datos["titulo"],
            autores=datos["autores"],
            editorial=datos["editorial"],
            anio=datos["anio"],
            categoria=datos["categoria"],
            dewey=datos["dewey"],
            isbn=datos["isbn"],
            sinopsis=datos["sinopsis"],
            palabras_clave=datos["palabras_clave"],
        )
        db.add(libro)
        db.flush()

        for _ in range(datos["ejemplares"]):
            db.add(
                Ejemplar(
                    libro_id=libro.id,
                    codigo_inventario=f"EJ-{correlativo:05d}",
                    estado=config.EJEMPLAR_DISPONIBLE,
                    ubicacion_id=ubicaciones[i % len(ubicaciones)].id,
                    condicion="bueno",
                )
            )
            correlativo += 1


def _sembrar_configuracion(db: Session) -> None:
    existentes = {c.clave for c in db.scalars(select(Configuracion))}
    for clave, valor in CONFIG_INICIAL.items():
        if clave not in existentes:
            db.add(Configuracion(clave=clave, valor=valor))


def sembrar_datos_iniciales(db: Session) -> bool:
    """Carga los datos iniciales. Devuelve True si creo algo."""
    vacia = not db.scalar(select(func.count()).select_from(Empleado))
    _sembrar_empleados(db)
    _sembrar_ubicaciones(db)
    _sembrar_libros(db)
    _sembrar_configuracion(db)
    return vacia
