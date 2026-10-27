"""Pantalla de socios: fichas, situación e historial de préstamos."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
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
from app.services import multas as servicio_multas
from app.services import socios as servicio
from app.services.auth import registrar_movimiento
from app.ui import theme
from app.ui.widgets.cards import EtiquetaEstado
from app.ui.widgets.dialogos import DialogoSocio


class SociosPage(QWidget):
    """Listado de socios con ficha lateral e historial."""

    COLUMNAS = ["Nombre", "Documento", "Tipo", "Estado", "Activos", "Vencidos", "Multas"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._socio_id: int | None = None
        self._historial: list[dict] = []
        self._multas: list[dict] = []
        self._multa_id: int | None = None

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
        divisor.addWidget(self._tabla_socios())
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
            "Buscar por nombre, documento, email o teléfono…"
        )
        self.buscador.setClearButtonEnabled(True)
        self.buscador.textChanged.connect(lambda _t: self._temporizador.start())
        self.buscador.setMinimumWidth(300)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Todos los tipos", None)
        for clave, etiqueta in config.TIPOS_SOCIO.items():
            self.combo_tipo.addItem(etiqueta, clave)
        self.combo_tipo.currentIndexChanged.connect(lambda _i: self._cargar_tabla())
        self.combo_tipo.setMinimumWidth(150)

        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todos los estados", None)
        for clave, etiqueta in config.ESTADOS_SOCIO.items():
            self.combo_estado.addItem(etiqueta, clave)
        self.combo_estado.currentIndexChanged.connect(lambda _i: self._cargar_tabla())
        self.combo_estado.setMinimumWidth(160)

        self.chk_vencidos = QCheckBox("Solo con vencidos")
        self.chk_vencidos.stateChanged.connect(lambda _e: self._cargar_tabla())

        boton = QPushButton("+  Nuevo socio")
        boton.setObjectName("primaryButton")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.clicked.connect(self._nuevo_socio)

        fila.addWidget(self.buscador, 1)
        fila.addWidget(self.combo_tipo)
        fila.addWidget(self.combo_estado)
        fila.addWidget(self.chk_vencidos)
        fila.addWidget(boton)
        return fila

    def _tabla_socios(self) -> QWidget:
        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setDefaultSectionSize(36)

        cabecera = self.tabla.horizontalHeader()
        cabecera.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        cabecera.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        cabecera.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        cabecera.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(3, 112)
        self.tabla.setColumnWidth(4, 74)
        self.tabla.setColumnWidth(5, 84)
        self.tabla.setColumnWidth(6, 68)
        cabecera.setHighlightSections(False)

        self.tabla.itemSelectionChanged.connect(self._al_seleccionar)
        self.tabla.doubleClicked.connect(lambda _i: self._editar_socio())
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

        titulo = QLabel("Seleccioná un socio")
        titulo.setObjectName("sectionTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detalle = QLabel(
            "Vas a ver sus datos de contacto, su situación\ny el historial de préstamos."
        )
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

        self.lbl_nombre = QLabel("")
        self.lbl_nombre.setObjectName("sectionTitle")
        self.lbl_nombre.setWordWrap(True)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("muted")
        self.lbl_meta.setWordWrap(True)

        fila_badge = QHBoxLayout()
        fila_badge.setContentsMargins(0, 2, 0, 2)
        self.badge_estado = EtiquetaEstado("", "neutro")
        fila_badge.addWidget(self.badge_estado)
        fila_badge.addStretch(1)

        self.aviso = QFrame()
        self.aviso.setObjectName("aviso")
        aviso_layout = QHBoxLayout(self.aviso)
        aviso_layout.setContentsMargins(12, 8, 12, 8)
        self.lbl_aviso = QLabel("")
        self.lbl_aviso.setObjectName("avisoTexto")
        self.lbl_aviso.setWordWrap(True)
        aviso_layout.addWidget(self.lbl_aviso)

        self.aviso_advertencia = QFrame()
        self.aviso_advertencia.setObjectName("aviso")
        self.aviso_advertencia.setProperty("tono", "aviso")
        advertencia_layout = QHBoxLayout(self.aviso_advertencia)
        advertencia_layout.setContentsMargins(12, 8, 12, 8)
        self.lbl_advertencia = QLabel("")
        self.lbl_advertencia.setObjectName("avisoTexto")
        self.lbl_advertencia.setWordWrap(True)
        advertencia_layout.addWidget(self.lbl_advertencia)
        self.aviso_advertencia.setVisible(False)

        self.lbl_contacto = QLabel("")
        self.lbl_contacto.setObjectName("muted")
        self.lbl_contacto.setWordWrap(True)

        layout.addWidget(self.lbl_nombre)
        layout.addWidget(self.lbl_meta)
        layout.addLayout(fila_badge)
        layout.addWidget(self.aviso)
        layout.addWidget(self.aviso_advertencia)
        layout.addWidget(self.lbl_contacto)
        layout.addSpacing(8)

        cabecera = QHBoxLayout()
        etiqueta = QLabel("Historial de préstamos")
        etiqueta.setObjectName("fieldLabel")
        self.lbl_historial = QLabel("")
        self.lbl_historial.setObjectName("muted")
        cabecera.addWidget(etiqueta)
        cabecera.addWidget(self.lbl_historial)
        cabecera.addStretch(1)
        layout.addLayout(cabecera)
        layout.addSpacing(4)

        self.tabla_historial = QTableWidget(0, 2)
        self.tabla_historial.setHorizontalHeaderLabels(["Libro", "Estado"])
        self.tabla_historial.verticalHeader().setVisible(False)
        self.tabla_historial.setShowGrid(False)
        self.tabla_historial.setWordWrap(True)
        self.tabla_historial.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabla_historial.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabla_historial.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabla_historial.verticalHeader().setDefaultSectionSize(48)

        cab_hist = self.tabla_historial.horizontalHeader()
        cab_hist.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cab_hist.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tabla_historial.setColumnWidth(1, 100)
        cab_hist.setHighlightSections(False)

        layout.addWidget(self.tabla_historial, 1)

        self.lbl_sin_historial = QLabel("Sin préstamos registrados.")
        self.lbl_sin_historial.setObjectName("muted")
        self.lbl_sin_historial.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sin_historial.setVisible(False)
        layout.addWidget(self.lbl_sin_historial, 1)

        layout.addSpacing(8)

        cabecera_multas = QHBoxLayout()
        etiqueta_multas = QLabel("Multas")
        etiqueta_multas.setObjectName("fieldLabel")
        self.lbl_multas = QLabel("")
        self.lbl_multas.setObjectName("muted")
        cabecera_multas.addWidget(etiqueta_multas)
        cabecera_multas.addWidget(self.lbl_multas)
        cabecera_multas.addStretch(1)
        layout.addLayout(cabecera_multas)
        layout.addSpacing(4)

        self.tabla_multas = QTableWidget(0, 3)
        self.tabla_multas.horizontalHeader().setVisible(False)
        self.tabla_multas.verticalHeader().setVisible(False)
        self.tabla_multas.setShowGrid(False)
        self.tabla_multas.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabla_multas.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabla_multas.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabla_multas.setWordWrap(False)
        self.tabla_multas.verticalHeader().setDefaultSectionSize(44)

        cab_multas = self.tabla_multas.horizontalHeader()
        cab_multas.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cab_multas.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        cab_multas.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tabla_multas.setColumnWidth(1, 104)
        self.tabla_multas.setColumnWidth(2, 88)
        cab_multas.setHighlightSections(False)

        self.tabla_multas.itemSelectionChanged.connect(self._al_seleccionar_multa)
        layout.addWidget(self.tabla_multas)

        acciones_multas = QHBoxLayout()
        acciones_multas.setSpacing(8)

        self.btn_pagar = QPushButton("Registrar pago")
        self.btn_pagar.setObjectName("ghostButton")
        self.btn_pagar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pagar.setEnabled(False)
        self.btn_pagar.clicked.connect(self._registrar_pago_multa)

        self.btn_anular_multa = QPushButton("Anular multa")
        self.btn_anular_multa.setObjectName("dangerGhostButton")
        self.btn_anular_multa.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_anular_multa.setEnabled(False)
        self.btn_anular_multa.clicked.connect(self._anular_multa)

        acciones_multas.addWidget(self.btn_pagar)
        acciones_multas.addWidget(self.btn_anular_multa)
        acciones_multas.addStretch(1)
        layout.addLayout(acciones_multas)

        layout.addSpacing(10)

        acciones = QHBoxLayout()
        acciones.setSpacing(8)

        self.btn_editar = QPushButton("Editar socio")
        self.btn_editar.setObjectName("ghostButton")
        self.btn_editar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_editar.clicked.connect(self._editar_socio)

        self.btn_estado = QPushButton("Suspender")
        self.btn_estado.setObjectName("ghostButton")
        self.btn_estado.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_estado.clicked.connect(self._cambiar_estado)

        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.setObjectName("dangerGhostButton")
        self.btn_eliminar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_eliminar.clicked.connect(self._eliminar_socio)

        acciones.addWidget(self.btn_editar)
        acciones.addWidget(self.btn_estado)
        acciones.addStretch(1)
        acciones.addWidget(self.btn_eliminar)
        layout.addLayout(acciones)

        return caja

    # ------------------------------------------------------------- refrescos
    def refrescar(self) -> None:
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        socios = servicio.listar_socios(
            busqueda=self.buscador.text(),
            tipo=self.combo_tipo.currentData(),
            estado=self.combo_estado.currentData(),
            solo_vencidos=self.chk_vencidos.isChecked(),
        )

        anterior = self._socio_id
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        self.tabla.setRowCount(len(socios))
        fila_anterior = -1

        for fila, socio in enumerate(socios):
            nombre = QTableWidgetItem(socio["nombre"])
            nombre.setData(Qt.ItemDataRole.UserRole, socio["id"])
            detalles = []
            if socio["email"]:
                detalles.append(socio["email"])
            if socio["advertencias"]:
                plural = (
                    "advertencia" if socio["advertencias"] == 1 else "advertencias"
                )
                detalles.append(
                    f"{socio['advertencias']} {plural} en la ficha"
                )
            if detalles:
                nombre.setToolTip("\n".join(detalles))

            documento = QTableWidgetItem(socio["documento"])
            tipo = QTableWidgetItem(socio["tipo_legible"])
            activos = QTableWidgetItem(str(socio["activos"]))
            vencidos = QTableWidgetItem(str(socio["vencidos"]))
            multas = QTableWidgetItem(str(socio["multas"]))

            for item in (activos, vencidos, multas):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            vencidos.setForeground(
                QColor(theme.PELIGRO)
                if socio["vencidos"]
                else QColor(theme.TEXTO_TENUE)
            )
            multas.setForeground(
                QColor(theme.PELIGRO)
                if socio["multas"]
                else QColor(theme.TEXTO_TENUE)
            )
            multas.setToolTip(
                "Multa(s) pendiente(s) de pago"
                if socio["multas"]
                else "Sin multas pendientes"
            )

            self.tabla.setItem(fila, 0, nombre)
            self.tabla.setItem(fila, 1, documento)
            self.tabla.setItem(fila, 2, tipo)
            self.tabla.setCellWidget(
                fila,
                3,
                EtiquetaEstado(
                    socio["estado_legible"], self._tono_estado(socio["estado"])
                ),
            )
            self.tabla.setItem(fila, 4, activos)
            self.tabla.setItem(fila, 5, vencidos)
            self.tabla.setItem(fila, 6, multas)

            if socio["id"] == anterior:
                fila_anterior = fila

        self.tabla.blockSignals(False)

        if not socios:
            self._socio_id = None
            self.pila_detalle.setCurrentIndex(0)
        elif fila_anterior >= 0:
            self.tabla.selectRow(fila_anterior)
        else:
            self.tabla.selectRow(0)

        self._actualizar_resumen(len(socios))

    def _actualizar_resumen(self, visibles: int) -> None:
        stats = servicio.estadisticas()
        a_la_vista = (
            "1 socio a la vista"
            if visibles == 1
            else f"{visibles} socios a la vista"
        )
        activos = f"{stats['activos']} activo" + (
            "" if stats["activos"] == 1 else "s"
        )
        texto = (
            f"{a_la_vista}   ·   "
            f"{stats['socios']} en total   ·   "
            f"{activos}   ·   "
            f"{stats['con_vencidos']} con préstamos vencidos   ·   "
            f"{stats['con_multas']} con multas pendientes   ·   "
            f"{stats['con_advertencias']} con advertencias"
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

        socio_id = item.data(Qt.ItemDataRole.UserRole)
        if socio_id is None:
            return

        self._socio_id = int(socio_id)
        self._cargar_detalle()

    def _cargar_detalle(self) -> None:
        if self._socio_id is None:
            self.pila_detalle.setCurrentIndex(0)
            return

        ficha = servicio.obtener_socio(self._socio_id)
        if ficha is None:
            self._socio_id = None
            self.pila_detalle.setCurrentIndex(0)
            return

        self.pila_detalle.setCurrentIndex(1)

        self.lbl_nombre.setText(ficha["nombre"])
        self.lbl_meta.setText(
            "   ·   ".join(
                [
                    f"Documento {ficha['documento']}",
                    ficha["tipo_legible"],
                    f"Préstamo {ficha['dias_prestamo']} días",
                ]
            )
        )

        self.badge_estado.setText(ficha["estado_legible"])
        self.badge_estado.aplicar_tono(self._tono_estado(ficha["estado"]))

        situacion = ficha["situacion"]
        self.aviso.setProperty("tono", situacion["tono"])
        self.aviso.style().unpolish(self.aviso)
        self.aviso.style().polish(self.aviso)
        self.lbl_aviso.setText(situacion["motivo"])

        advertencias = ficha["advertencias"]
        self.aviso_advertencia.setVisible(bool(advertencias))
        if advertencias:
            ultima = advertencias[0]
            texto = (
                f"Advertencia del {self._fecha(ultima['fecha'])}: "
                f"{ultima['motivo']}"
            )
            if len(advertencias) > 1:
                texto += f" Hay {len(advertencias)} advertencias en total."
            self.lbl_advertencia.setText(texto)
            self.lbl_advertencia.setToolTip(
                "\n\n".join(
                    f"{self._fecha(advertencia['fecha'])}: {advertencia['motivo']}"
                    for advertencia in advertencias
                )
            )
            self.aviso_advertencia.style().unpolish(self.aviso_advertencia)
            self.aviso_advertencia.style().polish(self.aviso_advertencia)
        else:
            self.lbl_advertencia.clear()
            self.lbl_advertencia.setToolTip("")

        lineas = [
            f"Email: {ficha['email'] or 'sin registrar'}",
            f"Teléfono: {ficha['telefono'] or 'sin registrar'}",
            f"Dirección: {ficha['direccion'] or 'sin registrar'}",
            f"Alta: {self._fecha(ficha['fecha_alta'])}",
        ]
        if ficha["observaciones"]:
            lineas.append(f"Notas: {ficha['observaciones']}")
        self.lbl_contacto.setText("\n".join(lineas))

        self._historial = ficha["historial"]
        activos_texto = f"{ficha['activos']} activo" + (
            "" if ficha["activos"] == 1 else "s"
        )
        self.lbl_historial.setText(
            f"{ficha['total_prestamos']} en total · {activos_texto}"
        )

        self.tabla_historial.setRowCount(0)
        self.tabla_historial.setRowCount(len(self._historial))
        for fila, prestamo in enumerate(self._historial):
            # En la ficha angosta no entran cuatro columnas: el ejemplar y la
            # fecha van en una segunda línea, debajo del título.
            recuperado_el = prestamo.get("recuperado_el") or prestamo["devuelto"]
            if prestamo["estado"] == config.PRESTAMO_PERDIDO:
                detalle = (
                    f"{prestamo['ejemplar']} · perdido el "
                    f"{self._fecha(prestamo['devuelto'])}"
                )
            elif prestamo["estado"] == config.PRESTAMO_RECUPERADO:
                detalle = (
                    f"{prestamo['ejemplar']} · recuperado el "
                    f"{self._fecha(recuperado_el)}"
                )
            elif prestamo["devuelto"]:
                detalle = f"{prestamo['ejemplar']} · devuelto el {self._fecha(prestamo['devuelto'])}"
            else:
                detalle = f"{prestamo['ejemplar']} · vence {self._fecha(prestamo['vence'])}"

            if prestamo["estado"] == config.PRESTAMO_PERDIDO:
                cierre = f" · perdido el {self._fecha(prestamo['devuelto'])}"
            elif prestamo["estado"] == config.PRESTAMO_RECUPERADO:
                cierre = f" · recuperado el {self._fecha(recuperado_el)}"
            elif prestamo["devuelto"]:
                cierre = f" · devuelto el {self._fecha(prestamo['devuelto'])}"
            else:
                cierre = ""

            libro = QTableWidgetItem(f"{prestamo['libro']}\n{detalle}")
            libro.setToolTip(
                f"Desde {self._fecha(prestamo['desde'])}"
                f" · vence {self._fecha(prestamo['vence'])}"
                + cierre
            )

            self.tabla_historial.setItem(fila, 0, libro)
            self.tabla_historial.setCellWidget(
                fila,
                1,
                EtiquetaEstado(
                    config.ESTADOS_PRESTAMO.get(prestamo["estado"], prestamo["estado"]),
                    self._tono_prestamo(prestamo["estado"]),
                ),
            )

        self.tabla_historial.resizeRowsToContents()

        hay_historial = bool(self._historial)
        self.tabla_historial.setVisible(hay_historial)
        self.lbl_sin_historial.setVisible(not hay_historial)

        # Multas: las pendientes bloquean nuevas salidas del socio.
        self._multas = ficha["multas"]
        pendientes = ficha["multas_pendientes"]
        if pendientes:
            plural = "pendiente" if pendientes == 1 else "pendientes"
            self.lbl_multas.setText(f"{pendientes} {plural} · {ficha['deuda']}")
        else:
            self.lbl_multas.setText("Sin deudas")

        self.tabla_multas.blockSignals(True)
        self.tabla_multas.setRowCount(0)
        self.tabla_multas.setRowCount(len(self._multas))
        for fila, multa in enumerate(self._multas):
            # El concepto completo va en el tooltip; en la fila se prioriza
            # el libro y el ejemplar para que entre en la ficha angosta.
            titulo = multa["libro"] or multa["concepto"]
            if multa["ejemplar"]:
                detalle_texto = f"{titulo}\n{multa['ejemplar']}"
            else:
                detalle_texto = f"{titulo}\n{self._fecha(multa['fecha'])}"
            detalle = QTableWidgetItem(detalle_texto)
            detalle.setData(Qt.ItemDataRole.UserRole, multa["id"])
            detalle.setToolTip(
                multa["concepto"]
                + f"\n{self._fecha(multa['fecha'])}"
                + (f"\n{multa['notas']}" if multa["notas"] else "")
            )

            monto = QTableWidgetItem(multa["monto"])
            monto.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            self.tabla_multas.setItem(fila, 0, detalle)
            self.tabla_multas.setItem(fila, 1, monto)
            self.tabla_multas.setCellWidget(
                fila,
                2,
                EtiquetaEstado(
                    multa["estado_legible"], self._tono_multa(multa["estado"])
                ),
            )
        self.tabla_multas.blockSignals(False)
        self.tabla_multas.resizeRowsToContents()

        hay_multas = bool(self._multas)
        self.tabla_multas.setVisible(hay_multas)
        if hay_multas:
            self._ajustar_alto_multas()

        if hay_multas:
            fila_pendiente = next(
                (
                    indice
                    for indice, multa in enumerate(self._multas)
                    if multa["estado"] == config.MULTA_PENDIENTE
                ),
                0,
            )
            self.tabla_multas.selectRow(fila_pendiente)
        else:
            self._multa_id = None
            self._actualizar_acciones_multa()

        if ficha["estado"] == config.SOCIO_ACTIVO:
            self.btn_estado.setText("Suspender")
        elif ficha["estado"] == config.SOCIO_SUSPENDIDO:
            self.btn_estado.setText("Reactivar")
        else:
            self.btn_estado.setText("Dar de alta")

    @staticmethod
    def _fecha(valor: date | None) -> str:
        return valor.strftime("%d/%m/%Y") if valor else "—"

    @staticmethod
    def _tono_estado(estado: str) -> str:
        if estado == config.SOCIO_ACTIVO:
            return "exito"
        if estado == config.SOCIO_SUSPENDIDO:
            return "aviso"
        return "neutro"

    @staticmethod
    def _tono_prestamo(estado: str) -> str:
        if estado == config.PRESTAMO_ACTIVO:
            return "acento"
        if estado == config.PRESTAMO_VENCIDO:
            return "peligro"
        if estado == config.PRESTAMO_PERDIDO:
            return "peligro"
        if estado == config.PRESTAMO_RECUPERADO:
            return "aviso"
        return "neutro"

    @staticmethod
    def _tono_multa(estado: str) -> str:
        if estado == config.MULTA_PENDIENTE:
            return "peligro"
        if estado == config.MULTA_PAGADA:
            return "exito"
        return "neutro"

    # --------------------------------------------------------------- multas
    def _ajustar_alto_multas(self) -> None:
        """Ajusta la tabla al alto real de sus filas.

        Las filas de dos líneas miden más de lo que parece, así que se
        calcula en vez de usar un número fijo. El tope evita que la sección
        de multas se quede con el espacio del historial.
        """
        cabecera = (
            self.tabla_multas.horizontalHeader().height()
            if self.tabla_multas.horizontalHeader().isVisible()
            else 0
        )
        filas = sum(
            self.tabla_multas.rowHeight(indice)
            for indice in range(self.tabla_multas.rowCount())
        )
        marco = self.tabla_multas.frameWidth() * 2
        self.tabla_multas.setFixedHeight(min(150, cabecera + filas + marco))

    def _al_seleccionar_multa(self) -> None:
        filas = self.tabla_multas.selectionModel().selectedRows()
        if not filas:
            self._multa_id = None
            self._actualizar_acciones_multa()
            return

        item = self.tabla_multas.item(filas[0].row(), 0)
        self._multa_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._actualizar_acciones_multa()

    def _multa_actual(self) -> dict | None:
        return next(
            (multa for multa in self._multas if multa["id"] == self._multa_id),
            None,
        )

    def _actualizar_acciones_multa(self) -> None:
        multa = self._multa_actual()
        pendiente = multa is not None and multa["estado"] == config.MULTA_PENDIENTE

        self.btn_pagar.setEnabled(pendiente)
        self.btn_anular_multa.setEnabled(pendiente)

        if multa is None:
            ayuda = "Elegí una multa de la lista."
        elif pendiente:
            ayuda = f"{multa['monto']} · {multa['concepto']}"
        else:
            ayuda = f"La multa figura como {multa['estado_legible'].lower()}."

        self.btn_pagar.setToolTip(ayuda)
        self.btn_anular_multa.setToolTip(ayuda)

    def _registrar_pago_multa(self) -> None:
        multa = self._multa_actual()
        if multa is None or multa["estado"] != config.MULTA_PENDIENTE:
            return

        respuesta = QMessageBox.question(
            self,
            "Registrar pago",
            f"¿Registrar el pago de {multa['monto']}?\n\n"
            f"{multa['concepto']}\nSocio: {multa['socio']}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = servicio_multas.registrar_pago(multa["id"])
        if not ok:
            QMessageBox.warning(self, "No se pudo registrar", mensaje)
            return

        registrar_movimiento(
            "pago_multa",
            "multa",
            multa["id"],
            f"{multa['socio']}: {multa['monto']} — {multa['concepto']}",
        )
        self._cargar_tabla()

    def _anular_multa(self) -> None:
        multa = self._multa_actual()
        if multa is None or multa["estado"] != config.MULTA_PENDIENTE:
            return

        motivo, aceptado = QInputDialog.getText(
            self,
            "Anular multa",
            f"Motivo para anular {multa['monto']} (opcional):",
        )
        if not aceptado:
            return

        ok, mensaje = servicio_multas.anular_multa(multa["id"], motivo)
        if not ok:
            QMessageBox.warning(self, "No se pudo anular", mensaje)
            return

        registrar_movimiento(
            "anulacion_multa",
            "multa",
            multa["id"],
            f"{multa['socio']}: {multa['monto']} — {multa['concepto']}",
        )
        self._cargar_tabla()

    # --------------------------------------------------------------- acciones
    def _nuevo_socio(self) -> None:
        dialogo = DialogoSocio(parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        ok, mensaje, socio_id = servicio.crear_socio(dialogo.datos())
        if not ok:
            QMessageBox.warning(self, "No se pudo guardar", mensaje)
            return

        registrar_movimiento(
            "alta_socio", "socio", socio_id, dialogo.datos().get("nombre")
        )
        self._socio_id = socio_id
        self._cargar_tabla()

    def _editar_socio(self) -> None:
        if self._socio_id is None:
            return

        ficha = servicio.obtener_socio(self._socio_id)
        if ficha is None:
            return

        dialogo = DialogoSocio(datos=ficha, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        ok, mensaje = servicio.actualizar_socio(self._socio_id, dialogo.datos())
        if not ok:
            QMessageBox.warning(self, "No se pudo guardar", mensaje)
            return

        registrar_movimiento(
            "edicion_socio", "socio", self._socio_id, dialogo.datos().get("nombre")
        )
        self._cargar_tabla()

    def _cambiar_estado(self) -> None:
        if self._socio_id is None:
            return

        ficha = servicio.obtener_socio(self._socio_id)
        if ficha is None:
            return

        if ficha["estado"] == config.SOCIO_ACTIVO:
            nuevo = config.SOCIO_SUSPENDIDO
            preguntar = (
                f"¿Suspender a {ficha['nombre']}?\n"
                "No va a poder retirar material hasta que lo reactives."
            )
        elif ficha["estado"] == config.SOCIO_SUSPENDIDO:
            nuevo = config.SOCIO_ACTIVO
            preguntar = f"¿Reactivar a {ficha['nombre']}?\nVa a poder retirar material."
        else:
            nuevo = config.SOCIO_ACTIVO
            preguntar = f"¿Dar de alta a {ficha['nombre']}?\nVa a poder retirar material."

        respuesta = QMessageBox.question(
            self,
            "Cambiar estado",
            preguntar,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = servicio.cambiar_estado(self._socio_id, nuevo)
        if not ok:
            QMessageBox.warning(self, "No se pudo cambiar", mensaje)
            return

        registrar_movimiento(
            "cambio_estado_socio",
            "socio",
            self._socio_id,
            f"{ficha['nombre']}: {config.ESTADOS_SOCIO.get(nuevo, nuevo)}",
        )
        self._cargar_tabla()

    def _eliminar_socio(self) -> None:
        if self._socio_id is None:
            return

        ficha = servicio.obtener_socio(self._socio_id)
        if ficha is None:
            return

        respuesta = QMessageBox.question(
            self,
            "Eliminar socio",
            f"¿Eliminar definitivamente a {ficha['nombre']}?\n\n"
            "Solo es posible si nunca tuvo préstamos registrados. "
            "Si tiene historial, conviene darlo de baja para conservarlo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = servicio.eliminar_socio(self._socio_id)
        if not ok:
            QMessageBox.warning(self, "No se pudo eliminar", mensaje)
            return

        registrar_movimiento("eliminar_socio", "socio", self._socio_id, ficha["nombre"])
        self._socio_id = None
        self._cargar_tabla()
