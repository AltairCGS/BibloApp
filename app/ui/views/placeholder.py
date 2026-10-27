"""Pantalla genérica para módulos que se construyen en fases posteriores."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.widgets.cards import EncabezadoSeccion, linea_horizontal


class PlaceholderPage(QWidget):
    """Muestra el nombre del módulo, su fase y lo que incluirá."""

    def __init__(
        self,
        titulo: str,
        descripcion: str,
        funciones: list[str],
        fase: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)

        layout.addWidget(EncabezadoSeccion(titulo, fase))
        layout.addWidget(linea_horizontal())

        detalle = QLabel(descripcion)
        detalle.setObjectName("muted")
        detalle.setWordWrap(True)
        layout.addWidget(detalle)

        layout.addSpacing(6)

        titulo_lista = QLabel("Incluirá")
        titulo_lista.setObjectName("fieldLabel")
        layout.addWidget(titulo_lista)

        for funcion in funciones:
            item = QLabel(f"•   {funcion}")
            item.setObjectName("muted")
            item.setWordWrap(True)
            layout.addWidget(item)

        layout.addStretch(1)

        aviso = QLabel("Módulo pendiente de implementación.")
        aviso.setObjectName("emptyState")
        aviso.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(aviso)
