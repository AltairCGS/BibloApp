"""Paleta, tipografía y hoja de estilos (QSS) de BibloApp.

Estética sobria y plana: herramientas de trabajo, no app de consumo.
Sin degradados, sin sombras difusas, sin animaciones.
"""

from __future__ import annotations

# --- Paleta ---------------------------------------------------------------------
FONDO = "#F4F6F8"
SUPERFICIE = "#FFFFFF"
BORDE = "#D9E0E8"
BORDE_SUAVE = "#E7ECF1"
TEXTO = "#1B2733"
TEXTO_SUAVE = "#5C6B7A"
TEXTO_TENUE = "#8A98A6"

NAVY = "#1F3A5F"
NAVY_HOVER = "#27496F"
NAVY_ACTIVO = "#2E5C8A"
NAVY_TEXTO = "#C9D8E6"
NAVY_TENUE = "#8FA9C2"

ACENTO = "#23648A"
ACENTO_HOVER = "#1B5070"
ACENTO_SUAVE = "#E8F1F7"

EXITO = "#1E7A46"
EXITO_SUAVE = "#E6F4EB"
ADVERTENCIA = "#B26A00"
ADVERTENCIA_SUAVE = "#FDF2E0"
PELIGRO = "#B3261E"
PELIGRO_HOVER = "#961F17"
PELIGRO_SUAVE = "#FBE9E7"

FUENTE = "Segoe UI"


def hoja_estilos() -> str:
    """Devuelve el QSS completo de la aplicación."""
    return f"""
    /* ---------- Base ---------- */
    QWidget {{
        font-family: "{FUENTE}";
        font-size: 14px;
        color: {TEXTO};
    }}

    QMainWindow, QWidget#appRoot, QWidget#loginRoot {{
        background: {FONDO};
    }}

    QToolTip {{
        background: {TEXTO};
        color: #FFFFFF;
        border: none;
        padding: 6px 8px;
        font-size: 12px;
    }}

    /* ---------- Barra lateral ---------- */
    QWidget#sidebar {{
        background: {NAVY};
    }}

    QLabel#brand {{
        color: #FFFFFF;
        font-size: 21px;
        font-weight: 700;
    }}

    QLabel#brandSub {{
        color: {NAVY_TENUE};
        font-size: 11px;
    }}

    QLabel#sidebarSection {{
        color: {NAVY_TENUE};
        font-size: 10px;
        font-weight: 600;
        padding: 0 18px;
    }}

    QPushButton#navItem {{
        background: transparent;
        color: {NAVY_TEXTO};
        border: none;
        border-left: 3px solid transparent;
        padding: 10px 18px;
        text-align: left;
        font-size: 14px;
    }}

    QPushButton#navItem:hover {{
        background: {NAVY_HOVER};
        color: #FFFFFF;
    }}

    QPushButton#navItem:checked {{
        background: {NAVY_ACTIVO};
        color: #FFFFFF;
        border-left: 3px solid #7FB2E5;
        font-weight: 600;
    }}

    QPushButton#navItem:disabled {{
        color: #5E7893;
    }}

    QWidget#sidebarFooter {{
        border-top: 1px solid #2C4A6E;
    }}

    QLabel#userName {{
        color: #FFFFFF;
        font-weight: 600;
        font-size: 13px;
    }}

    QLabel#userRole {{
        color: {NAVY_TENUE};
        font-size: 11px;
    }}

    QPushButton#logoutButton {{
        background: transparent;
        color: {NAVY_TEXTO};
        border: 1px solid #3B5B80;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    QPushButton#logoutButton:hover {{
        background: {NAVY_HOVER};
        color: #FFFFFF;
        border-color: #4E709A;
    }}

    /* ---------- Barra superior ---------- */
    QWidget#topbar {{
        background: {SUPERFICIE};
        border-bottom: 1px solid {BORDE};
    }}

    QLabel#pageTitle {{
        font-size: 18px;
        font-weight: 600;
    }}

    QLabel#pageSubtitle {{
        color: {TEXTO_SUAVE};
        font-size: 12px;
    }}

    /* ---------- Tarjetas ---------- */
    QFrame#card {{
        background: {SUPERFICIE};
        border: 1px solid {BORDE};
        border-radius: 10px;
    }}

    QLabel#kpiValue {{
        font-size: 30px;
        font-weight: 700;
    }}

    QLabel#kpiLabel {{
        color: {TEXTO_SUAVE};
        font-size: 12px;
        font-weight: 600;
    }}

    QLabel#kpiHint {{
        color: {TEXTO_TENUE};
        font-size: 11px;
    }}

    QLabel#sectionTitle {{
        font-size: 15px;
        font-weight: 600;
    }}

    QLabel#emptyState {{
        color: {TEXTO_SUAVE};
        font-size: 13px;
    }}

    /* ---------- Botones ---------- */
    QPushButton#primaryButton {{
        background: {ACENTO};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 9px 18px;
        font-weight: 600;
        font-size: 14px;
    }}

    QPushButton#primaryButton:hover {{
        background: {ACENTO_HOVER};
    }}

    QPushButton#primaryButton:pressed {{
        background: #16415C;
    }}

    QPushButton#primaryButton:disabled {{
        background: #B7C6D2;
        color: #F2F5F8;
    }}

    QPushButton#ghostButton {{
        background: {SUPERFICIE};
        color: {TEXTO};
        border: 1px solid {BORDE};
        border-radius: 6px;
        padding: 8px 16px;
    }}

    QPushButton#ghostButton:hover {{
        background: {ACENTO_SUAVE};
        border-color: {ACENTO};
        color: {ACENTO};
    }}

    QPushButton#ghostButton:disabled {{
        background: #F7F9FB;
        border-color: {BORDE_SUAVE};
        color: {TEXTO_TENUE};
    }}

    QPushButton#dangerButton {{
        background: {PELIGRO};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 9px 18px;
        font-weight: 600;
    }}

    QPushButton#dangerButton:hover {{
        background: {PELIGRO_HOVER};
    }}

    QPushButton#dangerGhostButton {{
        background: {SUPERFICIE};
        color: {PELIGRO};
        border: 1px solid #E7C4C0;
        border-radius: 6px;
        padding: 8px 16px;
    }}

    QPushButton#dangerGhostButton:hover {{
        background: {PELIGRO_SUAVE};
        border-color: {PELIGRO};
        color: {PELIGRO_HOVER};
    }}

    QPushButton#dangerGhostButton:disabled {{
        background: #F7F9FB;
        border-color: {BORDE_SUAVE};
        color: {TEXTO_TENUE};
    }}

    /* ---------- Formularios ---------- */
    QLineEdit, QComboBox, QDateEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background: {SUPERFICIE};
        border: 1px solid {BORDE};
        border-radius: 6px;
        padding: 8px 10px;
        selection-background-color: {ACENTO};
        selection-color: #FFFFFF;
        min-height: 20px;
    }}

    QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QSpinBox:hover,
    QDoubleSpinBox:hover {{
        border-color: #BFCBD7;
    }}

    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
    QDoubleSpinBox:focus {{
        border: 1px solid {ACENTO};
    }}

    /* El estilo global quita los botones nativos del spinbox y los deja
       como cajas vacías. Se ocultan: el monto se escribe o se ajusta con
       las flechas del teclado. */
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        width: 0;
        height: 0;
        border: none;
    }}

    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background: #F0F3F6;
        color: {TEXTO_TENUE};
    }}

    QLineEdit[error="true"] {{
        border: 1px solid {PELIGRO};
        background: {PELIGRO_SUAVE};
    }}

    QComboBox QAbstractItemView {{
        background: {SUPERFICIE};
        border: 1px solid {BORDE};
        selection-background-color: {ACENTO_SUAVE};
        selection-color: {TEXTO};
        outline: none;
    }}

    QLabel#fieldLabel {{
        color: {TEXTO_SUAVE};
        font-size: 12px;
        font-weight: 600;
    }}

    QLabel#formError {{
        color: {PELIGRO};
        font-size: 12px;
    }}

    /* ---------- Tablas ---------- */
    QTableWidget, QTableView {{
        background: {SUPERFICIE};
        border: 1px solid {BORDE};
        border-radius: 8px;
        gridline-color: {BORDE_SUAVE};
        selection-background-color: {ACENTO_SUAVE};
        selection-color: {TEXTO};
        outline: none;
    }}

    QHeaderView::section {{
        background: #EEF3F7;
        color: {TEXTO_SUAVE};
        border: none;
        border-bottom: 1px solid {BORDE};
        border-right: 1px solid {BORDE_SUAVE};
        padding: 9px 10px;
        font-size: 12px;
        font-weight: 600;
    }}

    QTableWidget::item {{
        padding: 7px 10px;
        border-bottom: 1px solid {BORDE_SUAVE};
    }}

    QTableWidget::item:selected {{
        background: {ACENTO_SUAVE};
        color: {TEXTO};
    }}

    QTableCornerButton::section {{
        background: #EEF3F7;
        border: none;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 11px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: #C3CED9;
        border-radius: 5px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #A9B7C4;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 11px;
        margin: 0;
    }}

    QScrollBar::handle:horizontal {{
        background: #C3CED9;
        border-radius: 5px;
        min-width: 30px;
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ---------- Etiquetas de estado ---------- */
    QLabel#badge {{
        border-radius: 9px;
        padding: 2px 9px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel#badge[tono="exito"] {{
        background: {EXITO_SUAVE};
        color: {EXITO};
    }}

    QLabel#badge[tono="aviso"] {{
        background: {ADVERTENCIA_SUAVE};
        color: {ADVERTENCIA};
    }}

    QLabel#badge[tono="peligro"] {{
        background: {PELIGRO_SUAVE};
        color: {PELIGRO};
    }}

    QLabel#badge[tono="neutro"] {{
        background: #EDF1F5;
        color: {TEXTO_SUAVE};
    }}

    QLabel#badge[tono="acento"] {{
        background: {ACENTO_SUAVE};
        color: {ACENTO};
    }}

    /* ---------- Login ---------- */
    QFrame#loginBrand {{
        background: {NAVY};
        border: none;
    }}

    QLabel#loginBrandTitle {{
        color: #FFFFFF;
        font-size: 34px;
        font-weight: 700;
    }}

    QLabel#loginBrandSub {{
        color: {NAVY_TENUE};
        font-size: 13px;
    }}

    QLabel#loginBrandFoot {{
        color: #6F8CAB;
        font-size: 11px;
    }}

    QFrame#loginForm {{
        background: {SUPERFICIE};
    }}

    QLabel#loginTitle {{
        font-size: 22px;
        font-weight: 700;
    }}

    QLabel#loginSubtitle {{
        color: {TEXTO_SUAVE};
        font-size: 13px;
    }}

    QLabel#loginHint {{
        color: {TEXTO_TENUE};
        font-size: 11px;
    }}

    QFrame#loginDivider {{
        background: {BORDE_SUAVE};
        max-height: 1px;
        border: none;
    }}

    /* ---------- Separadores y utilidades ---------- */
    QFrame#hline {{
        background: {BORDE_SUAVE};
        max-height: 1px;
        border: none;
    }}

    QLabel#muted {{
        color: {TEXTO_SUAVE};
        font-size: 12px;
    }}

    /* ---------- Diálogos ---------- */
    QDialog {{
        background: {SUPERFICIE};
    }}

    QLabel#dialogTitle {{
        font-size: 17px;
        font-weight: 600;
    }}

    QCheckBox {{
        color: {TEXTO_SUAVE};
        font-size: 12px;
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid #BFCBD7;
        border-radius: 3px;
        background: {SUPERFICIE};
    }}

    QCheckBox::indicator:checked {{
        background: {ACENTO};
        border-color: {ACENTO};
    }}

    QSplitter::handle:horizontal {{
        background: transparent;
        width: 14px;
    }}

    /* ---------- Avisos de situación ---------- */
    QFrame#aviso {{
        border-radius: 8px;
    }}

    QFrame#aviso[tono="exito"] {{
        background: {EXITO_SUAVE};
        border: 1px solid #CFE7DA;
    }}

    QFrame#aviso[tono="aviso"] {{
        background: {ADVERTENCIA_SUAVE};
        border: 1px solid #F1DCB8;
    }}

    QFrame#aviso[tono="peligro"] {{
        background: {PELIGRO_SUAVE};
        border: 1px solid #F2C9C4;
    }}

    QLabel#avisoTexto {{
        color: {TEXTO};
        font-size: 12px;
    }}

    QMessageBox {{
        background: {SUPERFICIE};
    }}
    """
