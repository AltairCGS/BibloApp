"""Formularios modales para libros y ejemplares."""

from __future__ import annotations

import re
from datetime import date, timedelta

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.services import catalogo as servicio_catalogo
from app.services import multas as servicio_multas
from app.services import prestamos as servicio_prestamos
from app.services import reglas
from app.services import socios as servicio_socios
from app.ui import theme


def _etiqueta(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setObjectName("fieldLabel")
    return lbl


def _botones(dialogo: QDialog, texto_guardar: str = "Guardar") -> QHBoxLayout:
    fila = QHBoxLayout()
    fila.setSpacing(10)

    cancelar = QPushButton("Cancelar")
    cancelar.setObjectName("ghostButton")
    cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
    cancelar.clicked.connect(dialogo.reject)

    guardar = QPushButton(texto_guardar)
    guardar.setObjectName("primaryButton")
    guardar.setCursor(Qt.CursorShape.PointingHandCursor)
    guardar.setDefault(True)
    guardar.clicked.connect(dialogo.accept)

    fila.addStretch(1)
    fila.addWidget(cancelar)
    fila.addWidget(guardar)
    return fila


class DialogoLibro(QDialog):
    """Alta y edición de un libro."""

    def __init__(self, datos: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._datos = datos or {}
        self.setWindowTitle("Editar libro" if datos else "Nuevo libro")
        self.setModal(True)
        self.setMinimumWidth(620)
        self._construir()
        self._cargar()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Editar libro" if self._datos else "Nuevo libro")
        titulo.setObjectName("dialogTitle")
        layout.addWidget(titulo)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.campo_titulo = QLineEdit()
        self.campo_titulo.setPlaceholderText("Título de la obra")
        self.campo_subtitulo = QLineEdit()
        self.campo_subtitulo.setPlaceholderText("Opcional")
        self.campo_autores = QLineEdit()
        self.campo_autores.setPlaceholderText("Separados por punto y coma: Borges, J. L.; Bioy Casares, A.")
        self.campo_isbn = QLineEdit()
        self.campo_isbn.setPlaceholderText("Opcional")
        self.campo_editorial = QLineEdit()
        self.campo_anio = QLineEdit()
        self.campo_anio.setPlaceholderText("Sin dato")
        self.campo_anio.setValidator(QIntValidator(0, 2100, self))
        self.campo_anio.setMaxLength(4)
        self.campo_categoria = QComboBox()
        self.campo_categoria.addItem("Sin categoría", None)
        for categoria in servicio_catalogo.listar_categorias():
            self.campo_categoria.addItem(categoria, categoria)
        self.campo_dewey = QLineEdit()
        self.campo_dewey.setPlaceholderText("Ej. 863")
        self.campo_dewey.setMaxLength(10)
        self.campo_claves = QLineEdit()
        self.campo_claves.setPlaceholderText("términos separados por coma")
        self.campo_sinopsis = QTextEdit()
        self.campo_sinopsis.setPlaceholderText("Resumen breve de la obra (opcional)")
        self.campo_sinopsis.setFixedHeight(86)

        grid.addWidget(_etiqueta("Título *"), 0, 0)
        grid.addWidget(self.campo_titulo, 1, 0, 1, 2)
        grid.addWidget(_etiqueta("Subtítulo"), 2, 0)
        grid.addWidget(self.campo_subtitulo, 3, 0, 1, 2)
        grid.addWidget(_etiqueta("Autor o autores"), 4, 0)
        grid.addWidget(self.campo_autores, 5, 0, 1, 2)
        grid.addWidget(_etiqueta("ISBN"), 6, 0)
        grid.addWidget(_etiqueta("Editorial"), 6, 1)
        grid.addWidget(self.campo_isbn, 7, 0)
        grid.addWidget(self.campo_editorial, 7, 1)
        grid.addWidget(_etiqueta("Año"), 8, 0)
        grid.addWidget(_etiqueta("Categoría"), 8, 1)
        grid.addWidget(self.campo_anio, 9, 0)
        grid.addWidget(self.campo_categoria, 9, 1)
        grid.addWidget(_etiqueta("Dewey"), 10, 0)
        grid.addWidget(_etiqueta("Palabras clave"), 10, 1)
        grid.addWidget(self.campo_dewey, 11, 0)
        grid.addWidget(self.campo_claves, 11, 1)
        grid.addWidget(_etiqueta("Sinopsis"), 12, 0)
        grid.addWidget(self.campo_sinopsis, 13, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("formError")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        layout.addLayout(_botones(self, "Guardar libro"))

        self.campo_titulo.setFocus()

    def _cargar(self) -> None:
        if not self._datos:
            return

        self.campo_titulo.setText(self._datos.get("titulo", ""))
        self.campo_subtitulo.setText(self._datos.get("subtitulo", ""))
        self.campo_autores.setText(self._datos.get("autores", ""))
        self.campo_isbn.setText(self._datos.get("isbn", ""))
        self.campo_editorial.setText(self._datos.get("editorial", ""))
        self.campo_anio.setText(str(self._datos.get("anio")) if self._datos.get("anio") else "")
        indice = self.campo_categoria.findData(self._datos.get("categoria") or None)
        self.campo_categoria.setCurrentIndex(max(0, indice))
        self.campo_dewey.setText(self._datos.get("dewey", ""))
        self.campo_claves.setText(self._datos.get("palabras_clave", ""))
        self.campo_sinopsis.setPlainText(self._datos.get("sinopsis", ""))
        for campo in (self.campo_subtitulo, self.campo_autores, self.campo_isbn,
                      self.campo_editorial, self.campo_dewey, self.campo_claves):
            campo.setCursorPosition(0)

    # --------------------------------------------------------------- validacion
    def accept(self) -> None:  # noqa: N802 (API de Qt)
        if not self.campo_titulo.text().strip():
            self._error("El título es obligatorio.")
            return

        isbn = re.sub(r"[^0-9Xx]", "", self.campo_isbn.text())
        if isbn and len(isbn) not in (10, 13):
            self._error("El ISBN debe tener 10 o 13 dígitos (o quedar vacío).")
            return

        super().accept()

    def _error(self, mensaje: str) -> None:
        self.lbl_error.setText(mensaje)
        self.lbl_error.setVisible(True)

    def datos(self) -> dict:
        return {
            "titulo": self.campo_titulo.text().strip(),
            "subtitulo": self.campo_subtitulo.text().strip(),
            "autores": self.campo_autores.text().strip(),
            "isbn": re.sub(r"[^0-9Xx]", "", self.campo_isbn.text()) or None,
            "editorial": self.campo_editorial.text().strip(),
            "anio": int(self.campo_anio.text()) if self.campo_anio.text().strip() else 0,
            "categoria": self.campo_categoria.currentData(),
            "dewey": self.campo_dewey.text().strip(),
            "palabras_clave": self.campo_claves.text().strip(),
            "sinopsis": self.campo_sinopsis.toPlainText().strip(),
        }


class DialogoEjemplar(QDialog):
    """Alta y edición de una copia física."""

    def __init__(
        self,
        datos: dict | None = None,
        codigo_sugerido: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._datos = datos or {}
        self._es_edicion = bool(datos)
        self.setWindowTitle("Editar ejemplar" if self._es_edicion else "Nuevo ejemplar")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._construir(codigo_sugerido)
        self._cargar()

    def _construir(self, codigo_sugerido: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Editar ejemplar" if self._es_edicion else "Nuevo ejemplar")
        titulo.setObjectName("dialogTitle")
        layout.addWidget(titulo)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.campo_codigo = QLineEdit(codigo_sugerido)
        self.campo_codigo.setPlaceholderText("EJ-00001")
        self.campo_ubicacion = QComboBox()
        self.campo_ubicacion.addItem("Sin ubicar", None)
        for ubicacion in servicio_catalogo.listar_ubicaciones():
            self.campo_ubicacion.addItem(
                f"{ubicacion['codigo']}  ·  {ubicacion['detalle']}", ubicacion["id"]
            )
        self.campo_estado = QComboBox()
        for clave, etiqueta in config.ESTADOS_EJEMPLAR.items():
            self.campo_estado.addItem(etiqueta, clave)
        self.campo_condicion = QComboBox()
        for valor, etiqueta in [
            ("bueno", "Bueno"),
            ("regular", "Regular"),
            ("malo", "Deteriorado"),
        ]:
            self.campo_condicion.addItem(etiqueta, valor)
        self.campo_notas = QLineEdit()
        self.campo_notas.setPlaceholderText("Opcional: daños, dedicatorias, etc.")

        grid.addWidget(_etiqueta("Código de inventario *"), 0, 0)
        grid.addWidget(_etiqueta("Ubicación"), 0, 1)
        grid.addWidget(self.campo_codigo, 1, 0)
        grid.addWidget(self.campo_ubicacion, 1, 1)
        grid.addWidget(_etiqueta("Estado"), 2, 0)
        grid.addWidget(_etiqueta("Condición"), 2, 1)
        grid.addWidget(self.campo_estado, 3, 0)
        grid.addWidget(self.campo_condicion, 3, 1)
        grid.addWidget(_etiqueta("Notas"), 4, 0, 1, 2)
        grid.addWidget(self.campo_notas, 5, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("formError")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        layout.addLayout(_botones(self, "Guardar ejemplar"))
        self.campo_codigo.setFocus()

    def _cargar(self) -> None:
        if not self._datos:
            return

        self.campo_codigo.setText(self._datos.get("codigo", ""))
        indice_ubicacion = self.campo_ubicacion.findText(
            self.campo_ubicacion.currentText()
        )
        # La ubicacion llega como codigo; se busca por el texto que empieza igual.
        codigo_ubicacion = self._datos.get("ubicacion", "")
        if codigo_ubicacion:
            for i in range(self.campo_ubicacion.count()):
                if self.campo_ubicacion.itemText(i).startswith(codigo_ubicacion):
                    indice_ubicacion = i
                    break
            self.campo_ubicacion.setCurrentIndex(max(0, indice_ubicacion))

        indice_estado = self.campo_estado.findData(self._datos.get("estado"))
        self.campo_estado.setCurrentIndex(max(0, indice_estado))
        if self._datos.get("estado") == config.EJEMPLAR_PRESTADO:
            self.campo_estado.setEnabled(False)
            self.campo_estado.setToolTip(
                "El estado cambia solo al registrar la devolución."
            )

        indice_cond = self.campo_condicion.findData(self._datos.get("condicion"))
        self.campo_condicion.setCurrentIndex(max(0, indice_cond))
        self.campo_notas.setText(self._datos.get("notas", ""))

    def accept(self) -> None:  # noqa: N802 (API de Qt)
        if not self.campo_codigo.text().strip():
            self.lbl_error.setText("El código de inventario es obligatorio.")
            self.lbl_error.setVisible(True)
            return
        super().accept()

    def datos(self) -> dict:
        return {
            "codigo_inventario": self.campo_codigo.text().strip().upper(),
            "ubicacion_id": self.campo_ubicacion.currentData(),
            "estado": self.campo_estado.currentData(),
            "condicion": self.campo_condicion.currentData(),
            "notas": self.campo_notas.text().strip(),
        }


class DialogoSocio(QDialog):
    """Alta y edición de la ficha de un socio."""

    def __init__(self, datos: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._datos = datos or {}
        self.setWindowTitle("Editar socio" if datos else "Nuevo socio")
        self.setModal(True)
        self.setMinimumWidth(580)
        self._construir()
        self._cargar()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Editar socio" if self._datos else "Nuevo socio")
        titulo.setObjectName("dialogTitle")
        layout.addWidget(titulo)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Apellido, Nombre")
        self.campo_documento = QLineEdit()
        self.campo_documento.setPlaceholderText("Solo números, sin puntos")
        self.campo_documento.setMaxLength(14)
        self.campo_email = QLineEdit()
        self.campo_email.setPlaceholderText("Opcional")
        self.campo_telefono = QLineEdit()
        self.campo_telefono.setPlaceholderText("Opcional")
        self.campo_direccion = QLineEdit()
        self.campo_direccion.setPlaceholderText("Opcional")
        self.campo_tipo = QComboBox()
        for clave, etiqueta in config.TIPOS_SOCIO.items():
            self.campo_tipo.addItem(etiqueta, clave)
        self.campo_estado = QComboBox()
        for clave, etiqueta in config.ESTADOS_SOCIO.items():
            self.campo_estado.addItem(etiqueta, clave)
        self.campo_observaciones = QTextEdit()
        self.campo_observaciones.setPlaceholderText("Opcional: notas internas")
        self.campo_observaciones.setFixedHeight(66)

        self.lbl_regla = QLabel("")
        self.lbl_regla.setObjectName("muted")

        grid.addWidget(_etiqueta("Nombre y apellido *"), 0, 0, 1, 2)
        grid.addWidget(self.campo_nombre, 1, 0, 1, 2)
        grid.addWidget(_etiqueta("Documento *"), 2, 0)
        grid.addWidget(_etiqueta("Email"), 2, 1)
        grid.addWidget(self.campo_documento, 3, 0)
        grid.addWidget(self.campo_email, 3, 1)
        grid.addWidget(_etiqueta("Teléfono"), 4, 0)
        grid.addWidget(_etiqueta("Dirección"), 4, 1)
        grid.addWidget(self.campo_telefono, 5, 0)
        grid.addWidget(self.campo_direccion, 5, 1)
        grid.addWidget(_etiqueta("Tipo de socio"), 6, 0)
        grid.addWidget(_etiqueta("Estado"), 6, 1)
        grid.addWidget(self.campo_tipo, 7, 0)
        grid.addWidget(self.campo_estado, 7, 1)
        grid.addWidget(self.lbl_regla, 8, 0, 1, 2)
        grid.addWidget(_etiqueta("Observaciones"), 9, 0, 1, 2)
        grid.addWidget(self.campo_observaciones, 10, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("formError")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        layout.addLayout(_botones(self, "Guardar socio"))

        self.campo_tipo.currentIndexChanged.connect(self._actualizar_regla)
        self.campo_nombre.setFocus()

    def _actualizar_regla(self) -> None:
        dias = reglas.dias_prestamo(self.campo_tipo.currentData())
        limite = reglas.limite_ejemplares()
        self.lbl_regla.setText(
            f"Préstamo por {dias} días · hasta {limite} ejemplares a la vez"
        )

    def _cargar(self) -> None:
        if not self._datos:
            self._actualizar_regla()
            return

        self.campo_nombre.setText(self._datos.get("nombre", ""))
        self.campo_documento.setText(self._datos.get("documento", ""))
        self.campo_email.setText(self._datos.get("email", ""))
        self.campo_telefono.setText(self._datos.get("telefono", ""))
        self.campo_direccion.setText(self._datos.get("direccion", ""))
        self.campo_observaciones.setPlainText(self._datos.get("observaciones", ""))

        indice_tipo = self.campo_tipo.findData(self._datos.get("tipo"))
        self.campo_tipo.setCurrentIndex(max(0, indice_tipo))

        indice_estado = self.campo_estado.findData(self._datos.get("estado"))
        self.campo_estado.setCurrentIndex(max(0, indice_estado))

        for campo in (
            self.campo_nombre,
            self.campo_documento,
            self.campo_email,
            self.campo_telefono,
            self.campo_direccion,
        ):
            campo.setCursorPosition(0)

        self._actualizar_regla()

    # --------------------------------------------------------------- validacion
    def accept(self) -> None:  # noqa: N802 (API de Qt)
        if len(self.campo_nombre.text().strip()) < 2:
            self._error("El nombre y apellido son obligatorios.")
            return

        documento = re.sub(r"[^0-9]", "", self.campo_documento.text())
        if not 6 <= len(documento) <= 12:
            self._error("El documento debe tener entre 6 y 12 dígitos.")
            return

        email = self.campo_email.text().strip()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            self._error("El email no tiene un formato válido.")
            return

        super().accept()

    def _error(self, mensaje: str) -> None:
        self.lbl_error.setText(mensaje)
        self.lbl_error.setVisible(True)

    def datos(self) -> dict:
        return {
            "nombre": self.campo_nombre.text().strip(),
            "documento": re.sub(r"[^0-9]", "", self.campo_documento.text()),
            "email": self.campo_email.text().strip(),
            "telefono": self.campo_telefono.text().strip(),
            "direccion": self.campo_direccion.text().strip(),
            "tipo": self.campo_tipo.currentData(),
            "estado": self.campo_estado.currentData(),
            "observaciones": self.campo_observaciones.toPlainText().strip(),
        }


class DialogoPrestamo(QDialog):
    """Registro de una salida: socio habilitado + ejemplar disponible."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo préstamo")
        self.setModal(True)
        self.setMinimumWidth(640)
        self._construir()
        self._cargar_opciones()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Nuevo préstamo")
        titulo.setObjectName("dialogTitle")
        layout.addWidget(titulo)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.combo_socio = QComboBox()
        self.combo_socio.setEditable(True)
        self.combo_socio.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_socio.setMinimumContentsLength(46)
        self.combo_socio.lineEdit().setPlaceholderText(
            "Escribí documento o apellido para buscar…"
        )
        self.combo_socio.currentIndexChanged.connect(
            lambda _i: self._actualizar_resumen()
        )

        self.combo_ejemplar = QComboBox()
        self.combo_ejemplar.setEditable(True)
        self.combo_ejemplar.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_ejemplar.setMinimumContentsLength(46)
        self.combo_ejemplar.lineEdit().setPlaceholderText(
            "Escribí el código o el título…"
        )
        self.combo_ejemplar.currentIndexChanged.connect(
            lambda _i: self._actualizar_resumen()
        )

        self.lbl_aviso = QLabel("")
        self.lbl_aviso.setWordWrap(True)

        self.lbl_vencimiento = QLabel("")
        self.lbl_vencimiento.setObjectName("muted")
        self.lbl_vencimiento.setWordWrap(True)

        self.campo_notas = QLineEdit()
        self.campo_notas.setPlaceholderText("Opcional: observaciones del préstamo")

        grid.addWidget(_etiqueta("Socio *"), 0, 0)
        grid.addWidget(self.combo_socio, 1, 0)
        grid.addWidget(_etiqueta("Ejemplar *"), 2, 0)
        grid.addWidget(self.combo_ejemplar, 3, 0)
        grid.addWidget(self.lbl_aviso, 4, 0)
        grid.addWidget(self.lbl_vencimiento, 5, 0)
        grid.addWidget(_etiqueta("Notas"), 6, 0)
        grid.addWidget(self.campo_notas, 7, 0)
        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("formError")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        layout.addLayout(_botones(self, "Registrar préstamo"))
        self.combo_socio.setFocus()

    def _cargar_opciones(self) -> None:
        self.combo_socio.addItem("Elegí un socio…", None)
        for socio in servicio_socios.listar_socios():
            etiqueta = (
                f"{socio['documento']} · {socio['nombre']} ({socio['tipo_legible']})"
            )
            if socio["estado"] != config.SOCIO_ACTIVO:
                etiqueta += f" — {socio['estado_legible']}"
            self.combo_socio.addItem(etiqueta, socio["id"])
        self._preparar_busqueda(self.combo_socio)

        disponibles = servicio_prestamos.ejemplares_disponibles()
        if disponibles:
            self.combo_ejemplar.addItem("Elegí un ejemplar…", None)
            for ejemplar in disponibles:
                self.combo_ejemplar.addItem(
                    f"{ejemplar['codigo']} · {ejemplar['libro']}", ejemplar["id"]
                )
            self._preparar_busqueda(self.combo_ejemplar)
        else:
            self.combo_ejemplar.addItem("No hay ejemplares disponibles", None)
            self.combo_ejemplar.setEnabled(False)

    @staticmethod
    def _preparar_busqueda(combo: QComboBox) -> None:
        """Permite escribir y filtrar en cualquier parte del texto."""
        completador = combo.completer()
        if completador is not None:
            completador.setFilterMode(Qt.MatchFlag.MatchContains)
            completador.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    @staticmethod
    def _seleccion(combo: QComboBox) -> int | None:
        """Id del ítem elegido; None si se escribió texto sin elegir."""
        indice = combo.currentIndex()
        if indice < 0:
            return None
        if combo.isEditable() and combo.currentText() != combo.itemText(indice):
            return None
        dato = combo.currentData()
        return int(dato) if dato is not None else None

    def _actualizar_resumen(self) -> None:
        self.lbl_aviso.setText("")
        self.lbl_aviso.setStyleSheet("")
        self.lbl_vencimiento.setText("")

        socio_id = self._seleccion(self.combo_socio)
        if socio_id is None:
            return

        situacion = servicio_socios.situacion(socio_id)
        if situacion is None:
            return

        color = {
            "exito": theme.EXITO,
            "aviso": theme.ADVERTENCIA,
            "peligro": theme.PELIGRO,
        }.get(situacion["tono"], theme.TEXTO_SUAVE)
        self.lbl_aviso.setStyleSheet(f"color: {color};")
        self.lbl_aviso.setText(situacion["motivo"])

        vence = date.today() + timedelta(days=situacion["dias"])
        self.lbl_vencimiento.setText(
            f"Vence el {vence:%d/%m/%Y} · {situacion['dias']} días de préstamo · "
            f"{situacion['activos']} de {situacion['limite']} ejemplares en préstamo"
        )

    def accept(self) -> None:  # noqa: N802 (API de Qt)
        socio_id = self._seleccion(self.combo_socio)
        if socio_id is None:
            self._error("Elegí un socio de la lista.")
            return

        if self._seleccion(self.combo_ejemplar) is None:
            self._error("Elegí un ejemplar disponible de la lista.")
            return

        situacion = servicio_socios.situacion(socio_id)
        if situacion is not None and not situacion["puede"]:
            self._error(situacion["motivo"])
            return

        super().accept()

    def _error(self, mensaje: str) -> None:
        self.lbl_error.setText(mensaje)
        self.lbl_error.setVisible(True)

    def datos(self) -> dict:
        return {
            "socio_id": self._seleccion(self.combo_socio),
            "ejemplar_id": self._seleccion(self.combo_ejemplar),
            "notas": self.campo_notas.text().strip(),
        }

    def descripcion(self) -> str:
        """Texto breve para la auditoría."""
        return f"{self.combo_ejemplar.currentText()} → {self.combo_socio.currentText()}"


class DialogoDevolucion(QDialog):
    """Cierre de un préstamo y estado en que queda el ejemplar."""

    def __init__(self, prestamo: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prestamo = prestamo
        self.setWindowTitle("Registrar devolución")
        self.setModal(True)
        self.setMinimumWidth(540)
        self._construir()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Registrar devolución")
        titulo.setObjectName("dialogTitle")
        layout.addWidget(titulo)

        detalle = QLabel(
            f"{self._prestamo['libro']}\n"
            f"{self._prestamo['ejemplar']} · {self._prestamo['socio']} "
            f"({self._prestamo['documento']})"
        )
        detalle.setWordWrap(True)
        layout.addWidget(detalle)

        vence = self._prestamo["vence"]
        self.lbl_estado = QLabel(
            f"Prestado desde el {self._prestamo['desde']:%d/%m/%Y} · "
            f"vence el {vence:%d/%m/%Y}"
        )
        self.lbl_estado.setObjectName("muted")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        atraso = self._prestamo["atraso"]
        if atraso:
            self.lbl_atraso = QLabel(
                f"Devuelve con {atraso} día(s) de atraso."
            )
            self.lbl_atraso.setStyleSheet(f"color: {theme.PELIGRO};")
            self.lbl_atraso.setWordWrap(True)
            layout.addWidget(self.lbl_atraso)

        layout.addWidget(_etiqueta("Estado del ejemplar al volver"))
        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Disponible para prestar", config.EJEMPLAR_DISPONIBLE)
        self.combo_estado.addItem("En reparación", config.EJEMPLAR_REPARACION)
        layout.addWidget(self.combo_estado)

        nota = QLabel(
            "La devolución cierra el préstamo y levanta el bloqueo del socio. "
            "Si el ejemplar queda en reparación, no vuelve al estante."
        )
        nota.setObjectName("muted")
        nota.setWordWrap(True)
        layout.addWidget(nota)

        layout.addLayout(_botones(self, "Registrar devolución"))

    def estado_ejemplar(self) -> str:
        return self.combo_estado.currentData()


class DialogoPerdido(QDialog):
    """Cierre de un préstamo como perdido y multa para el socio."""

    def __init__(self, prestamo: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prestamo = prestamo
        self.setWindowTitle("Marcar ejemplar perdido")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._construir()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Marcar ejemplar perdido")
        titulo.setObjectName("dialogTitle")
        layout.addWidget(titulo)

        detalle = QLabel(
            f"{self._prestamo['libro']}\n"
            f"{self._prestamo['ejemplar']} · {self._prestamo['socio']} "
            f"({self._prestamo['documento']})"
        )
        detalle.setWordWrap(True)
        layout.addWidget(detalle)

        vence = self._prestamo["vence"]
        lbl_estado = QLabel(
            f"Prestado desde el {self._prestamo['desde']:%d/%m/%Y} · "
            f"vence el {vence:%d/%m/%Y}"
        )
        lbl_estado.setObjectName("muted")
        lbl_estado.setWordWrap(True)
        layout.addWidget(lbl_estado)

        aviso = QLabel(
            "El préstamo se cerrará como perdido y el ejemplar saldrá del "
            "inventario. Si se genera una multa, el socio no podrá retirar "
            "material hasta que la pague o la anule."
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        deuda = servicio_multas.deuda_pendiente(self._prestamo["socio_id"])
        if deuda["cantidad"]:
            plural = "multa pendiente" if deuda["cantidad"] == 1 else "multas pendientes"
            lbl_deuda = QLabel(
                f"El socio ya tiene {deuda['cantidad']} {plural} por "
                f"{deuda['total']}."
            )
            lbl_deuda.setStyleSheet(f"color: {theme.ADVERTENCIA};")
            lbl_deuda.setWordWrap(True)
            layout.addWidget(lbl_deuda)

        layout.addWidget(_etiqueta("Monto de la multa"))
        self.campo_monto = QDoubleSpinBox()
        self.campo_monto.setLocale(QLocale("es_AR"))
        self.campo_monto.setDecimals(2)
        self.campo_monto.setRange(0, 10_000_000)
        self.campo_monto.setSingleStep(500)
        self.campo_monto.setPrefix("$ ")
        self.campo_monto.setGroupSeparatorShown(True)
        self.campo_monto.setValue(reglas.multa_perdida_centavos() / 100)
        layout.addWidget(self.campo_monto)

        self.lbl_monto = QLabel(
            f"Sugerido: {servicio_multas.formatear_monto(reglas.multa_perdida_centavos())} "
            "· Dejá 0 para no generar multa."
        )
        self.lbl_monto.setObjectName("muted")
        self.lbl_monto.setWordWrap(True)
        layout.addWidget(self.lbl_monto)

        layout.addWidget(_etiqueta("Notas"))
        self.campo_notas = QLineEdit()
        self.campo_notas.setPlaceholderText("Opcional: circunstancias de la pérdida")
        layout.addWidget(self.campo_notas)

        layout.addLayout(_botones(self, "Marcar perdido"))
        self.campo_monto.setFocus()

    def monto_centavos(self) -> int:
        return int(round(self.campo_monto.value() * 100))

    def notas(self) -> str:
        return self.campo_notas.text().strip()


class DialogoRecuperado(QDialog):
    """Reingreso de un ejemplar que se había dado por perdido."""

    def __init__(self, prestamo: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prestamo = prestamo
        self.setWindowTitle("Marcar ejemplar recuperado")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._construir()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Marcar ejemplar recuperado")
        titulo.setObjectName("dialogTitle")
        layout.addWidget(titulo)

        detalle = QLabel(
            f"{self._prestamo['libro']}\n"
            f"{self._prestamo['ejemplar']} · {self._prestamo['socio']} "
            f"({self._prestamo['documento']})"
        )
        detalle.setWordWrap(True)
        layout.addWidget(detalle)

        perdido_el = self._prestamo.get("devuelto")
        lbl_estado = QLabel(
            f"Prestado desde el {self._prestamo['desde']:%d/%m/%Y} · "
            f"marcado perdido el {perdido_el:%d/%m/%Y}"
            if perdido_el
            else f"Prestado desde el {self._prestamo['desde']:%d/%m/%Y}"
        )
        lbl_estado.setObjectName("muted")
        lbl_estado.setWordWrap(True)
        layout.addWidget(lbl_estado)

        aviso = QLabel(
            "El préstamo pasará a figurar como recuperado. Se anularán las "
            "multas pendientes de esta pérdida y quedará una advertencia en "
            "la ficha del socio."
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        pendientes = servicio_multas.listar_multas(
            prestamo_id=self._prestamo["id"],
            estado=config.MULTA_PENDIENTE,
        )
        if pendientes:
            total = sum(multa["monto_centavos"] for multa in pendientes)
            plural = "multa pendiente" if len(pendientes) == 1 else "multas pendientes"
            lbl_multas = QLabel(
                f"Se anulará {len(pendientes)} {plural} por "
                f"{servicio_multas.formatear_monto(total)}."
            )
            lbl_multas.setStyleSheet(f"color: {theme.ADVERTENCIA};")
            lbl_multas.setWordWrap(True)
            layout.addWidget(lbl_multas)
        else:
            lbl_sin = QLabel("Este préstamo no tiene multas pendientes.")
            lbl_sin.setObjectName("muted")
            lbl_sin.setWordWrap(True)
            layout.addWidget(lbl_sin)

        pagadas = servicio_multas.listar_multas(
            prestamo_id=self._prestamo["id"],
            estado=config.MULTA_PAGADA,
        )
        if pagadas:
            lbl_pagada = QLabel(
                "La multa de esta pérdida ya fue pagada: no se reintegra."
            )
            lbl_pagada.setObjectName("muted")
            lbl_pagada.setWordWrap(True)
            layout.addWidget(lbl_pagada)

        layout.addWidget(_etiqueta("Estado del ejemplar al recuperarlo"))
        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Disponible para prestar", config.EJEMPLAR_DISPONIBLE)
        self.combo_estado.addItem("En reparación", config.EJEMPLAR_REPARACION)
        layout.addWidget(self.combo_estado)

        nota = QLabel(
            "La advertencia se conserva en la ficha del socio aunque la multa "
            "se anule."
        )
        nota.setObjectName("muted")
        nota.setWordWrap(True)
        layout.addWidget(nota)

        layout.addLayout(_botones(self, "Marcar recuperado"))

    def estado_ejemplar(self) -> str:
        return self.combo_estado.currentData()
