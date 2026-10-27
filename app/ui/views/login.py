"""Pantalla de inicio de sesión de empleados."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.services.auth import autenticar


class LoginWindow(QWidget):
    """Ventana de login. Emite acceso_concedido(empleado) al validar."""

    acceso_concedido = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} - Iniciar sesión")
        self.setObjectName("loginRoot")
        self.setFixedSize(940, 560)
        self._construir()
        self._centrar()

    # ------------------------------------------------------------------ UI
    def _construir(self) -> None:
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._panel_marca(), 0)
        raiz.addWidget(self._panel_formulario(), 1)

    def _panel_marca(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("loginBrand")
        panel.setFixedWidth(380)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(44, 48, 44, 40)
        layout.setSpacing(10)

        titulo = QLabel(config.APP_NAME)
        titulo.setObjectName("loginBrandTitle")

        subtitulo = QLabel(config.APP_SUBTITLE)
        subtitulo.setObjectName("loginBrandSub")
        subtitulo.setWordWrap(True)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addStretch(1)

        detalle = QLabel(
            "Catálogo, préstamos y ubicación de cada ejemplar "
            "en un solo lugar."
        )
        detalle.setObjectName("loginBrandSub")
        detalle.setWordWrap(True)
        layout.addWidget(detalle)

        layout.addStretch(1)

        pie = QLabel(f"Versión {config.VERSION}")
        pie.setObjectName("loginBrandFoot")
        layout.addWidget(pie)

        return panel

    def _panel_formulario(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("loginForm")

        contenedor = QVBoxLayout(panel)
        contenedor.setContentsMargins(64, 0, 64, 0)
        contenedor.addStretch(1)

        caja = QVBoxLayout()
        caja.setSpacing(6)

        titulo = QLabel("Iniciar sesión")
        titulo.setObjectName("loginTitle")

        subtitulo = QLabel("Accede con tu cuenta de empleado.")
        subtitulo.setObjectName("loginSubtitle")

        divisoria = QFrame()
        divisoria.setObjectName("loginDivider")
        divisoria.setFixedHeight(1)

        caja.addWidget(titulo)
        caja.addWidget(subtitulo)
        caja.addSpacing(14)
        caja.addWidget(divisoria)
        caja.addSpacing(18)

        lbl_usuario = QLabel("Usuario")
        lbl_usuario.setObjectName("fieldLabel")
        self.campo_usuario = QLineEdit()
        self.campo_usuario.setPlaceholderText("Tu usuario de empleado")
        self.campo_usuario.setClearButtonEnabled(True)

        lbl_password = QLabel("Contraseña")
        lbl_password.setObjectName("fieldLabel")
        self.campo_password = QLineEdit()
        self.campo_password.setPlaceholderText("Tu contraseña")
        self.campo_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("formError")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setVisible(False)

        self.btn_entrar = QPushButton("Ingresar")
        self.btn_entrar.setObjectName("primaryButton")
        self.btn_entrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_entrar.setMinimumHeight(40)

        caja.addWidget(lbl_usuario)
        caja.addWidget(self.campo_usuario)
        caja.addSpacing(12)
        caja.addWidget(lbl_password)
        caja.addWidget(self.campo_password)
        caja.addSpacing(8)
        caja.addWidget(self.lbl_error)
        caja.addSpacing(10)
        caja.addWidget(self.btn_entrar)
        caja.addSpacing(16)

        pista = QLabel("Cuentas de prueba: admin / admin123")
        pista.setObjectName("loginHint")
        caja.addWidget(pista)

        contenedor.addLayout(caja)
        contenedor.addStretch(1)
        return panel

    # ------------------------------------------------------------- eventos
    def _conectar(self) -> None:
        self.btn_entrar.clicked.connect(self._intentar_acceso)
        self.campo_password.returnPressed.connect(self._intentar_acceso)
        self.campo_usuario.returnPressed.connect(self.campo_password.setFocus)

    def _centrar(self) -> None:
        pantalla = self.screen()
        if pantalla is None:
            return
        geo = pantalla.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _marcar_error(self, mensaje: str) -> None:
        self.lbl_error.setText(mensaje)
        self.lbl_error.setVisible(bool(mensaje))
        for campo in (self.campo_usuario, self.campo_password):
            campo.setProperty("error", "true" if mensaje else "false")
            campo.style().unpolish(campo)
            campo.style().polish(campo)

    def _intentar_acceso(self) -> None:
        self._marcar_error("")
        usuario = self.campo_usuario.text().strip()
        password = self.campo_password.text()

        if not usuario:
            self._marcar_error("Escribe tu usuario.")
            self.campo_usuario.setFocus()
            return
        if not password:
            self._marcar_error("Escribe tu contraseña.")
            self.campo_password.setFocus()
            return

        self.btn_entrar.setEnabled(False)
        self.btn_entrar.setText("Verificando...")
        try:
            ok, mensaje, empleado = autenticar(usuario, password)
        finally:
            self.btn_entrar.setEnabled(True)
            self.btn_entrar.setText("Ingresar")

        if not ok or empleado is None:
            self._marcar_error(mensaje)
            self.campo_password.clear()
            self.campo_password.setFocus()
            return

        self.campo_password.clear()
        self.acceso_concedido.emit(empleado)

    # ----------------------------------------------------------- ciclo vida
    def showEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        super().showEvent(evento)
        self._conectar_si_hace_falta()
        self.campo_usuario.setFocus()

    def _conectar_si_hace_falta(self) -> None:
        if getattr(self, "_conectado", False):
            return
        self._conectar()
        self._conectado = True
