"""Panel principal: estado general de la biblioteca."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services import panel as servicio_panel
from app.ui import theme
from app.ui.widgets.cards import EncabezadoSeccion, TarjetaKPI


class DashboardPage(QWidget):
    """Vista de resumen con tarjetas y préstamos activos."""

    COLUMNAS = ["Ejemplar", "Libro", "Socio", "Documento", "Vence", "Estado"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._construir()
        self.refrescar()

    # ------------------------------------------------------------------ UI
    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(18)

        fila_kpi = QHBoxLayout()
        fila_kpi.setSpacing(14)

        self.kpi_disponibles = TarjetaKPI(
            "Ejemplares disponibles", 0, "", theme.EXITO
        )
        self.kpi_prestamos = TarjetaKPI("Préstamos activos", 0, "", theme.ACENTO)
        self.kpi_vencidos = TarjetaKPI("Vencidos", 0, "", theme.PELIGRO)
        self.kpi_socios = TarjetaKPI("Socios activos", 0, "", theme.TEXTO)

        for tarjeta in (
            self.kpi_disponibles,
            self.kpi_prestamos,
            self.kpi_vencidos,
            self.kpi_socios,
        ):
            fila_kpi.addWidget(tarjeta, 1)

        layout.addLayout(fila_kpi)

        layout.addWidget(
            EncabezadoSeccion("Préstamos activos", "ordenados por fecha de vencimiento")
        )

        self.pila = QStackedWidget()
        self.pila.addWidget(self._tabla())
        self.pila.addWidget(self._estado_vacio())
        layout.addWidget(self.pila, 1)

        nota = QLabel(
            "Los ejemplares vencidos se marcan en rojo. "
            "Se bloquea a un socio cuando supera los días de gracia configurados."
        )
        nota.setObjectName("muted")
        layout.addWidget(nota)

    def _tabla(self) -> QWidget:
        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        cabecera = self.tabla.horizontalHeader()
        cabecera.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setHighlightSections(False)

        self.tabla.verticalHeader().setDefaultSectionSize(38)
        return self.tabla

    def _estado_vacio(self) -> QWidget:
        caja = QWidget()
        layout = QVBoxLayout(caja)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titulo = QLabel("No hay préstamos activos")
        titulo.setObjectName("sectionTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detalle = QLabel("Cuando registres un préstamo aparecerá en esta lista.")
        detalle.setObjectName("emptyState")
        detalle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(titulo)
        layout.addWidget(detalle)
        return caja

    # ------------------------------------------------------------- refresco
    def refrescar(self) -> None:
        try:
            resumen = servicio_panel.resumen_panel()
            prestamos = servicio_panel.prestamos_activos()
        except Exception:
            resumen = {
                "disponibles": 0,
                "prestamos_activos": 0,
                "vencidos": 0,
                "socios_activos": 0,
            }
            prestamos = []

        self.kpi_disponibles.actualizar(
            resumen["disponibles"],
            f"de {resumen['ejemplares']} ejemplares en total",
        )
        self.kpi_prestamos.actualizar(
            resumen["prestamos_activos"],
            f"{resumen['libros']} títulos en catálogo",
        )
        self.kpi_vencidos.actualizar(
            resumen["vencidos"],
            "requieren seguimiento" if resumen["vencidos"] else "todo al día",
        )
        self.kpi_socios.actualizar(resumen["socios_activos"], "socios habilitados")

        self._cargar_tabla(prestamos)

    def _cargar_tabla(self, prestamos: list[dict]) -> None:
        self.tabla.setRowCount(0)
        if not prestamos:
            self.pila.setCurrentIndex(1)
            return

        self.pila.setCurrentIndex(0)
        self.tabla.setRowCount(len(prestamos))

        for fila, datos in enumerate(prestamos):
            vencido = datos["dias_atraso"] > 0
            valores = [
                datos["ejemplar"],
                datos["libro"],
                datos["socio"],
                datos["documento"],
                datos["vence"].strftime("%d/%m/%Y"),
                "Vencido" if vencido else "Activo",
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if columna == 5:
                    item.setForeground(
                        Qt.GlobalColor.darkRed if vencido else Qt.GlobalColor.darkCyan
                    )
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(fila, columna, item)
