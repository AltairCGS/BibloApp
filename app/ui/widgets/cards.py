"""Componentes reutilizables: tarjetas, etiquetas de estado y encabezados."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui import theme


class TarjetaKPI(QFrame):
    """Tarjeta con un número grande y su descripción."""

    def __init__(
        self,
        etiqueta: str,
        valor: str | int = "0",
        pista: str = "",
        color_valor: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(112)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(2)

        self._lbl_etiqueta = QLabel(etiqueta)
        self._lbl_etiqueta.setObjectName("kpiLabel")

        self._lbl_valor = QLabel(str(valor))
        self._lbl_valor.setObjectName("kpiValue")
        if color_valor:
            self._lbl_valor.setStyleSheet(f"color: {color_valor};")

        self._lbl_pista = QLabel(pista)
        self._lbl_pista.setObjectName("kpiHint")
        self._lbl_pista.setVisible(bool(pista))

        layout.addWidget(self._lbl_etiqueta)
        layout.addWidget(self._lbl_valor)
        layout.addWidget(self._lbl_pista)

    def actualizar(self, valor: str | int, pista: str | None = None) -> None:
        self._lbl_valor.setText(str(valor))
        if pista is not None:
            self._lbl_pista.setText(pista)
            self._lbl_pista.setVisible(bool(pista))


class EtiquetaEstado(QLabel):
    """Badge de color según el estado."""

    TONOS = {
        "disponible": "exito",
        "activo": "acento",
        "prestado": "aviso",
        "vencido": "peligro",
        "bloqueado": "peligro",
        "en_reparacion": "aviso",
        "perdido": "peligro",
        "dado_de_baja": "neutro",
    }

    def __init__(self, texto: str, tono: str = "neutro", parent: QWidget | None = None) -> None:
        super().__init__(texto, parent)
        self.setObjectName("badge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.aplicar_tono(tono)

    def aplicar_tono(self, tono: str) -> None:
        self.setProperty("tono", tono)
        self.style().unpolish(self)
        self.style().polish(self)


class EncabezadoSeccion(QWidget):
    """Título de sección con una línea separadora opcional."""

    def __init__(self, titulo: str, subtitulo: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("sectionTitle")
        layout.addWidget(etiqueta)

        if subtitulo:
            sub = QLabel(subtitulo)
            sub.setObjectName("muted")
            layout.addWidget(sub)

        layout.addStretch(1)


def linea_horizontal() -> QFrame:
    """Separador de 1 px."""
    linea = QFrame()
    linea.setObjectName("hline")
    linea.setFixedHeight(1)
    linea.setStyleSheet(f"background: {theme.BORDE_SUAVE};")
    return linea
