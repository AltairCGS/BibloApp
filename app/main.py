"""Punto de entrada de BibloApp.

Ejecutar desde la raiz del proyecto:
    .venv\\Scripts\\python.exe -m app.main
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app import config
from app.db.database import init_db, sesion
from app.db.seed import sembrar_datos_iniciales
from app.services.auth import sesion_actual
from app.ui.theme import hoja_estilos
from app.ui.views.login import LoginWindow
from app.ui.views.main_window import MainWindow


class Aplicacion:
    """Coordina el ciclo login -> ventana principal -> logout."""

    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.ventana_principal = MainWindow()
        self.ventana_principal.sesion_cerrada.connect(self._al_cerrar_sesion)
        self.login: LoginWindow | None = None

    def iniciar(self) -> None:
        self._mostrar_login()

    def _mostrar_login(self) -> None:
        self.login = LoginWindow()
        self.login.acceso_concedido.connect(self._al_entrar)
        self.login.show()
        self.login.raise_()
        self.login.activateWindow()

    def _al_entrar(self, empleado) -> None:
        sesion_actual.iniciar(empleado)
        if self.login is not None:
            self.login.close()
            self.login.deleteLater()
            self.login = None

        self.ventana_principal.iniciar_sesion()
        self.ventana_principal.show()
        self.ventana_principal.raise_()
        self.ventana_principal.activateWindow()

    def _al_cerrar_sesion(self) -> None:
        sesion_actual.cerrar()
        self._mostrar_login()


def main() -> int:
    config.asegurar_directorios()
    init_db()

    with sesion() as db:
        sembrar_datos_iniciales(db)

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName(config.APP_NAME)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(hoja_estilos())

    controlador = Aplicacion(app)
    controlador.iniciar()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
