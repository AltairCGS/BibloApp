"""Pantalla de vencidos: préstamos fuera de plazo y recordatorios."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
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
from app.services import prestamos as servicio_prestamos
from app.services import vencidos as servicio
from app.services.auth import registrar_movimiento
from app.ui import theme
from app.ui.widgets.dialogos import DialogoDevolucion, DialogoPerdido


class VencidosPage(QWidget):
    """Listado de préstamos abiertos fuera de plazo, con exportación CSV."""

    COLUMNAS = ["Ejemplar", "Libro", "Socio", "Contacto", "Vence", "Atraso"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filas: list[dict] = []
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

        fila_busqueda = QHBoxLayout()
        fila_busqueda.setSpacing(10)

        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText(
            "Buscar por socio, documento, contacto, libro o ejemplar…"
        )
        self.buscador.setClearButtonEnabled(True)
        self.buscador.textChanged.connect(lambda _t: self._temporizador.start())
        self.buscador.setMinimumWidth(300)

        self.check_gracia = QCheckBox("Solo fuera de gracia")
        self.check_gracia.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_gracia.setToolTip(
            "Oculta los atrasos que todavía están dentro del plazo de gracia."
        )
        self.check_gracia.toggled.connect(lambda _v: self._cargar_tabla())

        self.btn_exportar = QPushButton("Exportar CSV")
        self.btn_exportar.setObjectName("ghostButton")
        self.btn_exportar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exportar.setToolTip(
            "Genera un archivo con una fila por préstamo para enviar recordatorios."
        )
        self.btn_exportar.clicked.connect(self._exportar)

        fila_busqueda.addWidget(self.buscador, 1)
        fila_busqueda.addWidget(self.check_gracia)
        fila_busqueda.addWidget(self.btn_exportar)
        caja.addLayout(fila_busqueda)

        fila_acciones = QHBoxLayout()
        fila_acciones.setSpacing(10)

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

        fila_acciones.addStretch(1)
        fila_acciones.addWidget(self.btn_devolver)
        fila_acciones.addWidget(self.btn_perdido)
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
        cabecera.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        cabecera.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(4, 104)
        self.tabla.setColumnWidth(5, 88)
        cabecera.setHighlightSections(False)

        self.tabla.itemSelectionChanged.connect(self._al_seleccionar)
        return self.tabla

    def _estado_vacio(self) -> QWidget:
        caja = QWidget()
        layout = QVBoxLayout(caja)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titulo = QLabel("No hay préstamos vencidos")
        titulo.setObjectName("sectionTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detalle = QLabel(
            "Todo el material está dentro del plazo.\n"
            "Probá quitar el filtro de gracia."
        )
        detalle.setObjectName("emptyState")
        detalle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(titulo)
        layout.addWidget(detalle)
        return caja

    # ------------------------------------------------------------- refrescos
    def refrescar(self) -> None:
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        filas = servicio.listar_vencidos(
            busqueda=self.buscador.text(),
            solo_fuera_de_gracia=self.check_gracia.isChecked(),
        )

        objetivo = self._seleccionado["id"] if self._seleccionado else None
        self._filas = filas

        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        self.tabla.setRowCount(len(filas))

        for indice, fila in enumerate(filas):
            self._llenar_fila(indice, fila)

        self.tabla.blockSignals(False)

        if not filas:
            self.pila.setCurrentIndex(1)
            self._seleccionado = None
            self._actualizar_acciones()
        else:
            self.pila.setCurrentIndex(0)
            fila_objetivo = next(
                (
                    indice
                    for indice, fila in enumerate(filas)
                    if fila["id"] == objetivo
                ),
                0,
            )
            self.tabla.selectRow(fila_objetivo)

        self._actualizar_resumen()

    def _llenar_fila(self, indice: int, fila: dict) -> None:
        ejemplar = QTableWidgetItem(fila["ejemplar"])
        ejemplar.setData(Qt.ItemDataRole.UserRole, fila["id"])

        libro = QTableWidgetItem(fila["libro"])
        if fila["autores"]:
            libro.setToolTip(fila["autores"])

        socio = QTableWidgetItem(fila["socio"])
        socio.setToolTip(
            f"Documento {fila['documento']} · {fila['tipo_socio']}"
        )

        contacto = QTableWidgetItem(
            fila["telefono"] or fila["email"] or "Sin contacto"
        )
        if not fila["telefono"] and not fila["email"]:
            contacto.setForeground(QColor(theme.TEXTO_TENUE))
        contacto.setToolTip(
            f"Teléfono: {fila['telefono'] or '—'}\n"
            f"Correo: {fila['email'] or '—'}\n"
            f"Documento: {fila['documento']}"
        )

        vence = QTableWidgetItem(f"{fila['vence']:%d/%m/%Y}")
        vence.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        atraso = QTableWidgetItem(
            "1 día" if fila["dias_atraso"] == 1 else f"{fila['dias_atraso']} días"
        )
        atraso.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        atraso.setForeground(QColor(theme.PELIGRO))
        if fila["en_gracia"]:
            atraso.setToolTip("Todavía dentro del plazo de gracia.")
        else:
            atraso.setToolTip("Fuera del plazo de gracia: el socio queda bloqueado.")

        self.tabla.setItem(indice, 0, ejemplar)
        self.tabla.setItem(indice, 1, libro)
        self.tabla.setItem(indice, 2, socio)
        self.tabla.setItem(indice, 3, contacto)
        self.tabla.setItem(indice, 4, vence)
        self.tabla.setItem(indice, 5, atraso)

    def _actualizar_resumen(self) -> None:
        resumen = servicio.resumen(
            busqueda=self.buscador.text(),
            solo_fuera_de_gracia=self.check_gracia.isChecked(),
        )
        total = resumen["total"]
        socios = resumen["socios"]
        maximo = resumen["maximo_atraso"]
        fuera = resumen["fuera_de_gracia"]

        partes = [
            "1 préstamo vencido" if total == 1 else f"{total} préstamos vencidos",
            "1 socio" if socios == 1 else f"{socios} socios",
        ]
        if total:
            partes.append(
                "hasta 1 día de atraso"
                if maximo == 1
                else f"hasta {maximo} días de atraso"
            )
        partes.append(
            "1 fuera del plazo de gracia"
            if fuera == 1
            else f"{fuera} fuera del plazo de gracia"
        )
        self.lbl_resumen.setText(" · ".join(partes))

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
            (fila for fila in self._filas if fila["id"] == prestamo_id), None
        )
        self._actualizar_acciones()

    def _actualizar_acciones(self) -> None:
        hay_seleccion = self._seleccionado is not None
        self.btn_devolver.setEnabled(hay_seleccion)
        self.btn_devolver.setToolTip(
            "Cierra el préstamo y devuelve el ejemplar al estante."
            if hay_seleccion
            else "Elegí un préstamo vencido de la lista."
        )
        self.btn_perdido.setEnabled(hay_seleccion)
        self.btn_perdido.setToolTip(
            "Cierra el préstamo como perdido y permite imponer una multa al socio."
            if hay_seleccion
            else "Elegí un préstamo vencido de la lista."
        )

    # --------------------------------------------------------------- acciones
    def _devolver(self) -> None:
        fila = self._seleccionado
        if fila is None:
            return

        dialogo = DialogoDevolucion(fila, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        estado_ejemplar = dialogo.estado_ejemplar()
        ok, mensaje = servicio_prestamos.devolver(fila["id"], estado_ejemplar)
        if not ok:
            QMessageBox.warning(self, "No se pudo devolver", mensaje)
            self._cargar_tabla()
            return

        detalle = (
            f"{fila['ejemplar']} · {fila['libro']} — "
            f"devuelto por {fila['socio']}"
        )
        if estado_ejemplar == config.EJEMPLAR_REPARACION:
            detalle += " (queda en reparación)"
        registrar_movimiento("devolucion", "prestamo", fila["id"], detalle)
        self._cargar_tabla()

    def _marcar_perdido(self) -> None:
        fila = self._seleccionado
        if fila is None:
            return

        dialogo = DialogoPerdido(fila, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        monto = dialogo.monto_centavos()
        ok, mensaje = servicio_prestamos.marcar_perdido(
            fila["id"], monto, dialogo.notas()
        )
        if not ok:
            QMessageBox.warning(self, "No se pudo marcar", mensaje)
            self._cargar_tabla()
            return

        detalle = (
            f"{fila['ejemplar']} · {fila['libro']} — "
            f"perdido por {fila['socio']}"
        )
        if monto:
            detalle += f"; multa {servicio_multas.formatear_monto(monto)}"
        else:
            detalle += "; sin multa"
        registrar_movimiento("perdida", "prestamo", fila["id"], detalle)
        self._cargar_tabla()

    def _exportar(self) -> None:
        propuesto = f"vencidos_{date.today():%Y-%m-%d}.csv"
        ruta, _filtro = QFileDialog.getSaveFileName(
            self,
            "Exportar recordatorios",
            propuesto,
            "Archivos CSV (*.csv)",
        )
        if not ruta:
            return
        if not ruta.lower().endswith(".csv"):
            ruta += ".csv"

        ok, mensaje = servicio.exportar_csv(
            ruta,
            busqueda=self.buscador.text(),
            solo_fuera_de_gracia=self.check_gracia.isChecked(),
        )
        if not ok:
            QMessageBox.warning(self, "No se pudo exportar", mensaje)
            return

        cantidad = servicio.resumen(
            busqueda=self.buscador.text(),
            solo_fuera_de_gracia=self.check_gracia.isChecked(),
        )["total"]
        detalle = (
            "Se exportó 1 préstamo vencido a:"
            if cantidad == 1
            else f"Se exportaron {cantidad} préstamos vencidos a:"
        )
        QMessageBox.information(
            self,
            "Recordatorios exportados",
            f"{detalle}\n{ruta}",
        )
