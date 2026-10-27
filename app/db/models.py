"""Modelos de datos de BibloApp (SQLAlchemy 2.0).

Separación clave del diseño:
  - Libro    = la obra bibliográfica (título, autor, ISBN).
  - Ejemplar = la copia física concreta, con su propio código y ubicación.
Un libro puede tener N ejemplares.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app import config


class Base(DeclarativeBase):
    pass


class Empleado(Base):
    __tablename__ = "empleado"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    usuario: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    pass_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20), default=config.ROL_AUXILIAR)
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    prestamos: Mapped[list["Prestamo"]] = relationship(back_populates="empleado")
    movimientos: Mapped[list["Movimiento"]] = relationship(back_populates="empleado")
    multas: Mapped[list["Multa"]] = relationship(back_populates="empleado")

    def __repr__(self) -> str:
        return f"<Empleado {self.usuario} ({self.rol})>"


class Ubicacion(Base):
    """Lugar físico dentro de la biblioteca: sala + estantería + balda."""

    __tablename__ = "ubicacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    sala: Mapped[str] = mapped_column(String(60))
    estanteria: Mapped[str] = mapped_column(String(20))
    balda: Mapped[str] = mapped_column(String(20))
    referencia: Mapped[str | None] = mapped_column(String(200), default=None)

    ejemplares: Mapped[list["Ejemplar"]] = relationship(back_populates="ubicacion")

    @property
    def descripcion(self) -> str:
        return f"{self.sala} / Estanteria {self.estanteria} / Balda {self.balda}"

    def __repr__(self) -> str:
        return f"<Ubicacion {self.codigo}>"


class Libro(Base):
    __tablename__ = "libro"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(250), index=True)
    subtitulo: Mapped[str | None] = mapped_column(String(250), default=None)
    autores: Mapped[str] = mapped_column(String(250), default="")
    isbn: Mapped[str | None] = mapped_column(String(20), index=True, default=None)
    editorial: Mapped[str | None] = mapped_column(String(120), default=None)
    anio: Mapped[int | None] = mapped_column(Integer, default=None)
    idioma: Mapped[str] = mapped_column(String(20), default="es")
    categoria: Mapped[str | None] = mapped_column(String(60), index=True, default=None)
    dewey: Mapped[str | None] = mapped_column(String(10), default=None)
    sinopsis: Mapped[str | None] = mapped_column(Text, default=None)
    palabras_clave: Mapped[str | None] = mapped_column(String(300), default=None)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    ejemplares: Mapped[list["Ejemplar"]] = relationship(
        back_populates="libro", cascade="all, delete-orphan"
    )

    @property
    def autores_lista(self) -> list[str]:
        return [a.strip() for a in self.autores.split(";") if a.strip()]

    @property
    def disponibles(self) -> int:
        return sum(1 for e in self.ejemplares if e.estado == config.EJEMPLAR_DISPONIBLE)

    def __repr__(self) -> str:
        return f"<Libro {self.titulo}>"


class Ejemplar(Base):
    """Copia física de un libro. Tiene código propio y ubicación propia."""

    __tablename__ = "ejemplar"

    id: Mapped[int] = mapped_column(primary_key=True)
    libro_id: Mapped[int] = mapped_column(ForeignKey("libro.id"), index=True)
    codigo_inventario: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(20), default=config.EJEMPLAR_DISPONIBLE)
    ubicacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("ubicacion.id"), default=None
    )
    fecha_alta: Mapped[date] = mapped_column(Date, default=date.today)
    condicion: Mapped[str] = mapped_column(String(40), default="bueno")
    notas: Mapped[str | None] = mapped_column(Text, default=None)

    libro: Mapped["Libro"] = relationship(back_populates="ejemplares")
    ubicacion: Mapped["Ubicacion | None"] = relationship(back_populates="ejemplares")
    prestamos: Mapped[list["Prestamo"]] = relationship(back_populates="ejemplar")

    @property
    def esta_disponible(self) -> bool:
        return self.estado == config.EJEMPLAR_DISPONIBLE

    def __repr__(self) -> str:
        return f"<Ejemplar {self.codigo_inventario}>"


class Socio(Base):
    __tablename__ = "socio"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), index=True)
    documento: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(150), default=None)
    telefono: Mapped[str | None] = mapped_column(String(40), default=None)
    direccion: Mapped[str | None] = mapped_column(String(250), default=None)
    tipo: Mapped[str] = mapped_column(String(20), default=config.TIPO_EXTERNO)
    estado: Mapped[str] = mapped_column(String(20), default=config.SOCIO_ACTIVO)
    fecha_alta: Mapped[date] = mapped_column(Date, default=date.today)
    observaciones: Mapped[str | None] = mapped_column(Text, default=None)

    prestamos: Mapped[list["Prestamo"]] = relationship(back_populates="socio")
    multas: Mapped[list["Multa"]] = relationship(back_populates="socio")
    advertencias: Mapped[list["Advertencia"]] = relationship(back_populates="socio")

    def __repr__(self) -> str:
        return f"<Socio {self.nombre}>"


class Prestamo(Base):
    __tablename__ = "prestamo"

    id: Mapped[int] = mapped_column(primary_key=True)
    ejemplar_id: Mapped[int] = mapped_column(ForeignKey("ejemplar.id"), index=True)
    socio_id: Mapped[int] = mapped_column(ForeignKey("socio.id"), index=True)
    empleado_id: Mapped[int | None] = mapped_column(
        ForeignKey("empleado.id"), default=None
    )
    fecha_prestamo: Mapped[date] = mapped_column(Date, default=date.today)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    fecha_devolucion: Mapped[date | None] = mapped_column(Date, default=None)
    estado: Mapped[str] = mapped_column(String(20), default=config.PRESTAMO_ACTIVO)
    renovaciones: Mapped[int] = mapped_column(Integer, default=0)
    notas: Mapped[str | None] = mapped_column(Text, default=None)

    ejemplar: Mapped["Ejemplar"] = relationship(back_populates="prestamos")
    socio: Mapped["Socio"] = relationship(back_populates="prestamos")
    empleado: Mapped["Empleado | None"] = relationship(back_populates="prestamos")
    multas: Mapped[list["Multa"]] = relationship(back_populates="prestamo")
    advertencia: Mapped["Advertencia | None"] = relationship(back_populates="prestamo")

    @property
    def dias_atraso(self) -> int:
        if self.fecha_devolucion is not None:
            return 0
        return max(0, (date.today() - self.fecha_vencimiento).days)

    def __repr__(self) -> str:
        return f"<Prestamo {self.id} ejemplar={self.ejemplar_id}>"


class Multa(Base):
    """Deuda de un socio, normalmente por un ejemplar perdido.

    El monto se guarda en centavos para que las cuentas sean exactas.
    Una multa pendiente bloquea nuevas salidas del socio hasta que se pague
    o se anule.
    """

    __tablename__ = "multa"

    id: Mapped[int] = mapped_column(primary_key=True)
    socio_id: Mapped[int] = mapped_column(ForeignKey("socio.id"), index=True)
    prestamo_id: Mapped[int | None] = mapped_column(
        ForeignKey("prestamo.id"), index=True, default=None
    )
    empleado_id: Mapped[int | None] = mapped_column(
        ForeignKey("empleado.id"), default=None
    )
    concepto: Mapped[str] = mapped_column(String(200))
    monto_centavos: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(
        String(20), default=config.MULTA_PENDIENTE
    )
    fecha: Mapped[date] = mapped_column(Date, default=date.today)
    fecha_pago: Mapped[date | None] = mapped_column(Date, default=None)
    notas: Mapped[str | None] = mapped_column(Text, default=None)

    socio: Mapped["Socio"] = relationship(back_populates="multas")
    prestamo: Mapped["Prestamo | None"] = relationship(back_populates="multas")
    empleado: Mapped["Empleado | None"] = relationship(back_populates="multas")

    def __repr__(self) -> str:
        return f"<Multa {self.id} socio={self.socio_id} ${self.monto_centavos / 100:.2f}>"


class Advertencia(Base):
    """Aviso que queda en la ficha del socio al recuperar un ejemplar perdido.

    No bloquea nuevas salidas: solo deja constancia de que el socio ya tuvo
    un ejemplar marcado como perdido y que después apareció. Se conserva
    aunque la multa asociada se haya anulado.
    """

    __tablename__ = "advertencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    socio_id: Mapped[int] = mapped_column(ForeignKey("socio.id"), index=True)
    prestamo_id: Mapped[int | None] = mapped_column(
        ForeignKey("prestamo.id"), unique=True, index=True, default=None
    )
    motivo: Mapped[str] = mapped_column(String(300))
    fecha: Mapped[date] = mapped_column(Date, default=date.today)

    socio: Mapped["Socio"] = relationship(back_populates="advertencias")
    prestamo: Mapped["Prestamo | None"] = relationship(back_populates="advertencia")

    def __repr__(self) -> str:
        return f"<Advertencia {self.id} socio={self.socio_id}>"


class Movimiento(Base):
    """Auditoría: quién hizo qué y cuándo."""

    __tablename__ = "movimiento"

    id: Mapped[int] = mapped_column(primary_key=True)
    empleado_id: Mapped[int | None] = mapped_column(
        ForeignKey("empleado.id"), default=None, index=True
    )
    accion: Mapped[str] = mapped_column(String(40), index=True)
    entidad: Mapped[str] = mapped_column(String(40))
    entidad_id: Mapped[int | None] = mapped_column(Integer, default=None)
    detalle: Mapped[str | None] = mapped_column(Text, default=None)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    empleado: Mapped["Empleado | None"] = relationship(back_populates="movimientos")

    def __repr__(self) -> str:
        return f"<Movimiento {self.accion} {self.entidad}>"


class Configuracion(Base):
    """Ajustes editables en tiempo de ejecución (clave/valor)."""

    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"<Configuracion {self.clave}={self.valor}>"
