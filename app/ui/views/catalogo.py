"""Pantalla de catalogo: libros, ejemplares y ubicaciones."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.services import catalogo as servicio
from app.services.auth import registrar_movimiento
from app.ui import theme
from app.ui.widgets.cards import EtiquetaEstado
from app.ui.widgets.dialogos import DialogoEjemplar, DialogoLibro


class CatalogoPage(QWidget):
    """Listado de libros con ficha lateral y gestion de ejemplares."""

    COLUMNAS = ["Título", "Autor", "Categoría", "Ej.", "Disp."]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._libro_id: int | None = None
        self._ejemplares: list[dict] = []

        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.setInterval(180)
        self._temporizador.timeout.connect(self._cargar_tabla)

        self._construir()

    # ------------------------------------------------------------------ UI
    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 18, 26, 16)
        layout.setSpacing(12)

        layout.addLayout(self._barra_herramientas())

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        divisor.addWidget(self._tabla_libros())
        divisor.addWidget(self._panel_detalle())
        divisor.setStretchFactor(0, 3)
        divisor.setStretchFactor(1, 2)
        divisor.setSizes([700, 420])
        layout.addWidget(divisor, 1)

        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setObjectName("muted")
        layout.addWidget(self.lbl_resumen)

    def _barra_herramientas(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(10)

        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText(
            "Buscar por título, autor, ISBN, editorial o tema…"
        )
        self.buscador.setClearButtonEnabled(True)
        self.buscador.textChanged.connect(lambda _t: self._temporizador.start())
        self.buscador.setMinimumWidth(320)

        self.combo_categoria = QComboBox()
        self.combo_categoria.addItem("Todas las categorías", None)
        for categoria in servicio.listar_categorias():
            self.combo_categoria.addItem(categoria, categoria)
        self.combo_categoria.currentIndexChanged.connect(lambda _i: self._cargar_tabla())
        self.combo_categoria.setMinimumWidth(170)

        self.chk_disponibles = QCheckBox("Solo con ejemplares disponibles")
        self.chk_disponibles.stateChanged.connect(lambda _e: self._cargar_tabla())

        boton = QPushButton("+  Nuevo libro")
        boton.setObjectName("primaryButton")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.clicked.connect(self._nuevo_libro)

        fila.addWidget(self.buscador, 1)
        fila.addWidget(self.combo_categoria)
        fila.addWidget(self.chk_disponibles)
        fila.addWidget(boton)
        return fila

    def _tabla_libros(self) -> QWidget:
        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.verticalHeader().setDefaultSectionSize(36)

        cabecera = self.tabla.horizontalHeader()
        cabecera.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setHighlightSections(False)

        self.tabla.itemSelectionChanged.connect(self._al_seleccionar)
        self.tabla.doubleClicked.connect(lambda _i: self._editar_libro())
        return self.tabla

    def _panel_detalle(self) -> QWidget:
        tarjeta = QFrame()
        tarjeta.setObjectName("card")

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(0)

        self.pila_detalle = QStackedWidget()
        self.pila_detalle.addWidget(self._detalle_vacio())
        self.pila_detalle.addWidget(self._detalle_ficha())
        layout.addWidget(self.pila_detalle)
        return tarjeta

    def _detalle_vacio(self) -> QWidget:
        caja = QWidget()
        layout = QVBoxLayout(caja)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titulo = QLabel("Seleccioná un libro")
        titulo.setObjectName("sectionTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detalle = QLabel("Vas a ver sus datos, la ubicación de cada\nejemplar y su disponibilidad.")
        detalle.setObjectName("emptyState")
        detalle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(titulo)
        layout.addWidget(detalle)
        return caja

    def _detalle_ficha(self) -> QWidget:
        caja = QWidget()
        layout = QVBoxLayout(caja)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.lbl_titulo = QLabel("")
        self.lbl_titulo.setObjectName("sectionTitle")
        self.lbl_titulo.setWordWrap(True)

        self.lbl_autores = QLabel("")
        self.lbl_autores.setObjectName("muted")
        self.lbl_autores.setWordWrap(True)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("muted")
        self.lbl_meta.setWordWrap(True)

        self.lbl_isbn = QLabel("")
        self.lbl_isbn.setObjectName("muted")

        layout.addWidget(self.lbl_titulo)
        layout.addWidget(self.lbl_autores)
        layout.addWidget(self.lbl_meta)
        layout.addWidget(self.lbl_isbn)
        layout.addSpacing(8)

        self.lbl_sinopsis = QLabel("")
        self.lbl_sinopsis.setObjectName("muted")
        self.lbl_sinopsis.setWordWrap(True)
        self.lbl_sinopsis.setMaximumHeight(96)
        layout.addWidget(self.lbl_sinopsis)
        layout.addSpacing(10)

        cabecera = QHBoxLayout()
        etiqueta = QLabel("Ejemplares")
        etiqueta.setObjectName("fieldLabel")
        self.lbl_conteo = QLabel("")
        self.lbl_conteo.setObjectName("muted")
        cabecera.addWidget(etiqueta)
        cabecera.addWidget(self.lbl_conteo)
        cabecera.addStretch(1)
        layout.addLayout(cabecera)
        layout.addSpacing(4)

        self.tabla_ejemplares = QTableWidget(0, 3)
        self.tabla_ejemplares.setHorizontalHeaderLabels(["Código", "Ubicación", "Estado"])
        self.tabla_ejemplares.verticalHeader().setVisible(False)
        self.tabla_ejemplares.setShowGrid(False)
        self.tabla_ejemplares.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabla_ejemplares.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabla_ejemplares.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabla_ejemplares.verticalHeader().setDefaultSectionSize(32)
        cab_ej = self.tabla_ejemplares.horizontalHeader()
        cab_ej.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cab_ej.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cab_ej.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        cab_ej.setHighlightSections(False)
        self.tabla_ejemplares.setColumnWidth(2, 116)
        self.tabla_ejemplares.doubleClicked.connect(lambda _i: self._editar_ejemplar())

        layout.addWidget(self.tabla_ejemplares, 1)
        layout.addSpacing(10)

        acciones = QHBoxLayout()
        acciones.setSpacing(8)

        self.btn_editar = QPushButton("Editar libro")
        self.btn_editar.setObjectName("ghostButton")
        self.btn_editar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_editar.clicked.connect(self._editar_libro)

        self.btn_ejemplar = QPushButton("+  Agregar ejemplar")
        self.btn_ejemplar.setObjectName("primaryButton")
        self.btn_ejemplar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ejemplar.clicked.connect(self._nuevo_ejemplar)

        acciones.addWidget(self.btn_editar)
        acciones.addWidget(self.btn_ejemplar)
        acciones.addStretch(1)
        layout.addLayout(acciones)

        return caja

    # ------------------------------------------------------------- refrescos
    def refrescar(self) -> None:
        """Recarga todo respetando el filtro y la selección actual."""
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        libros = servicio.listar_libros(
            busqueda=self.buscador.text(),
            categoria=self.combo_categoria.currentData(),
            solo_disponibles=self.chk_disponibles.isChecked(),
        )

        anterior = self._libro_id
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        self.tabla.setRowCount(len(libros))
        fila_anterior = -1

        for fila, libro in enumerate(libros):
            titulo = QTableWidgetItem(libro["titulo"])
            titulo.setData(Qt.ItemDataRole.UserRole, libro["id"])
            if libro["anio"]:
                titulo.setToolTip(f"{libro['titulo']} ({libro['anio']})")

            autor = QTableWidgetItem(libro["autores"])
            categoria = QTableWidgetItem(libro["categoria"])
            total = QTableWidgetItem(str(libro["ejemplares"]))
            disponibles = QTableWidgetItem(str(libro["disponibles"]))

            for item in (total, disponibles):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if libro["disponibles"] == 0:
                disponibles.setForeground(Qt.GlobalColor.gray)
            else:
                disponibles.setForeground(Qt.GlobalColor.darkGreen)

            self.tabla.setItem(fila, 0, titulo)
            self.tabla.setItem(fila, 1, autor)
            self.tabla.setItem(fila, 2, categoria)
            self.tabla.setItem(fila, 3, total)
            self.tabla.setItem(fila, 4, disponibles)

            if libro["id"] == anterior:
                fila_anterior = fila

        self.tabla.blockSignals(False)

        if not libros:
            self._libro_id = None
            self.pila_detalle.setCurrentIndex(0)
        elif fila_anterior >= 0:
            self.tabla.selectRow(fila_anterior)
        else:
            self.tabla.selectRow(0)

        self._actualizar_resumen(len(libros))

    def _actualizar_resumen(self, visibles: int) -> None:
        stats = servicio.estadisticas()
        texto = (
            f"{visibles} título(s) a la vista   ·   "
            f"{stats['libros']} en catálogo   ·   "
            f"{stats['ejemplares']} ejemplares   ·   "
            f"{stats['disponibles']} disponibles"
        )
        self.lbl_resumen.setText(texto)

    # ------------------------------------------------------------- seleccion
    def _al_seleccionar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return

        item = self.tabla.item(filas[0].row(), 0)
        if item is None:
            return

        libro_id = item.data(Qt.ItemDataRole.UserRole)
        if libro_id is None:
            return

        self._libro_id = int(libro_id)
        self._cargar_detalle()

    def _cargar_detalle(self) -> None:
        if self._libro_id is None:
            self.pila_detalle.setCurrentIndex(0)
            return

        detalle = servicio.obtener_libro(self._libro_id)
        if detalle is None:
            self._libro_id = None
            self.pila_detalle.setCurrentIndex(0)
            return

        self.pila_detalle.setCurrentIndex(1)

        titulo = detalle["titulo"]
        if detalle["subtitulo"]:
            titulo = f"{titulo}. {detalle['subtitulo']}"
        self.lbl_titulo.setText(titulo)

        self.lbl_autores.setText(detalle["autores"] or "Autor sin registrar")

        partes = []
        if detalle["categoria"]:
            partes.append(detalle["categoria"])
        if detalle["anio"]:
            partes.append(str(detalle["anio"]))
        if detalle["editorial"]:
            partes.append(detalle["editorial"])
        if detalle["dewey"]:
            partes.append(f"Dewey {detalle['dewey']}")
        self.lbl_meta.setText("   ·   ".join(partes) or "Sin datos editoriales")

        self.lbl_isbn.setText(f"ISBN {detalle['isbn']}" if detalle["isbn"] else "ISBN sin registrar")
        self.lbl_sinopsis.setText(detalle["sinopsis"] or "")
        self.lbl_sinopsis.setVisible(bool(detalle["sinopsis"]))

        self._ejemplares = detalle["ejemplares"]
        disponibles = sum(
            1
            for e in self._ejemplares
            if e["estado"] == config.EJEMPLAR_DISPONIBLE
        )
        self.lbl_conteo.setText(
            f"{len(self._ejemplares)} en total, {disponibles} disponibles"
        )

        self.tabla_ejemplares.setRowCount(0)
        self.tabla_ejemplares.setRowCount(len(self._ejemplares))
        for fila, ejemplar in enumerate(self._ejemplares):
            codigo = QTableWidgetItem(ejemplar["codigo"])
            codigo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla_ejemplares.setItem(fila, 0, codigo)

            # El código de sala se centra bajo su encabezado: si la columna se
            # estira, un valor corto pegado a la izquierda parece pertenecer a
            # la columna anterior. El detalle completo queda en el tooltip.
            ubicacion = QTableWidgetItem(ejemplar["ubicacion"] or "—")
            ubicacion.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ubicacion.setToolTip(ejemplar["ubicacion_detalle"])
            self.tabla_ejemplares.setItem(fila, 1, ubicacion)

            estado = EtiquetaEstado(
                config.ESTADOS_EJEMPLAR.get(ejemplar["estado"], ejemplar["estado"]),
                self._tono_estado(ejemplar["estado"]),
            )
            self.tabla_ejemplares.setCellWidget(fila, 2, estado)

        self.btn_editar.setEnabled(True)
        self.btn_ejemplar.setEnabled(True)

    @staticmethod
    def _tono_estado(estado: str) -> str:
        if estado == config.EJEMPLAR_DISPONIBLE:
            return "exito"
        if estado == config.EJEMPLAR_PRESTADO:
            return "aviso"
        if estado in (config.EJEMPLAR_PERDIDO,):
            return "peligro"
        return "neutro"

    # --------------------------------------------------------------- acciones
    def _nuevo_libro(self) -> None:
        dialogo = DialogoLibro(parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        ok, mensaje, libro_id = servicio.crear_libro(dialogo.datos())
        if not ok:
            QMessageBox.warning(self, "No se pudo guardar", mensaje)
            return

        registrar_movimiento(
            "alta_libro", "libro", libro_id, dialogo.datos().get("titulo")
        )
        self._libro_id = libro_id
        self._cargar_tabla()
        self._ofrecer_primer_ejemplar(libro_id)

    def _ofrecer_primer_ejemplar(self, libro_id: int) -> None:
        respuesta = QMessageBox.question(
            self,
            "Libro creado",
            "El libro se guardó sin ejemplares.\n¿Querés agregar la primera copia ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self._nuevo_ejemplar()

    def _editar_libro(self) -> None:
        if self._libro_id is None:
            return

        detalle = servicio.obtener_libro(self._libro_id)
        if detalle is None:
            return

        dialogo = DialogoLibro(datos=detalle, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        ok, mensaje = servicio.actualizar_libro(self._libro_id, dialogo.datos())
        if not ok:
            QMessageBox.warning(self, "No se pudo guardar", mensaje)
            return

        registrar_movimiento(
            "edicion_libro", "libro", self._libro_id, dialogo.datos().get("titulo")
        )
        self._cargar_tabla()

    def _nuevo_ejemplar(self) -> None:
        if self._libro_id is None:
            return

        dialogo = DialogoEjemplar(
            codigo_sugerido=servicio.siguiente_codigo_inventario(), parent=self
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        ok, mensaje, ejemplar_id = servicio.agregar_ejemplar(
            self._libro_id, dialogo.datos()
        )
        if not ok:
            QMessageBox.warning(self, "No se pudo guardar", mensaje)
            return

        registrar_movimiento(
            "alta_ejemplar",
            "ejemplar",
            ejemplar_id,
            dialogo.datos().get("codigo_inventario"),
        )
        self._cargar_tabla()

    def _editar_ejemplar(self) -> None:
        filas = self.tabla_ejemplares.selectionModel().selectedRows()
        if not filas:
            return

        indice = filas[0].row()
        if not 0 <= indice < len(self._ejemplares):
            return

        ejemplar = self._ejemplares[indice]
        dialogo = DialogoEjemplar(datos=ejemplar, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        ok, mensaje = servicio.actualizar_ejemplar(ejemplar["id"], dialogo.datos())
        if not ok:
            QMessageBox.warning(self, "No se pudo guardar", mensaje)
            return

        registrar_movimiento(
            "edicion_ejemplar", "ejemplar", ejemplar["id"], ejemplar["codigo"]
        )
        self._cargar_tabla()
