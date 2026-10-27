"""Servicio de socios: fichas, historial y situación de préstamo.

«Situación» es distinto de «estado»: el estado es el que se guarda en la
ficha (activo, suspendido, baja); la situación es la conclusión operativa
—puede o no retirar material— y depende también de los vencimientos y del
límite de ejemplares.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import func, select

from app import config
from app.db.database import sesion
from app.db.models import Advertencia, Ejemplar, Libro, Multa, Prestamo, Socio
from app.services import permisos, reglas
from app.services import multas as servicio_multas
from app.services.texto import normalizar

_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


# --------------------------------------------------------------------- lectura
def listar_socios(
    busqueda: str = "",
    tipo: str | None = None,
    estado: str | None = None,
    solo_vencidos: bool = False,
) -> list[dict]:
    """Listado de socios con su cantidad de préstamos activos y vencidos."""
    activos = (
        select(Prestamo.socio_id.label("socio_id"), func.count().label("total"))
        .where(Prestamo.fecha_devolucion.is_(None))
        .group_by(Prestamo.socio_id)
        .subquery()
    )
    vencidos = (
        select(Prestamo.socio_id.label("socio_id"), func.count().label("total"))
        .where(
            Prestamo.fecha_devolucion.is_(None),
            Prestamo.fecha_vencimiento < date.today(),
        )
        .group_by(Prestamo.socio_id)
        .subquery()
    )
    multas_pendientes = (
        select(Multa.socio_id.label("socio_id"), func.count().label("total"))
        .where(Multa.estado == config.MULTA_PENDIENTE)
        .group_by(Multa.socio_id)
        .subquery()
    )
    advertencias = (
        select(Advertencia.socio_id.label("socio_id"), func.count().label("total"))
        .group_by(Advertencia.socio_id)
        .subquery()
    )

    consulta = (
        select(
            Socio,
            func.coalesce(activos.c.total, 0),
            func.coalesce(vencidos.c.total, 0),
            func.coalesce(multas_pendientes.c.total, 0),
            func.coalesce(advertencias.c.total, 0),
        )
        .outerjoin(activos, activos.c.socio_id == Socio.id)
        .outerjoin(vencidos, vencidos.c.socio_id == Socio.id)
        .outerjoin(multas_pendientes, multas_pendientes.c.socio_id == Socio.id)
        .outerjoin(advertencias, advertencias.c.socio_id == Socio.id)
        .order_by(Socio.nombre)
    )

    if tipo:
        consulta = consulta.where(Socio.tipo == tipo)
    if estado:
        consulta = consulta.where(Socio.estado == estado)

    with sesion() as db:
        filas = db.execute(consulta).all()

    termino = normalizar(busqueda)
    resultado: list[dict] = []

    for socio, n_activos, n_vencidos, n_multas, n_advertencias in filas:
        if termino:
            campos = " ".join(
                [
                    socio.nombre or "",
                    socio.documento or "",
                    socio.email or "",
                    socio.telefono or "",
                ]
            )
            if termino not in normalizar(campos):
                continue

        if solo_vencidos and n_vencidos == 0:
            continue

        resultado.append(
            {
                "id": socio.id,
                "nombre": socio.nombre,
                "documento": socio.documento,
                "tipo": socio.tipo,
                "tipo_legible": config.TIPOS_SOCIO.get(socio.tipo, socio.tipo),
                "estado": socio.estado,
                "estado_legible": config.ESTADOS_SOCIO.get(socio.estado, socio.estado),
                "email": socio.email or "",
                "telefono": socio.telefono or "",
                "activos": n_activos,
                "vencidos": n_vencidos,
                "multas": n_multas,
                "advertencias": n_advertencias,
            }
        )

    return resultado


def obtener_socio(socio_id: int) -> dict | None:
    """Ficha completa de un socio, con su historial y su situación actual."""
    with sesion() as db:
        socio = db.get(Socio, socio_id)
        if socio is None:
            return None

        filas = db.execute(
            select(Prestamo, Ejemplar, Libro, Advertencia)
            .join(Ejemplar, Prestamo.ejemplar_id == Ejemplar.id)
            .join(Libro, Ejemplar.libro_id == Libro.id)
            .outerjoin(Advertencia, Advertencia.prestamo_id == Prestamo.id)
            .where(Prestamo.socio_id == socio_id)
            .order_by(Prestamo.fecha_prestamo.desc(), Prestamo.id.desc())
        ).all()

        hoy = date.today()
        activos = vencidos = atraso_maximo = 0
        historial: list[dict] = []

        for prestamo, ejemplar, libro, advertencia in filas:
            atraso = 0
            if prestamo.fecha_devolucion is None:
                activos += 1
                atraso = max(0, (hoy - prestamo.fecha_vencimiento).days)
                if atraso > 0:
                    vencidos += 1
                    atraso_maximo = max(atraso_maximo, atraso)

            recuperado = prestamo.estado == config.PRESTAMO_RECUPERADO
            historial.append(
                {
                    "id": prestamo.id,
                    "libro": libro.titulo,
                    "ejemplar": ejemplar.codigo_inventario,
                    "desde": prestamo.fecha_prestamo,
                    "vence": prestamo.fecha_vencimiento,
                    "devuelto": prestamo.fecha_devolucion,
                    "recuperado_el": (
                        advertencia.fecha
                        if recuperado and advertencia is not None
                        else None
                    ),
                    "estado": _estado_prestamo(prestamo, atraso),
                    "atraso": atraso,
                }
            )

        filas_advertencias = db.scalars(
            select(Advertencia)
            .where(Advertencia.socio_id == socio_id)
            .order_by(Advertencia.fecha.desc(), Advertencia.id.desc())
        ).all()
        advertencias_socio = [
            {
                "id": advertencia.id,
                "prestamo_id": advertencia.prestamo_id,
                "motivo": advertencia.motivo,
                "fecha": advertencia.fecha,
            }
            for advertencia in filas_advertencias
        ]

    multas_socio = servicio_multas.listar_multas(socio_id=socio_id)
    deuda = servicio_multas.deuda_pendiente(socio_id)

    return {
        "id": socio.id,
        "nombre": socio.nombre,
        "documento": socio.documento,
        "email": socio.email or "",
        "telefono": socio.telefono or "",
        "direccion": socio.direccion or "",
        "tipo": socio.tipo,
        "tipo_legible": config.TIPOS_SOCIO.get(socio.tipo, socio.tipo),
        "estado": socio.estado,
        "estado_legible": config.ESTADOS_SOCIO.get(socio.estado, socio.estado),
        "fecha_alta": socio.fecha_alta,
        "observaciones": socio.observaciones or "",
        "dias_prestamo": reglas.dias_prestamo(socio.tipo),
        "activos": activos,
        "vencidos": vencidos,
        "atraso_maximo": atraso_maximo,
        "total_prestamos": len(historial),
        "historial": historial,
        "advertencias": advertencias_socio,
        "multas": multas_socio,
        "multas_pendientes": deuda["cantidad"],
        "deuda_centavos": deuda["total_centavos"],
        "deuda": deuda["total"],
        "situacion": _situacion(socio, vencidos, atraso_maximo, activos, deuda),
    }


def situacion(socio_id: int) -> dict | None:
    """Indica si el socio puede retirar material y con qué motivo.

    Lo va a consultar el módulo de préstamos antes de registrar una salida.
    """
    with sesion() as db:
        socio = db.get(Socio, socio_id)
        if socio is None:
            return None

        vencimientos = db.scalars(
            select(Prestamo.fecha_vencimiento).where(
                Prestamo.socio_id == socio_id,
                Prestamo.fecha_devolucion.is_(None),
            )
        ).all()

        atrasos = [max(0, (date.today() - v).days) for v in vencimientos]
        vencidos = sum(1 for atraso in atrasos if atraso > 0)
        deuda = servicio_multas.deuda_pendiente(socio_id)
        return _situacion(
            socio, vencidos, max(atrasos, default=0), len(vencimientos), deuda
        )


def estadisticas() -> dict[str, int]:
    """Contadores del pie del listado."""
    hoy = date.today()
    with sesion() as db:
        return {
            "socios": db.scalar(select(func.count()).select_from(Socio)) or 0,
            "activos": db.scalar(
                select(func.count())
                .select_from(Socio)
                .where(Socio.estado == config.SOCIO_ACTIVO)
            )
            or 0,
            "suspendidos": db.scalar(
                select(func.count())
                .select_from(Socio)
                .where(Socio.estado == config.SOCIO_SUSPENDIDO)
            )
            or 0,
            "con_vencidos": db.scalar(
                select(func.count(func.distinct(Prestamo.socio_id))).where(
                    Prestamo.fecha_devolucion.is_(None),
                    Prestamo.fecha_vencimiento < hoy,
                )
            )
            or 0,
            "con_multas": db.scalar(
                select(func.count(func.distinct(Multa.socio_id))).where(
                    Multa.estado == config.MULTA_PENDIENTE
                )
            )
            or 0,
            "con_advertencias": db.scalar(
                select(func.count(func.distinct(Advertencia.socio_id)))
            )
            or 0,
        }


# -------------------------------------------------------------------- escritura
def crear_socio(datos: dict) -> tuple[bool, str, int | None]:
    if not permisos.puede("socios"):
        return False, permisos.SIN_PERMISO, None

    limpio, error = _validar(datos)
    if error:
        return False, error, None

    with sesion() as db:
        repetido = db.scalar(
            select(func.count())
            .select_from(Socio)
            .where(Socio.documento == limpio["documento"])
        )
        if repetido:
            return (
                False,
                f"Ya existe un socio con el documento {limpio['documento']}.",
                None,
            )

        socio = Socio(**limpio)
        db.add(socio)
        db.flush()
        return True, "", socio.id


def actualizar_socio(socio_id: int, datos: dict) -> tuple[bool, str]:
    if not permisos.puede("socios"):
        return False, permisos.SIN_PERMISO

    limpio, error = _validar(datos)
    if error:
        return False, error

    with sesion() as db:
        socio = db.get(Socio, socio_id)
        if socio is None:
            return False, "El socio ya no existe."

        if limpio["documento"] != socio.documento:
            repetido = db.scalar(
                select(func.count())
                .select_from(Socio)
                .where(
                    Socio.documento == limpio["documento"],
                    Socio.id != socio_id,
                )
            )
            if repetido:
                return (
                    False,
                    f"Ya existe un socio con el documento {limpio['documento']}.",
                )

        for campo, valor in limpio.items():
            setattr(socio, campo, valor)
        return True, ""


def cambiar_estado(socio_id: int, nuevo: str) -> tuple[bool, str]:
    """Cambia el estado de la ficha (activo, suspendido o baja)."""
    if not permisos.puede("socios"):
        return False, permisos.SIN_PERMISO

    if nuevo not in config.ESTADOS_SOCIO:
        return False, "El estado indicado no es válido."

    with sesion() as db:
        socio = db.get(Socio, socio_id)
        if socio is None:
            return False, "El socio ya no existe."

        socio.estado = nuevo
        return True, ""


def eliminar_socio(socio_id: int) -> tuple[bool, str]:
    """Solo permite borrar si el socio no tiene préstamos registrados."""
    if not permisos.puede("socios"):
        return False, permisos.SIN_PERMISO

    with sesion() as db:
        socio = db.get(Socio, socio_id)
        if socio is None:
            return False, "El socio ya no existe."

        historial = db.scalar(
            select(func.count())
            .select_from(Prestamo)
            .where(Prestamo.socio_id == socio_id)
        )
        if historial:
            return False, (
                "No se puede eliminar: el socio tiene préstamos registrados. "
                "Cambiá su estado a «Baja» para conservar el historial."
            )

        multas_registradas = db.scalar(
            select(func.count())
            .select_from(Multa)
            .where(Multa.socio_id == socio_id)
        )
        if multas_registradas:
            return False, (
                "No se puede eliminar: el socio tiene multas registradas. "
                "Cambiá su estado a «Baja» para conservar el historial."
            )

        db.delete(socio)
        return True, ""


# -------------------------------------------------------------------- internos
def _validar(datos: dict) -> tuple[dict, str | None]:
    """Normaliza y valida lo que llega del formulario."""
    nombre = (datos.get("nombre") or "").strip()
    if len(nombre) < 2:
        return {}, "El nombre y apellido son obligatorios."

    documento = re.sub(r"[^0-9]", "", datos.get("documento") or "")
    if not 6 <= len(documento) <= 12:
        return {}, "El documento debe tener entre 6 y 12 dígitos."

    email = (datos.get("email") or "").strip().lower() or None
    if email and not _CORREO.fullmatch(email):
        return {}, "El email no tiene un formato válido."

    tipo = datos.get("tipo")
    if tipo not in config.TIPOS_SOCIO:
        tipo = config.TIPO_EXTERNO

    estado = datos.get("estado")
    if estado not in config.ESTADOS_SOCIO:
        estado = config.SOCIO_ACTIVO

    return {
        "nombre": nombre,
        "documento": documento,
        "email": email,
        "telefono": (datos.get("telefono") or "").strip() or None,
        "direccion": (datos.get("direccion") or "").strip() or None,
        "tipo": tipo,
        "estado": estado,
        "observaciones": (datos.get("observaciones") or "").strip() or None,
    }, None


def _estado_prestamo(prestamo: Prestamo, atraso: int) -> str:
    if prestamo.estado == config.PRESTAMO_PERDIDO:
        return config.PRESTAMO_PERDIDO
    if prestamo.estado == config.PRESTAMO_RECUPERADO:
        return config.PRESTAMO_RECUPERADO
    if prestamo.fecha_devolucion is not None:
        return config.PRESTAMO_DEVUELTO
    return config.PRESTAMO_VENCIDO if atraso > 0 else config.PRESTAMO_ACTIVO


def _situacion(
    socio: Socio,
    vencidos: int,
    atraso_maximo: int,
    activos: int = 0,
    deuda: dict | None = None,
) -> dict:
    """Conclusión operativa: puede retirar material o no, y por qué."""
    dias = reglas.dias_prestamo(socio.tipo)
    gracia = reglas.dias_gracia_bloqueo()
    limite = reglas.limite_ejemplares()
    plural = "préstamo vencido" if vencidos == 1 else "préstamos vencidos"
    deuda = deuda or {"cantidad": 0, "total_centavos": 0, "total": "$ 0,00"}

    if socio.estado == config.SOCIO_BAJA:
        resultado = {
            "puede": False,
            "tono": "peligro",
            "motivo": "El socio está dado de baja: no puede retirar material.",
            "dias": dias,
        }
    elif socio.estado == config.SOCIO_SUSPENDIDO:
        resultado = {
            "puede": False,
            "tono": "peligro",
            "motivo": "El socio está suspendido: no puede retirar material.",
            "dias": dias,
        }
    elif deuda["cantidad"]:
        if deuda["cantidad"] == 1:
            motivo = (
                f"Tiene una multa pendiente de {deuda['total']}. "
                "Debe pagarla o anularla antes de retirar material."
            )
        else:
            motivo = (
                f"Tiene {deuda['cantidad']} multas pendientes por "
                f"{deuda['total']}. Debe pagarlas o anularlas antes de "
                "retirar material."
            )
        resultado = {
            "puede": False,
            "tono": "peligro",
            "motivo": motivo,
            "dias": dias,
        }
    elif vencidos and atraso_maximo > gracia:
        resultado = {
            "puede": False,
            "tono": "peligro",
            "motivo": (
                f"Bloqueado por {vencidos} {plural}, con hasta {atraso_maximo} "
                f"días de atraso. Debe devolverlos antes de retirar más material."
            ),
            "dias": dias,
        }
    elif activos >= limite:
        resultado = {
            "puede": False,
            "tono": "aviso",
            "motivo": (
                f"Ya tiene {activos} de {limite} ejemplares en préstamo. "
                "Debe devolver alguno antes de retirar más material."
            ),
            "dias": dias,
        }
    elif vencidos:
        resultado = {
            "puede": True,
            "tono": "aviso",
            "motivo": (
                f"Tiene {vencidos} {plural} dentro del plazo de gracia "
                f"({gracia} días)."
            ),
            "dias": dias,
        }
    else:
        resultado = {
            "puede": True,
            "tono": "exito",
            "motivo": f"Puede retirar material. Préstamo por {dias} días.",
            "dias": dias,
        }

    resultado["activos"] = activos
    resultado["limite"] = limite
    resultado["deuda_centavos"] = deuda["total_centavos"]
    resultado["multas_pendientes"] = deuda["cantidad"]
    return resultado
