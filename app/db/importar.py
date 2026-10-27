"""Importa un catalogo en JSON a la base de datos de BibloApp.

Uso:
    python -m app.db.importar datos/catalogo_ejemplo.json
    python -m app.db.importar datos/catalogo_ejemplo.json --reemplazar

El formato esperado es el de datos/catalogo_ejemplo.json:
    { "libros": [...], "socios": [...] }

La clave "socios" es opcional: el catálogo de ejemplo solo trae libros.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

from app import config
from app.db.database import init_db, sesion
from app.db.models import Ejemplar, Libro, Prestamo, Socio, Ubicacion


def cargar_json(ruta: Path) -> dict:
    if not ruta.exists():
        raise SystemExit(f"No existe el archivo: {ruta}")

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if "libros" not in datos:
        raise SystemExit("El JSON no tiene la clave 'libros'.")
    return datos


def reemplazar_catalogo() -> None:
    """Borra libros y ejemplares. Se niega si hay prestamos registrados."""
    with sesion() as db:
        prestamos = db.scalar(select(func.count()).select_from(Prestamo)) or 0
        if prestamos:
            raise SystemExit(
                f"Hay {prestamos} prestamo(s) registrados. "
                "No se puede reemplazar el catalogo sin perder ese historial."
            )
        db.execute(delete(Ejemplar))
        db.execute(delete(Libro))


def siguiente_numero(db) -> int:
    codigos = db.scalars(select(Ejemplar.codigo_inventario)).all()
    mayor = 0
    for codigo in codigos:
        if codigo.startswith("EJ-"):
            try:
                mayor = max(mayor, int(codigo[3:]))
            except ValueError:
                continue
    return mayor + 1


def importar(datos: dict, reemplazar: bool = False) -> dict:
    init_db()

    if reemplazar:
        reemplazar_catalogo()

    creados_libros = 0
    creados_ejemplares = 0
    creados_socios = 0
    omitidos = 0

    with sesion() as db:
        ubicaciones = list(db.scalars(select(Ubicacion).order_by(Ubicacion.codigo)))
        if not ubicaciones:
            raise SystemExit(
                "No hay ubicaciones cargadas. Ejecuta la app una vez para sembrarlas."
            )

        existentes = {
            (libro.titulo or "").strip().lower()
            for libro in db.scalars(select(Libro))
        }

        correlativo = siguiente_numero(db)
        indice_ubicacion = 0

        for entrada in datos["libros"]:
            titulo = (entrada.get("titulo") or "").strip()
            if not titulo:
                omitidos += 1
                continue

            if titulo.lower() in existentes:
                omitidos += 1
                continue

            libro = Libro(
                titulo=titulo,
                subtitulo=entrada.get("subtitulo") or None,
                autores="; ".join(entrada.get("autores") or []) or "",
                isbn=entrada.get("isbn") or None,
                editorial=entrada.get("editorial") or None,
                anio=entrada.get("anio") or None,
                idioma=entrada.get("idioma") or "es",
                categoria=entrada.get("categoria") or None,
                dewey=entrada.get("dewey") or None,
                sinopsis=entrada.get("sinopsis") or None,
                palabras_clave=", ".join(entrada.get("palabras_clave") or []) or None,
            )
            db.add(libro)
            db.flush()
            creados_libros += 1
            existentes.add(titulo.lower())

            cantidad = int(entrada.get("ejemplares") or 1)
            for _ in range(max(1, cantidad)):
                ubicacion = ubicaciones[indice_ubicacion % len(ubicaciones)]
                indice_ubicacion += 1

                db.add(
                    Ejemplar(
                        libro_id=libro.id,
                        codigo_inventario=f"EJ-{correlativo:05d}",
                        estado=config.EJEMPLAR_DISPONIBLE,
                        ubicacion_id=ubicacion.id,
                        condicion="bueno",
                    )
                )
                correlativo += 1
                creados_ejemplares += 1

        documentos = {s.documento for s in db.scalars(select(Socio))}
        for entrada in datos.get("socios", []):
            documento = str(entrada.get("documento") or "").strip()
            nombre = (entrada.get("nombre") or "").strip()
            if not documento or not nombre or documento in documentos:
                continue

            db.add(
                Socio(
                    nombre=nombre,
                    documento=documento,
                    email=entrada.get("email") or None,
                    telefono=entrada.get("telefono") or None,
                    direccion=entrada.get("direccion") or None,
                    tipo=entrada.get("tipo") or config.TIPO_EXTERNO,
                    estado=entrada.get("estado") or config.SOCIO_ACTIVO,
                )
            )
            documentos.add(documento)
            creados_socios += 1

    return {
        "libros": creados_libros,
        "ejemplares": creados_ejemplares,
        "socios": creados_socios,
        "omitidos": omitidos,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Importa un catalogo JSON.")
    parser.add_argument("archivo", help="Ruta al archivo JSON")
    parser.add_argument(
        "--reemplazar",
        action="store_true",
        help="Borra el catalogo actual antes de importar (falla si hay prestamos).",
    )
    args = parser.parse_args(argv)

    datos = cargar_json(Path(args.archivo))
    resumen = importar(datos, reemplazar=args.reemplazar)

    print("Importacion terminada")
    print(f"  libros creados:     {resumen['libros']}")
    print(f"  ejemplares creados: {resumen['ejemplares']}")
    print(f"  socios creados:     {resumen['socios']}")
    print(f"  omitidos:           {resumen['omitidos']}")

    with sesion() as db:
        print()
        print(f"  libros en base:     {db.scalar(select(func.count()).select_from(Libro))}")
        print(f"  ejemplares en base: {db.scalar(select(func.count()).select_from(Ejemplar))}")
        print(f"  socios en base:     {db.scalar(select(func.count()).select_from(Socio))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
