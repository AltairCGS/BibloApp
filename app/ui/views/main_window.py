"""Ventana principal con navegación lateral y carga de módulos."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.services.auth import sesion_actual
from app.ui.views.catalogo import CatalogoPage
from app.ui.views.dashboard import DashboardPage
from app.ui.views.placeholder import PlaceholderPage
from app.ui.views.prestamos import PrestamosPage
from app.ui.views.socios import SociosPage
from app.ui.views.vencidos import VencidosPage

# (clave, etiqueta, permiso requerido, titulo de barra, subtitulo de barra)
MODULOS = [
    ("panel", "Panel", None, "Panel", "Resumen general de la biblioteca"),
    ("catalogo", "Catálogo", "catalogo", "Catálogo", "Libros, ejemplares y ubicaciones"),
    ("ubicacion", "Buscar ubicación", None, "Buscar ubicación",
     "Dónde está cada libro en la biblioteca"),
    ("prestamos", "Préstamos", "prestamos", "Préstamos", "Altas, devoluciones y renovaciones"),
    ("socios", "Socios", "socios", "Socios", "Fichas, historial y estado"),
    ("vencidos", "Vencidos", "vencidos", "Vencidos", "Préstamos fuera de plazo"),
    ("reportes", "Reportes", "reportes", "Reportes", "Estadísticas y exportaciones"),
    ("configuracion", "Configuración", "configuracion", "Configuración",
     "Reglas de préstamo, empleados y respaldos"),
]


class MainWindow(QMainWindow):
    """Contenedor principal de la aplicación."""

    sesion_cerrada = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(1280, 800)
        self.setMinimumSize(1080, 680)

        self._botones: dict[str, QPushButton] = {}
        self._paginas: dict[str, QWidget] = {}
        self._indices: dict[str, int] = {}
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)

        self._construir()
        self._grupo.idClicked.connect(self._cambiar_modulo)

    # ------------------------------------------------------------------ UI
    def _construir(self) -> None:
        raiz = QWidget()
        raiz.setObjectName("appRoot")
        self.setCentralWidget(raiz)

        layout = QHBoxLayout(raiz)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar(), 0)
        layout.addWidget(self._contenido(), 1)

    def _sidebar(self) -> QWidget:
        barra = QWidget()
        barra.setObjectName("sidebar")
        barra.setFixedWidth(228)

        layout = QVBoxLayout(barra)
        layout.setContentsMargins(0, 24, 0, 16)
        layout.setSpacing(0)

        marca = QLabel(config.APP_NAME)
        marca.setObjectName("brand")
        marca.setContentsMargins(20, 0, 20, 0)

        sub = QLabel(config.APP_SUBTITLE)
        sub.setObjectName("brandSub")
        sub.setContentsMargins(20, 2, 20, 0)
        sub.setWordWrap(True)

        layout.addWidget(marca)
        layout.addWidget(sub)
        layout.addSpacing(26)

        etiqueta = QLabel("MENÚ")
        etiqueta.setObjectName("sidebarSection")
        layout.addWidget(etiqueta)
        layout.addSpacing(6)

        for indice, (clave, etiqueta_mod, permiso, _titulo, _sub) in enumerate(MODULOS):
            boton = QPushButton(etiqueta_mod)
            boton.setObjectName("navItem")
            boton.setCheckable(True)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setMinimumHeight(40)
            boton.setProperty("permiso", permiso or "")

            self._grupo.addButton(boton, indice)
            self._botones[clave] = boton
            layout.addWidget(boton)

        layout.addStretch(1)
        layout.addWidget(self._pie_sidebar())
        return barra

    def _pie_sidebar(self) -> QWidget:
        pie = QWidget()
        pie.setObjectName("sidebarFooter")

        layout = QVBoxLayout(pie)
        layout.setContentsMargins(20, 14, 20, 6)
        layout.setSpacing(2)

        self.lbl_usuario = QLabel("")
        self.lbl_usuario.setObjectName("userName")

        self.lbl_rol = QLabel("")
        self.lbl_rol.setObjectName("userRole")

        boton = QPushButton("Cerrar sesión")
        boton.setObjectName("logoutButton")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.clicked.connect(self._cerrar_sesion)

        layout.addWidget(self.lbl_usuario)
        layout.addWidget(self.lbl_rol)
        layout.addSpacing(10)
        layout.addWidget(boton)
        return pie

    def _contenido(self) -> QWidget:
        contenedor = QWidget()

        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._topbar())

        self.pila = QStackedWidget()
        layout.addWidget(self.pila, 1)

        for indice, (clave, etiqueta_mod, permiso, titulo, sub) in enumerate(MODULOS):
            pagina = self._crear_pagina(clave, etiqueta_mod, titulo, sub)
            self._paginas[clave] = pagina
            self._indices[clave] = self.pila.addWidget(pagina)

        return contenedor

    def _topbar(self) -> QWidget:
        barra = QWidget()
        barra.setObjectName("topbar")
        barra.setFixedHeight(70)

        layout = QHBoxLayout(barra)
        layout.setContentsMargins(26, 0, 26, 0)
        layout.setSpacing(12)

        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.lbl_titulo = QLabel("Panel")
        self.lbl_titulo.setObjectName("pageTitle")
        self.lbl_subtitulo = QLabel("")
        self.lbl_subtitulo.setObjectName("pageSubtitle")
        textos.addWidget(self.lbl_titulo)
        textos.addWidget(self.lbl_subtitulo)

        layout.addLayout(textos)
        layout.addStretch(1)

        hoy = date.today().strftime("%d/%m/%Y")
        self.lbl_fecha = QLabel(hoy)
        self.lbl_fecha.setObjectName("muted")
        layout.addWidget(self.lbl_fecha)

        return barra

    def _crear_pagina(self, clave: str, etiqueta_mod: str, titulo: str, sub: str) -> QWidget:
        if clave == "panel":
            return DashboardPage()
        if clave == "catalogo":
            return CatalogoPage()
        if clave == "prestamos":
            return PrestamosPage()
        if clave == "socios":
            return SociosPage()
        if clave == "vencidos":
            return VencidosPage()

        descripciones = {
            "catalogo": (
                "Administración de libros y de sus ejemplares físicos.",
                [
                    "Alta, edición y baja de libros (título, autor, ISBN, categoría)",
                    "Cada libro puede tener varias copias con código propio",
                    "Asignación de ubicación a cada ejemplar",
                    "Filtros por categoría, estado y disponibilidad",
                ],
                "Fase 1",
            ),
            "ubicacion": (
                "Encuentra rápidamente dónde está un libro en la biblioteca.",
                [
                    "Búsqueda por título, autor, ISBN, tema o palabra clave",
                    "Resultado con sala, estantería y balda exactas",
                    "Cantidad de copias disponibles en ese momento",
                    "Plano de la biblioteca con zonas clicables",
                ],
                "Fase 2",
            ),
            "prestamos": (
                "Registro de préstamos, devoluciones y renovaciones.",
                [
                    "Préstamo por código de ejemplar y documento del socio",
                    "Vencimiento automático según el tipo de socio",
                    "Devolución y renovación en un clic",
                    "Validación de límite de ejemplares y socios bloqueados",
                ],
                "Fase 1",
            ),
            "socios": (
                "Fichas de lectores con su historial completo.",
                [
                    "Datos personales y tipo de socio",
                    "Préstamos activos e historial de devoluciones",
                    "Estado de bloqueo por vencimientos",
                    "Carnet imprimible con código",
                ],
                "Fase 1",
            ),
            "reportes": (
                "Estadísticas de uso de la colección.",
                [
                    "Libros más prestados y socios más activos",
                    "Préstamos por período y por categoría",
                    "Ejemplares sin movimiento",
                    "Exportación a PDF y Excel",
                ],
                "Fase 3",
            ),
            "configuracion": (
                "Reglas del sistema y gestión de cuentas.",
                [
                    "Días de préstamo por tipo de socio",
                    "Límite de ejemplares y días de gracia",
                    "Alta y edición de empleados y roles",
                    "Respaldo manual y automático de la base",
                ],
                "Fase 0 / 3",
            ),
        }

        descripcion, funciones, fase = descripciones.get(
            clave, ("Módulo en preparación.", [], "")
        )
        return PlaceholderPage(etiqueta_mod, descripcion, funciones, fase)

    # ------------------------------------------------------------- sesion
    def iniciar_sesion(self) -> None:
        self.lbl_usuario.setText(sesion_actual.nombre)
        self.lbl_rol.setText(sesion_actual.rol_legible)

        primer_modulo = None
        for clave, _etiqueta, permiso, _t, _s in MODULOS:
            habilitado = permiso is None or sesion_actual.puede(permiso)
            boton = self._botones[clave]
            boton.setEnabled(habilitado)
            boton.setVisible(habilitado)
            if habilitado and primer_modulo is None:
                primer_modulo = clave

        self._ir_a(primer_modulo or "panel")

    def _cerrar_sesion(self) -> None:
        respuesta = QMessageBox.question(
            self,
            "Cerrar sesión",
            "¿Quieres cerrar la sesión actual?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self.hide()
            self.sesion_cerrada.emit()

    # ----------------------------------------------------------- navegacion
    def _ir_a(self, clave: str) -> None:
        if clave not in self._paginas:
            return

        boton = self._botones[clave]
        if not boton.isEnabled():
            return

        boton.setChecked(True)
        self.pila.setCurrentIndex(self._indices[clave])

        for clave_mod, _e, _p, titulo, sub in MODULOS:
            if clave_mod == clave:
                self.lbl_titulo.setText(titulo)
                self.lbl_subtitulo.setText(sub)
                break

        pagina = self._paginas[clave]
        if hasattr(pagina, "refrescar"):
            pagina.refrescar()

    def _cambiar_modulo(self, indice: int) -> None:
        if 0 <= indice < len(MODULOS):
            self._ir_a(MODULOS[indice][0])

    def showEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        super().showEvent(evento)
        pagina = self.pila.currentWidget()
        if hasattr(pagina, "refrescar"):
            pagina.refrescar()
