"""Pantalla de préstamos: salidas, devoluciones y renovaciones."""

from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.services import multas as servicio_multas
from app.services import prestamos as servicio
from app.services import reglas
from app.services.auth import registrar_movimiento, sesion_actual
from app.ui import theme
from app.ui.widgets.cards import EtiquetaEstado
from app.ui.widgets.dialogos import (
    DialogoDevolucion,
    DialogoPerdido,
    DialogoPrestamo,
    DialogoRecuperado,
)


class PrestamosPage(QWidget):
    """Listado de préstamos con las acciones de devolución y renovación."""

    COLUMNAS = ["Ejemplar", "Libro", "Socio", "Desde", "Vence", "Estado", "Renov."]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prestamos: list[dict] = []
        self._seleccionado: dict | None = None

        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.setInterval(180)
        self._temporizador.timeout.connect(lambda: self._cargar_tabla())

        self._construir()

    # ------------------------------------------------------------------ UI
    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 18, 26, 16)
        layout.setSpacing(12)

        layout.addLayout(self._barra_herramientas())

        self.pila = QStackedWidget()
        self.pila.addWidget(self._tabla())
        self.pila.addWidget(self._estado_vacio())
        layout.addWidget(self.pila, 1)

        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setObjectName("muted")
        layout.addWidget(self.lbl_resumen)

    def _barra_herramientas(self) -> QVBoxLayout:
        caja = QVBoxLayout()
        caja.setSpacing(8)

        # Primera fila: búsqueda y filtro. Así el buscador conserva ancho
        # aunque la ventana se achique.
        fila_busqueda = QHBoxLayout()
        fila_busqueda.setSpacing(10)

        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText(
            "Buscar por libro, socio, documento o código de ejemplar…"
        )
        self.buscador.setClearButtonEnabled(True)
        self.buscador.textChanged.connect(lambda _t: self._temporizador.start())
        self.buscador.setMinimumWidth(300)

        self.combo_filtro = QComboBox()
        for clave, etiqueta in servicio.FILTROS.items():
            self.combo_filtro.addItem(etiqueta, clave)
        self.combo_filtro.currentIndexChanged.connect(lambda _i: self._cargar_tabla())
        self.combo_filtro.setMinimumWidth(170)

        fila_busqueda.addWidget(self.buscador, 1)
        fila_busqueda.addWidget(self.combo_filtro)
        caja.addLayout(fila_busqueda)

        # Segunda fila: acciones sobre el préstamo elegido.
        fila_acciones = QHBoxLayout()
        fila_acciones.setSpacing(10)

        self.btn_renovar = QPushButton("Renovar")
        self.btn_renovar.setObjectName("ghostButton")
        self.btn_renovar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_renovar.setEnabled(False)
        self.btn_renovar.clicked.connect(self._renovar)

        self.btn_devolver = QPushButton("Registrar devolución")
        self.btn_devolver.setObjectName("ghostButton")
        self.btn_devolver.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_devolver.setEnabled(False)
        self.btn_devolver.clicked.connect(self._devolver)

        self.btn_perdido = QPushButton("Marcar perdido")
        self.btn_perdido.setObjectName("dangerGhostButton")
        self.btn_perdido.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_perdido.setEnabled(False)
        self.btn_perdido.clicked.connect(self._marcar_perdido)

        self.btn_recuperar = QPushButton("Marcar recuperado")
        self.btn_recuperar.setObjectName("ghostButton")
        self.btn_recuperar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_recuperar.setEnabled(False)
        self.btn_recuperar.clicked.connect(self._recuperar)

        boton = QPushButton("+  Nuevo préstamo")
        boton.setObjectName("primaryButton")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.clicked.connect(self._nuevo_prestamo)

        fila_acciones.addStretch(1)
        fila_acciones.addWidget(self.btn_renovar)
        fila_acciones.addWidget(self.btn_devolver)
        fila_acciones.addWidget(self.btn_perdido)
        fila_acciones.addWidget(self.btn_recuperar)
        fila_acciones.addWidget(boton)
        caja.addLayout(fila_acciones)
        return caja

    def _tabla(self) -> QWidget:
        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setDefaultSectionSize(40)

        cabecera = self.tabla.horizontalHeader()
        cabecera.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        cabecera.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        cabecera.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        cabecera.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(3, 112)
        self.tabla.setColumnWidth(4, 112)
        self.tabla.setColumnWidth(5, 106)
        self.tabla.setColumnWidth(6, 68)
        cabecera.setHighlightSections(False)

        self.tabla.itemSelectionChanged.connect(self._al_seleccionar)
        return self.tabla

    def _estado_vacio(self) -> QWidget:
        caja = QWidget()
        layout = QVBoxLayout(caja)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titulo = QLabel("No hay préstamos en esta vista")
        titulo.setObjectName("sectionTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detalle = QLabel(
            "Registrá una salida con «Nuevo préstamo»\n"
            "o cambiá la búsqueda y los filtros."
        )
        detalle.setObjectName("emptyState")
        detalle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(titulo)
        layout.addWidget(detalle)
        return caja

    # ------------------------------------------------------------- refrescos
    def refrescar(self) -> None:
        self._cargar_tabla()

    def _cargar_tabla(self, seleccionar: int | None = None) -> None:
        prestamos = servicio.listar_prestamos(
            busqueda=self.buscador.text(),
            filtro=self.combo_filtro.currentData(),
        )

        objetivo = (
            seleccionar
            if seleccionar is not None
            else (self._seleccionado["id"] if self._seleccionado else None)
        )
        self._prestamos = prestamos

        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        self.tabla.setRowCount(len(prestamos))

        for fila, prestamo in enumerate(prestamos):
            self._llenar_fila(fila, prestamo)

        self.tabla.blockSignals(False)

        if not prestamos:
            self.pila.setCurrentIndex(1)
            self._seleccionado = None
            self._actualizar_acciones()
        else:
            self.pila.setCurrentIndex(0)
            fila_objetivo = next(
                (
                    indice
                    for indice, prestamo in enumerate(prestamos)
                    if prestamo["id"] == objetivo
                ),
                0,
            )
            self.tabla.selectRow(fila_objetivo)

        self._actualizar_resumen(len(prestamos))

    def _llenar_fila(self, fila: int, prestamo: dict) -> None:
        ejemplar = QTableWidgetItem(prestamo["ejemplar"])
        ejemplar.setData(Qt.ItemDataRole.UserRole, prestamo["id"])

        libro = QTableWidgetItem(prestamo["libro"])
        if prestamo["autores"]:
            libro.setToolTip(prestamo["autores"])

        socio = QTableWidgetItem(prestamo["socio"])
        socio.setToolTip(f"Documento {prestamo['documento']}")

        desde = QTableWidgetItem(f"{prestamo['desde']:%d/%m/%Y}")
        vence = QTableWidgetItem(f"{prestamo['vence']:%d/%m/%Y}")
        for fecha in (desde, vence):
            fecha.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if prestamo["atraso"]:
            vence.setForeground(QColor(theme.PELIGRO))
            vence.setToolTip(f"{prestamo['atraso']} día(s) de atraso")

        if prestamo["devuelto"] is not None:
            for item in (ejemplar, libro, socio, desde, vence):
                item.setForeground(QColor(theme.TEXTO_TENUE))

        renovaciones = QTableWidgetItem(
            "—"
            if prestamo["devuelto"] is not None
            else f"{prestamo['renovaciones']}/{prestamo['max_renovaciones']}"
        )
        renovaciones.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        renovaciones.setToolTip(
            f"Renovaciones usadas: {prestamo['renovaciones']} "
            f"de {prestamo['max_renovaciones']}"
        )

        self.tabla.setItem(fila, 0, ejemplar)
        self.tabla.setItem(fila, 1, libro)
        self.tabla.setItem(fila, 2, socio)
        self.tabla.setItem(fila, 3, desde)
        self.tabla.setItem(fila, 4, vence)
        self.tabla.setCellWidget(
            fila,
            5,
            EtiquetaEstado(
                config.ESTADOS_PRESTAMO.get(prestamo["estado"], prestamo["estado"]),
                self._tono_estado(prestamo["estado"]),
            ),
        )
        self.tabla.setItem(fila, 6, renovaciones)

    def _actualizar_resumen(self, visibles: int) -> None:
        stats = servicio.estadisticas()
        renovaciones = reglas.max_renovaciones()
        if renovaciones == 0:
            texto_renovacion = "sin renovaciones"
        elif renovaciones == 1:
            texto_renovacion = f"1 renovación de {reglas.dias_renovacion()} días"
        else:
            texto_renovacion = (
                f"{renovaciones} renovaciones de {reglas.dias_renovacion()} días"
            )

        a_la_vista = (
            "1 préstamo a la vista"
            if visibles == 1
            else f"{visibles} préstamos a la vista"
        )
        activos = f"{stats['activos']} activo" + (
            "" if stats["activos"] == 1 else "s"
        )
        vencidos = f"{stats['vencidos']} vencido" + (
            "" if stats["vencidos"] == 1 else "s"
        )
        devueltos = f"{stats['devueltos']} devuelto" + (
            "" if stats["devueltos"] == 1 else "s"
        )
        recuperados = f"{stats['recuperados']} recuperado" + (
            "" if stats["recuperados"] == 1 else "s"
        )
        perdidos = f"{stats['perdidos']} perdido" + (
            "" if stats["perdidos"] == 1 else "s"
        )
        self.lbl_resumen.setText(
            f"{a_la_vista}   ·   "
            f"{activos}   ·   "
            f"{vencidos}   ·   "
            f"{devueltos}   ·   "
            f"{recuperados}   ·   "
            f"{perdidos}   ·   "
            f"{texto_renovacion}"
        )

    @staticmethod
    def _tono_estado(estado: str) -> str:
        if estado == config.PRESTAMO_DEVUELTO:
            return "neutro"
        if estado in (config.PRESTAMO_VENCIDO, config.PRESTAMO_PERDIDO):
            return "peligro"
        if estado == config.PRESTAMO_RECUPERADO:
            return "aviso"
        return "acento"

    # ------------------------------------------------------------- seleccion
    def _al_seleccionar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            self._seleccionado = None
            self._actualizar_acciones()
            return

        item = self.tabla.item(filas[0].row(), 0)
        prestamo_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._seleccionado = next(
            (p for p in self._prestamos if p["id"] == prestamo_id), None
        )
        self._actualizar_acciones()

    def _actualizar_acciones(self) -> None:
        prestamo = self._seleccionado
        self.btn_devolver.setEnabled(bool(prestamo) and prestamo["devuelto"] is None)
        self.btn_devolver.setToolTip(
            "Cierra el préstamo y devuelve el ejemplar al estante."
            if prestamo and prestamo["devuelto"] is None
            else "Elegí un préstamo sin devolver."
        )

        self.btn_perdido.setEnabled(bool(prestamo) and prestamo["devuelto"] is None)
        self.btn_perdido.setToolTip(
            "Cierra el préstamo como perdido y permite imponer una multa al socio."
            if prestamo and prestamo["devuelto"] is None
            else "Elegí un préstamo sin devolver."
        )

        es_perdido = bool(prestamo) and prestamo["estado"] == config.PRESTAMO_PERDIDO
        puede_recuperar = sesion_actual.puede("socios")
        self.btn_recuperar.setEnabled(es_perdido and puede_recuperar)
        if not es_perdido:
            ayuda = "Elegí un préstamo marcado como perdido."
        elif not puede_recuperar:
            ayuda = (
                "Requiere permiso de socios: la recuperación anula la multa "
                "pendiente."
            )
        else:
            ayuda = (
                "Devuelve el ejemplar al inventario y anula la multa pendiente. "
                "Queda una advertencia en el socio."
            )
        self.btn_recuperar.setToolTip(ayuda)

        self.btn_renovar.setEnabled(bool(prestamo) and prestamo["renovable"])
        self.btn_renovar.setToolTip(self._motivo_renovacion(prestamo))

    def _motivo_renovacion(self, prestamo: dict | None) -> str:
        if prestamo is None:
            return "Elegí un préstamo de la lista."

        if prestamo["estado"] == config.PRESTAMO_PERDIDO:
            return "El préstamo figura como perdido."
        if prestamo["estado"] == config.PRESTAMO_RECUPERADO:
            return "El préstamo ya fue recuperado."
        if prestamo["devuelto"] is not None:
            return "El préstamo ya fue devuelto."
        if prestamo["socio_estado"] != config.SOCIO_ACTIVO:
            estado = config.ESTADOS_SOCIO.get(
                prestamo["socio_estado"], prestamo["socio_estado"]
            )
            return f"El socio está {estado.lower()}: no se puede renovar."
        if prestamo["atraso"] > 0:
            return (
                "Los préstamos vencidos no se renuevan: "
                "registrá primero la devolución."
            )
        if prestamo["max_renovaciones"] <= 0:
            return "Las renovaciones están deshabilitadas en la configuración."
        if prestamo["renovaciones"] >= prestamo["max_renovaciones"]:
            veces = "vez" if prestamo["renovaciones"] == 1 else "veces"
            return (
                f"Ya se renovó {prestamo['renovaciones']} {veces} "
                f"(máximo {prestamo['max_renovaciones']})."
            )
        return f"Extiende el vencimiento {reglas.dias_renovacion()} días."

    # --------------------------------------------------------------- acciones
    def _nuevo_prestamo(self) -> None:
        dialogo = DialogoPrestamo(parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        datos = dialogo.datos()
        ok, mensaje, prestamo_id = servicio.prestar(
            datos["socio_id"], datos["ejemplar_id"], datos["notas"]
        )
        if not ok:
            QMessageBox.warning(self, "No se pudo registrar", mensaje)
            return

        registrar_movimiento(
            "prestamo", "prestamo", prestamo_id, dialogo.descripcion()
        )
        # Si había un filtro o una búsqueda, el préstamo nuevo no se vería:
        # se vuelve a la vista completa y se selecciona la fila recién creada.
        self.buscador.blockSignals(True)
        self.combo_filtro.blockSignals(True)
        self.buscador.clear()
        self.combo_filtro.setCurrentIndex(0)
        self.combo_filtro.blockSignals(False)
        self.buscador.blockSignals(False)
        self._cargar_tabla(seleccionar=prestamo_id)

    def _devolver(self) -> None:
        prestamo = self._seleccionado
        if prestamo is None or prestamo["devuelto"] is not None:
            return

        dialogo = DialogoDevolucion(prestamo, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        estado_ejemplar = dialogo.estado_ejemplar()
        ok, mensaje = servicio.devolver(prestamo["id"], estado_ejemplar)
        if not ok:
            QMessageBox.warning(self, "No se pudo devolver", mensaje)
            return

        detalle = (
            f"{prestamo['ejemplar']} · {prestamo['libro']} — "
            f"devuelto por {prestamo['socio']}"
        )
        if estado_ejemplar == config.EJEMPLAR_REPARACION:
            detalle += " (queda en reparación)"
        registrar_movimiento("devolucion", "prestamo", prestamo["id"], detalle)
        self._cargar_tabla(seleccionar=prestamo["id"])

    def _marcar_perdido(self) -> None:
        prestamo = self._seleccionado
        if prestamo is None or prestamo["devuelto"] is not None:
            return

        dialogo = DialogoPerdido(prestamo, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        monto = dialogo.monto_centavos()
        ok, mensaje = servicio.marcar_perdido(
            prestamo["id"], monto, dialogo.notas()
        )
        if not ok:
            QMessageBox.warning(self, "No se pudo marcar", mensaje)
            self._cargar_tabla(seleccionar=prestamo["id"])
            return

        detalle = (
            f"{prestamo['ejemplar']} · {prestamo['libro']} — "
            f"perdido por {prestamo['socio']}"
        )
        if monto:
            detalle += f"; multa {servicio_multas.formatear_monto(monto)}"
        else:
            detalle += "; sin multa"
        registrar_movimiento("perdida", "prestamo", prestamo["id"], detalle)
        self._cargar_tabla(seleccionar=prestamo["id"])

    def _recuperar(self) -> None:
        prestamo = self._seleccionado
        if prestamo is None or prestamo["estado"] != config.PRESTAMO_PERDIDO:
            return

        dialogo = DialogoRecuperado(prestamo, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        estado_ejemplar = dialogo.estado_ejemplar()
        ok, mensaje = servicio.recuperar(prestamo["id"], estado_ejemplar)
        if not ok:
            QMessageBox.warning(self, "No se pudo recuperar", mensaje)
            self._cargar_tabla(seleccionar=prestamo["id"])
            return

        detalle = (
            f"{prestamo['ejemplar']} · {prestamo['libro']} — "
            f"recuperado por {prestamo['socio']}"
        )
        if estado_ejemplar == config.EJEMPLAR_REPARACION:
            detalle += " (queda en reparación)"
        else:
            detalle += " (vuelve al estante)"
        registrar_movimiento("recuperacion", "prestamo", prestamo["id"], detalle)
        self._cargar_tabla(seleccionar=prestamo["id"])

    def _renovar(self) -> None:
        prestamo = self._seleccionado
        if prestamo is None or not prestamo["renovable"]:
            return

        dias = reglas.dias_renovacion()
        nueva = prestamo["vence"] + timedelta(days=dias)
        respuesta = QMessageBox.question(
            self,
            "Renovar préstamo",
            f"¿Renovar el préstamo de «{prestamo['libro']}» a "
            f"{prestamo['socio']}?\n\n"
            f"Vence el {prestamo['vence']:%d/%m/%Y} y pasaría a vencer el "
            f"{nueva:%d/%m/%Y} ({dias} días más).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = servicio.renovar(prestamo["id"])
        if not ok:
            QMessageBox.warning(self, "No se pudo renovar", mensaje)
            self._cargar_tabla(seleccionar=prestamo["id"])
            return

        registrar_movimiento(
            "renovacion",
            "prestamo",
            prestamo["id"],
            f"{prestamo['ejemplar']} · {prestamo['libro']}: "
            f"nuevo vencimiento {nueva:%d/%m/%Y}",
        )
        self._cargar_tabla(seleccionar=prestamo["id"])
