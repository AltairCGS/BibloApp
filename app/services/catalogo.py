"""Servicio de catalogo: libros, ejemplares y ubicaciones."""

from __future__ import annotations

from sqlalchemy import case, func, select

from app import config
from app.db.database import sesion
from app.db.models import Ejemplar, Libro, Prestamo, Ubicacion
from app.services import permisos
from app.services.texto import normalizar


# --------------------------------------------------------------------- lectura
def listar_libros(
    busqueda: str = "",
    categoria: str | None = None,
    solo_disponibles: bool = False,
) -> list[dict]:
    """Lista de libros con conteo de ejemplares.

    La busqueda ignora tildes y mayusculas, y mira titulo, autores, ISBN,
    editorial, categoria y palabras clave.
    """
    consulta = (
        select(
            Libro,
            func.count(Ejemplar.id).label("total"),
            func.coalesce(
                func.sum(
                    case((Ejemplar.estado == config.EJEMPLAR_DISPONIBLE, 1), else_=0)
                ),
                0,
            ).label("disponibles"),
        )
        .outerjoin(Ejemplar, Ejemplar.libro_id == Libro.id)
        .group_by(Libro.id)
        .order_by(Libro.titulo)
    )

    if categoria:
        consulta = consulta.where(Libro.categoria == categoria)

    with sesion() as db:
        filas = db.execute(consulta).all()

    termino = normalizar(busqueda)
    resultado: list[dict] = []

    for libro, total, disponibles in filas:
        if termino:
            campos = " ".join(
                [
                    libro.titulo or "",
                    libro.subtitulo or "",
                    libro.autores or "",
                    libro.isbn or "",
                    libro.editorial or "",
                    libro.categoria or "",
                    libro.palabras_clave or "",
                ]
            )
            if termino not in normalizar(campos):
                continue

        if solo_disponibles and disponibles == 0:
            continue

        resultado.append(
            {
                "id": libro.id,
                "titulo": libro.titulo,
                "autores": libro.autores,
                "categoria": libro.categoria or "",
                "anio": libro.anio,
                "isbn": libro.isbn or "",
                "ejemplares": total,
                "disponibles": disponibles,
            }
        )

    return resultado


def obtener_libro(libro_id: int) -> dict | None:
    """Ficha completa de un libro con sus ejemplares y ubicaciones."""
    with sesion() as db:
        libro = db.get(Libro, libro_id)
        if libro is None:
            return None

        ejemplares = db.execute(
            select(Ejemplar, Ubicacion)
            .outerjoin(Ubicacion, Ejemplar.ubicacion_id == Ubicacion.id)
            .where(Ejemplar.libro_id == libro_id)
            .order_by(Ejemplar.codigo_inventario)
        ).all()

        return {
            "id": libro.id,
            "titulo": libro.titulo,
            "subtitulo": libro.subtitulo or "",
            "autores": libro.autores or "",
            "isbn": libro.isbn or "",
            "editorial": libro.editorial or "",
            "anio": libro.anio,
            "idioma": libro.idioma or "es",
            "categoria": libro.categoria or "",
            "dewey": libro.dewey or "",
            "sinopsis": libro.sinopsis or "",
            "palabras_clave": libro.palabras_clave or "",
            "ejemplares": [
                {
                    "id": ejemplar.id,
                    "codigo": ejemplar.codigo_inventario,
                    "estado": ejemplar.estado,
                    "condicion": ejemplar.condicion,
                    "notas": ejemplar.notas or "",
                    "ubicacion": ubicacion.codigo if ubicacion else "",
                    "ubicacion_detalle": ubicacion.descripcion if ubicacion else "Sin ubicar",
                }
                for ejemplar, ubicacion in ejemplares
            ],
        }


def listar_ubicaciones() -> list[dict]:
    with sesion() as db:
        filas = db.scalars(select(Ubicacion).order_by(Ubicacion.codigo)).all()
        return [
            {"id": u.id, "codigo": u.codigo, "detalle": u.descripcion} for u in filas
        ]


def listar_categorias() -> list[str]:
    return list(config.CATEGORIAS)


def siguiente_codigo_inventario() -> str:
    """Sugiere el proximo codigo correlativo EJ-00001."""
    with sesion() as db:
        codigos = db.scalars(select(Ejemplar.codigo_inventario)).all()

    mayor = 0
    for codigo in codigos:
        if codigo.startswith("EJ-"):
            try:
                mayor = max(mayor, int(codigo[3:]))
            except ValueError:
                continue
    return f"EJ-{mayor + 1:05d}"


# ------------------------------------------------------------------- escritura
def crear_libro(datos: dict) -> tuple[bool, str, int | None]:
    if not permisos.puede("catalogo"):
        return False, permisos.SIN_PERMISO, None

    titulo = (datos.get("titulo") or "").strip()
    if not titulo:
        return False, "El título es obligatorio.", None

    with sesion() as db:
        libro = Libro(**_limpiar_datos_libro(datos))
        db.add(libro)
        db.flush()
        return True, "", libro.id


def actualizar_libro(libro_id: int, datos: dict) -> tuple[bool, str]:
    if not permisos.puede("catalogo"):
        return False, permisos.SIN_PERMISO

    titulo = (datos.get("titulo") or "").strip()
    if not titulo:
        return False, "El título es obligatorio."

    with sesion() as db:
        libro = db.get(Libro, libro_id)
        if libro is None:
            return False, "El libro ya no existe."

        for campo, valor in _limpiar_datos_libro(datos).items():
            setattr(libro, campo, valor)
        return True, ""


def eliminar_libro(libro_id: int) -> tuple[bool, str]:
    """Solo permite borrar si el libro no tiene prestamos registrados."""
    if not permisos.puede("catalogo"):
        return False, permisos.SIN_PERMISO

    with sesion() as db:
        libro = db.get(Libro, libro_id)
        if libro is None:
            return False, "El libro ya no existe."

        conteo = db.scalar(
            select(func.count())
            .select_from(Prestamo)
            .join(Ejemplar, Prestamo.ejemplar_id == Ejemplar.id)
            .where(Ejemplar.libro_id == libro_id)
        )
        if conteo:
            return False, (
                "No se puede eliminar: el libro tiene préstamos registrados. "
                "Para retirarlo de circulación, dá de baja sus ejemplares."
            )

        db.delete(libro)
        return True, ""


def agregar_ejemplar(libro_id: int, datos: dict) -> tuple[bool, str, int | None]:
    if not permisos.puede("catalogo"):
        return False, permisos.SIN_PERMISO, None

    codigo = (datos.get("codigo_inventario") or "").strip().upper()
    if not codigo:
        return False, "El código de inventario es obligatorio.", None

    with sesion() as db:
        if db.get(Libro, libro_id) is None:
            return False, "El libro ya no existe.", None

        existe = db.scalar(
            select(func.count())
            .select_from(Ejemplar)
            .where(Ejemplar.codigo_inventario == codigo)
        )
        if existe:
            return False, f"Ya existe un ejemplar con el código {codigo}.", None

        ejemplar = Ejemplar(
            libro_id=libro_id,
            codigo_inventario=codigo,
            estado=datos.get("estado") or config.EJEMPLAR_DISPONIBLE,
            ubicacion_id=datos.get("ubicacion_id"),
            condicion=datos.get("condicion") or "bueno",
            notas=(datos.get("notas") or "").strip() or None,
        )
        db.add(ejemplar)
        db.flush()
        return True, "", ejemplar.id


def actualizar_ejemplar(ejemplar_id: int, datos: dict) -> tuple[bool, str]:
    if not permisos.puede("catalogo"):
        return False, permisos.SIN_PERMISO

    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        if ejemplar is None:
            return False, "El ejemplar ya no existe."

        nuevo_codigo = (datos.get("codigo_inventario") or "").strip().upper()
        if not nuevo_codigo:
            return False, "El código de inventario es obligatorio."

        if nuevo_codigo != ejemplar.codigo_inventario:
            repetido = db.scalar(
                select(func.count())
                .select_from(Ejemplar)
                .where(Ejemplar.codigo_inventario == nuevo_codigo)
            )
            if repetido:
                return False, f"Ya existe un ejemplar con el código {nuevo_codigo}."
            ejemplar.codigo_inventario = nuevo_codigo

        ejemplar.ubicacion_id = datos.get("ubicacion_id")
        ejemplar.condicion = datos.get("condicion") or ejemplar.condicion
        ejemplar.notas = (datos.get("notas") or "").strip() or None

        # El estado "prestado" lo controla el modulo de prestamos.
        nuevo_estado = datos.get("estado")
        if nuevo_estado and ejemplar.estado != config.EJEMPLAR_PRESTADO:
            ejemplar.estado = nuevo_estado

        return True, ""


def eliminar_ejemplar(ejemplar_id: int) -> tuple[bool, str]:
    if not permisos.puede("catalogo"):
        return False, permisos.SIN_PERMISO

    with sesion() as db:
        ejemplar = db.get(Ejemplar, ejemplar_id)
        if ejemplar is None:
            return False, "El ejemplar ya no existe."

        if ejemplar.estado == config.EJEMPLAR_PRESTADO:
            return False, "No se puede eliminar un ejemplar que está prestado."

        conteo = db.scalar(
            select(func.count())
            .select_from(Prestamo)
            .where(Prestamo.ejemplar_id == ejemplar_id)
        )
        if conteo:
            return False, (
                "No se puede eliminar: el ejemplar tiene historial de préstamos. "
                "Márcalo como dado de baja."
            )

        db.delete(ejemplar)
        return True, ""


def estadisticas() -> dict[str, int]:
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
        }


# -------------------------------------------------------------------- internos
def _limpiar_datos_libro(datos: dict) -> dict:
    """Normaliza el diccionario que llega del formulario."""

    def texto(clave: str) -> str | None:
        valor = (datos.get(clave) or "").strip()
        return valor or None

    anio = datos.get("anio")
    if isinstance(anio, int) and anio <= 0:
        anio = None

    return {
        "titulo": (datos.get("titulo") or "").strip(),
        "subtitulo": texto("subtitulo"),
        "autores": (datos.get("autores") or "").strip(),
        "isbn": texto("isbn"),
        "editorial": texto("editorial"),
        "anio": anio,
        "idioma": datos.get("idioma") or "es",
        "categoria": texto("categoria"),
        "dewey": texto("dewey"),
        "sinopsis": texto("sinopsis"),
        "palabras_clave": texto("palabras_clave"),
    }
