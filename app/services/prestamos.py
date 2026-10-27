"""Servicio de préstamos: salidas, devoluciones, renovaciones y vencidos.

Un préstamo está abierto mientras no tenga fecha de devolución. El estado
«vencido» no se guarda: se deduce comparando la fecha de vencimiento con
hoy, igual que hace la ficha del socio. La tabla conserva el estado con el
que se cerró el préstamo (activo, devuelto, perdido o recuperado).

«Recuperado» es un préstamo que se había cerrado como perdido y cuyo
ejemplar apareció después. La multa pendiente se anula, pero queda una
advertencia en la ficha del socio.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select

from app import config
from app.db.database import sesion
from app.db.models import (
    Advertencia,
    Ejemplar,
    Libro,
    Multa,
    Prestamo,
    Socio,
    Ubicacion,
)
from app.services import multas as servicio_multas
from app.services import permisos, reglas, socios
from app.services.auth import sesion_actual
from app.services.texto import normalizar

FILTROS = {
    None: "Todos los préstamos",
    "activos": "Activos",
    "vencidos": "Vencidos",
    "devueltos": "Devueltos",
    "recuperados": "Recuperados",
    "perdidos": "Perdidos",
}


# --------------------------------------------------------------------- lectura
def listar_prestamos(
    busqueda: str = "",
    filtro: str | None = None,
) -> list[dict]:
    """Préstamos con los datos que se muestran en la pantalla.

    `filtro` acepta «activos», «vencidos», «devueltos» o None. La búsqueda
    ignora tildes y mayúsculas y mira libro, ejemplar, socio y documento.
    """
    consulta = (
        select(Prestamo, Ejemplar, Libro, Socio, Advertencia)
        .join(Ejemplar, Prestamo.ejemplar_id == Ejemplar.id)
        .join(Libro, Ejemplar.libro_id == Libro.id)
        .join(Socio, Prestamo.socio_id == Socio.id)
        .outerjoin(Advertencia, Advertencia.prestamo_id == Prestamo.id)
    )

    hoy = date.today()
    if filtro == "activos":
        consulta = consulta.where(
            Prestamo.fecha_devolucion.is_(None),
            Prestamo.fecha_vencimiento >= hoy,
        )
    elif filtro == "vencidos":
        consulta = consulta.where(
            Prestamo.fecha_devolucion.is_(None),
            Prestamo.fecha_vencimiento < hoy,
        )
    elif filtro == "devueltos":
        consulta = consulta.where(
            Prestamo.fecha_devolucion.is_not(None),
            Prestamo.estado.notin_(
                (config.PRESTAMO_PERDIDO, config.PRESTAMO_RECUPERADO)
            ),
        )
    elif filtro == "recuperados":
        consulta = consulta.where(Prestamo.estado == config.PRESTAMO_RECUPERADO)
    elif filtro == "perdidos":
        consulta = consulta.where(Prestamo.estado == config.PRESTAMO_PERDIDO)

    with sesion() as db:
        filas = db.execute(consulta).all()

    maximo = reglas.max_renovaciones()
    termino = normalizar(busqueda)
    resultado: list[dict] = []

    for prestamo, ejemplar, libro, socio, advertencia in filas:
        if termino:
            campos = " ".join(
                [
                    libro.titulo or "",
                    libro.autores or "",
                    ejemplar.codigo_inventario or "",
                    socio.nombre or "",
                    socio.documento or "",
                ]
            )
            if termino not in normalizar(campos):
                continue

        resultado.append(
            _armar(prestamo, ejemplar, libro, socio, hoy, maximo, advertencia)
        )

    # Abiertos primero (por vencimiento); después los devueltos, del más
    # reciente al más viejo.
    resultado.sort(
        key=lambda p: (
            0 if p["devuelto"] is None else 1,
            p["vence"] if p["devuelto"] is None else -p["devuelto"].toordinal(),
        )
    )
    return resultado


def obtener_prestamo(prestamo_id: int) -> dict | None:
    """Un préstamo concreto, con el mismo formato que el listado."""
    with sesion() as db:
        fila = db.execute(
            select(Prestamo, Ejemplar, Libro, Socio, Advertencia)
            .join(Ejemplar, Prestamo.ejemplar_id == Ejemplar.id)
            .join(Libro, Ejemplar.libro_id == Libro.id)
            .join(Socio, Prestamo.socio_id == Socio.id)
            .outerjoin(Advertencia, Advertencia.prestamo_id == Prestamo.id)
            .where(Prestamo.id == prestamo_id)
        ).first()

        if fila is None:
            return None

        prestamo, ejemplar, libro, socio, advertencia = fila
        return _armar(
            prestamo,
            ejemplar,
            libro,
            socio,
            date.today(),
            reglas.max_renovaciones(),
            advertencia,
        )


def ejemplares_disponibles() -> list[dict]:
    """Copias que hoy se pueden prestar, para el formulario de salida."""
    with sesion() as db:
        filas = db.execute(
            select(Ejemplar, Libro, Ubicacion)
            .join(Libro, Ejemplar.libro_id == Libro.id)
            .outerjoin(Ubicacion, Ejemplar.ubicacion_id == Ubicacion.id)
            .where(Ejemplar.estado == config.EJEMPLAR_DISPONIBLE)
            .order_by(Libro.titulo, Ejemplar.codigo_inventario)
        ).all()

        return [
            {
                "id": ejemplar.id,
                "codigo": ejemplar.codigo_inventario,
                "libro": libro.titulo,
                "autores": libro.autores or "",
                "ubicacion": ubicacion.codigo if ubicacion else "",
            }
            for ejemplar, libro, ubicacion in filas
        ]


def estadisticas() -> dict[str, int]:
    """Contadores del pie del listado."""
    hoy = date.today()
    with sesion() as db:
        return {
            "total": db.scalar(select(func.count()).select_from(Prestamo)) or 0,
            "activos": db.scalar(
                select(func.count())
                .select_from(Prestamo)
                .where(
                    Prestamo.fecha_devolucion.is_(None),
                    Prestamo.fecha_vencimiento >= hoy,
                )
            )
            or 0,
            "vencidos": db.scalar(
                select(func.count())
                .select_from(Prestamo)
                .where(
                    Prestamo.fecha_devolucion.is_(None),
                    Prestamo.fecha_vencimiento < hoy,
                )
            )
            or 0,
            "devueltos": db.scalar(
                select(func.count())
                .select_from(Prestamo)
                .where(
                    Prestamo.fecha_devolucion.is_not(None),
                    Prestamo.estado.notin_(
                        (config.PRESTAMO_PERDIDO, config.PRESTAMO_RECUPERADO)
                    ),
                )
            )
            or 0,
            "recuperados": db.scalar(
                select(func.count())
                .select_from(Prestamo)
                .where(Prestamo.estado == config.PRESTAMO_RECUPERADO)
            )
            or 0,
            "perdidos": db.scalar(
                select(func.count())
                .select_from(Prestamo)
                .where(Prestamo.estado == config.PRESTAMO_PERDIDO)
            )
            or 0,
        }


# -------------------------------------------------------------------- escritura
def prestar(
    socio_id: int, ejemplar_id: int, notas: str = ""
) -> tuple[bool, str, int | None]:
    """Registra la salida de un ejemplar a un socio habilitado."""
    if not permisos.puede("prestamos"):
        return False, permisos.SIN_PERMISO, None

    with sesion() as db:
        socio = db.get(Socio, socio_id)
        if socio is None:
            return False, "El socio ya no existe.", None

        ejemplar = db.get(Ejemplar, ejemplar_id)
        if ejemplar is None:
            return False, "El ejemplar ya no existe.", None

        if ejemplar.estado == config.EJEMPLAR_PRESTADO:
            return (
                False,
                f"El ejemplar {ejemplar.codigo_inventario} ya está prestado. "
                "Registrá primero la devolución.",
                None,
            )

        if ejemplar.estado != config.EJEMPLAR_DISPONIBLE:
            estado = config.ESTADOS_EJEMPLAR.get(ejemplar.estado, ejemplar.estado)
            return (
                False,
                f"El ejemplar {ejemplar.codigo_inventario} no se puede prestar: "
                f"está {estado.lower()}.",
                None,
            )

        # Situación del socio: estado de la ficha, atrasos y límite de
        # ejemplares. Es la misma conclusión que muestra la ficha del socio.
        situacion = socios.situacion(socio_id)
        if situacion is None:
            return False, "El socio ya no existe.", None
        if not situacion["puede"]:
            return False, situacion["motivo"], None

        abierto = db.scalar(
            select(func.count())
            .select_from(Prestamo)
            .where(
                Prestamo.ejemplar_id == ejemplar_id,
                Prestamo.fecha_devolucion.is_(None),
            )
        )
        if abierto:
            return (
                False,
                f"El ejemplar {ejemplar.codigo_inventario} figura con un "
                "préstamo sin devolver. Revisá el historial antes de continuar.",
                None,
            )

        hoy = date.today()
        registro = Prestamo(
            ejemplar_id=ejemplar.id,
            socio_id=socio.id,
            empleado_id=_empleado_id(),
            fecha_prestamo=hoy,
            fecha_vencimiento=hoy + timedelta(days=situacion["dias"]),
            estado=config.PRESTAMO_ACTIVO,
            renovaciones=0,
            notas=(notas or "").strip() or None,
        )
        ejemplar.estado = config.EJEMPLAR_PRESTADO
        db.add(registro)
        db.flush()
        return True, "", registro.id


def devolver(
    prestamo_id: int, estado_ejemplar: str = config.EJEMPLAR_DISPONIBLE
) -> tuple[bool, str]:
    """Cierra un préstamo y deja el ejemplar disponible o en reparación."""
    if not permisos.puede("prestamos"):
        return False, permisos.SIN_PERMISO

    if estado_ejemplar not in (
        config.EJEMPLAR_DISPONIBLE,
        config.EJEMPLAR_REPARACION,
    ):
        estado_ejemplar = config.EJEMPLAR_DISPONIBLE

    with sesion() as db:
        prestamo = db.get(Prestamo, prestamo_id)
        if prestamo is None:
            return False, "El préstamo ya no existe."

        if prestamo.fecha_devolucion is not None:
            return False, "Este préstamo ya figura como devuelto."

        prestamo.fecha_devolucion = date.today()
        prestamo.estado = config.PRESTAMO_DEVUELTO

        ejemplar = db.get(Ejemplar, prestamo.ejemplar_id)
        if ejemplar is not None and ejemplar.estado == config.EJEMPLAR_PRESTADO:
            ejemplar.estado = estado_ejemplar

        return True, ""


def marcar_perdido(
    prestamo_id: int, monto_centavos: int = 0, notas: str = ""
) -> tuple[bool, str]:
    """Cierra el préstamo como perdido, da de baja el ejemplar y multa al socio.

    La fecha de devolución se usa como fecha de cierre para que el préstamo
    deje de contar como activo o vencido. El estado «perdido» es el que
    distingue este cierre de una devolución normal. Si el monto es mayor que
    cero se crea una multa pendiente; pagarla o anularla es lo que levanta el
    bloqueo del socio.
    """
    if not permisos.puede("prestamos"):
        return False, permisos.SIN_PERMISO

    monto = max(0, int(monto_centavos or 0))

    with sesion() as db:
        prestamo = db.get(Prestamo, prestamo_id)
        if prestamo is None:
            return False, "El préstamo ya no existe."

        if prestamo.estado == config.PRESTAMO_PERDIDO:
            return False, "Este préstamo ya figura como perdido."

        if prestamo.fecha_devolucion is not None:
            return False, "Este préstamo ya está cerrado."

        ejemplar = db.get(Ejemplar, prestamo.ejemplar_id)
        if ejemplar is None:
            return False, "El ejemplar ya no existe."

        socio = db.get(Socio, prestamo.socio_id)
        if socio is None:
            return False, "El socio ya no existe."

        libro = db.get(Libro, ejemplar.libro_id)
        hoy = date.today()
        prestamo.fecha_devolucion = hoy
        prestamo.estado = config.PRESTAMO_PERDIDO
        ejemplar.estado = config.EJEMPLAR_PERDIDO

        if monto > 0:
            titulo = libro.titulo if libro is not None else ejemplar.codigo_inventario
            db.add(
                Multa(
                    socio_id=socio.id,
                    prestamo_id=prestamo.id,
                    empleado_id=_empleado_id(),
                    concepto=(
                        f"Ejemplar perdido: {ejemplar.codigo_inventario} · {titulo}"
                    ),
                    monto_centavos=monto,
                    estado=config.MULTA_PENDIENTE,
                    fecha=hoy,
                    notas=(notas or "").strip() or None,
                )
            )

        return True, ""


def recuperar(
    prestamo_id: int, estado_ejemplar: str = config.EJEMPLAR_DISPONIBLE
) -> tuple[bool, str]:
    """Marca como recuperado un ejemplar que había sido dado por perdido.

    Cierra el círculo de una pérdida: devuelve el ejemplar al inventario en
    el estado elegido, anula las multas pendientes de ese préstamo y deja una
    advertencia permanente en la ficha del socio. Las multas ya pagadas no
    se modifican.

    Anular una multa es una decisión administrativa, así que la operación
    pide el permiso «socios» (el mismo que cobrar o anular una multa).
    """
    if not permisos.puede("socios"):
        return False, permisos.SIN_PERMISO

    if estado_ejemplar not in (
        config.EJEMPLAR_DISPONIBLE,
        config.EJEMPLAR_REPARACION,
    ):
        estado_ejemplar = config.EJEMPLAR_DISPONIBLE

    with sesion() as db:
        prestamo = db.get(Prestamo, prestamo_id)
        if prestamo is None:
            return False, "El préstamo ya no existe."

        if prestamo.estado == config.PRESTAMO_RECUPERADO:
            return False, "Este préstamo ya figura como recuperado."
        if prestamo.estado != config.PRESTAMO_PERDIDO:
            return False, "Solo se puede recuperar un préstamo marcado como perdido."

        ejemplar = db.get(Ejemplar, prestamo.ejemplar_id)
        if ejemplar is None:
            return False, "El ejemplar ya no existe."

        socio = db.get(Socio, prestamo.socio_id)
        if socio is None:
            return False, "El socio ya no existe."

        libro = db.get(Libro, ejemplar.libro_id)
        hoy = date.today()
        prestamo.estado = config.PRESTAMO_RECUPERADO
        ejemplar.estado = estado_ejemplar

        pendientes = list(
            db.scalars(
                select(Multa).where(
                    Multa.prestamo_id == prestamo.id,
                    Multa.estado == config.MULTA_PENDIENTE,
                )
            )
        )
        nota = f"Anulada al recuperar el ejemplar el {hoy:%d/%m/%Y}."
        for multa in pendientes:
            multa.estado = config.MULTA_ANULADA
            multa.notas = f"{multa.notas}\n{nota}" if multa.notas else nota

        titulo = libro.titulo if libro is not None else ejemplar.codigo_inventario
        motivo = (
            "Recuperó un ejemplar que había sido marcado como perdido: "
            f"{ejemplar.codigo_inventario} · {titulo}."
        )
        if pendientes:
            total = sum(multa.monto_centavos for multa in pendientes)
            motivo += (
                " Se anuló la multa pendiente de "
                f"{servicio_multas.formatear_monto(total)}."
            )

        db.add(
            Advertencia(
                socio_id=socio.id,
                prestamo_id=prestamo.id,
                motivo=motivo,
                fecha=hoy,
            )
        )
        return True, ""


def renovar(prestamo_id: int) -> tuple[bool, str]:
    """Extiende el vencimiento de un préstamo abierto y al día."""
    if not permisos.puede("prestamos"):
        return False, permisos.SIN_PERMISO

    with sesion() as db:
        prestamo = db.get(Prestamo, prestamo_id)
        if prestamo is None:
            return False, "El préstamo ya no existe."

        if prestamo.fecha_devolucion is not None:
            return False, "Este préstamo ya fue devuelto: no se puede renovar."

        if prestamo.estado == config.PRESTAMO_PERDIDO:
            return False, "El préstamo figura como perdido: no se puede renovar."

        hoy = date.today()
        if prestamo.fecha_vencimiento < hoy:
            return (
                False,
                "El préstamo está vencido: no se puede renovar. "
                "Registrá la devolución y, si corresponde, un nuevo préstamo.",
            )

        maximo = reglas.max_renovaciones()
        if maximo <= 0:
            return False, "Las renovaciones están deshabilitadas en la configuración."

        if prestamo.renovaciones >= maximo:
            veces = "vez" if prestamo.renovaciones == 1 else "veces"
            return (
                False,
                f"Este préstamo ya se renovó {prestamo.renovaciones} {veces}. "
                f"El máximo permitido es {maximo}.",
            )

        socio = db.get(Socio, prestamo.socio_id)
        if socio is None:
            return False, "El socio ya no existe."

        if socio.estado == config.SOCIO_SUSPENDIDO:
            return False, "El socio está suspendido: no se puede renovar."
        if socio.estado == config.SOCIO_BAJA:
            return False, "El socio está dado de baja: no se puede renovar."

        # Otros préstamos del socio fuera del plazo de gracia bloquean la
        # renovación, igual que bloquean una salida nueva. No se aplica el
        # límite de ejemplares: renovar no suma una copia más.
        gracia = reglas.dias_gracia_bloqueo()
        otros_vencidos = db.scalar(
            select(func.count())
            .select_from(Prestamo)
            .where(
                Prestamo.socio_id == prestamo.socio_id,
                Prestamo.id != prestamo.id,
                Prestamo.fecha_devolucion.is_(None),
                Prestamo.fecha_vencimiento < hoy - timedelta(days=gracia),
            )
        )
        if otros_vencidos:
            plural = (
                "préstamo vencido" if otros_vencidos == 1 else "préstamos vencidos"
            )
            return (
                False,
                f"El socio tiene {otros_vencidos} {plural} fuera del plazo de "
                "gracia: no se puede renovar hasta devolverlos.",
            )

        dias = reglas.dias_renovacion()
        if dias <= 0:
            return False, "Los días de renovación configurados son cero."

        prestamo.fecha_vencimiento = prestamo.fecha_vencimiento + timedelta(days=dias)
        prestamo.renovaciones += 1
        return True, ""


# -------------------------------------------------------------------- internos
def _armar(
    prestamo: Prestamo,
    ejemplar: Ejemplar,
    libro: Libro,
    socio: Socio,
    hoy: date,
    maximo: int,
    advertencia: Advertencia | None = None,
) -> dict:
    """Pasa un préstamo del ORM al diccionario que consume la interfaz."""
    devuelto = prestamo.fecha_devolucion
    if devuelto is None:
        atraso = max(0, (hoy - prestamo.fecha_vencimiento).days)
    else:
        atraso = 0

    perdido = prestamo.estado == config.PRESTAMO_PERDIDO
    recuperado = prestamo.estado == config.PRESTAMO_RECUPERADO
    if perdido:
        estado = config.PRESTAMO_PERDIDO
    elif recuperado:
        estado = config.PRESTAMO_RECUPERADO
    elif devuelto is not None:
        estado = config.PRESTAMO_DEVUELTO
    elif atraso > 0:
        estado = config.PRESTAMO_VENCIDO
    else:
        estado = config.PRESTAMO_ACTIVO

    renovable = (
        devuelto is None
        and socio.estado == config.SOCIO_ACTIVO
        and not perdido
        and not recuperado
        and atraso == 0
        and maximo > 0
        and prestamo.renovaciones < maximo
    )

    return {
        "id": prestamo.id,
        "socio_id": socio.id,
        "ejemplar_id": ejemplar.id,
        "socio": socio.nombre,
        "documento": socio.documento,
        "socio_estado": socio.estado,
        "libro": libro.titulo,
        "autores": libro.autores or "",
        "ejemplar": ejemplar.codigo_inventario,
        "desde": prestamo.fecha_prestamo,
        "vence": prestamo.fecha_vencimiento,
        "devuelto": devuelto,
        "perdido": perdido,
        "recuperado": recuperado,
        "recuperado_el": (
            advertencia.fecha if recuperado and advertencia is not None else None
        ),
        "atraso": atraso,
        "estado": estado,
        "renovaciones": prestamo.renovaciones,
        "max_renovaciones": maximo,
        "renovable": renovable,
        "notas": prestamo.notas or "",
    }


def _empleado_id() -> int | None:
    empleado = sesion_actual.empleado
    return empleado.id if empleado is not None else None
