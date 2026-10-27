"""Configuración central de BibloApp: rutas, constantes y reglas de negocio."""

from __future__ import annotations

import os
from pathlib import Path

# --- Identidad de la aplicacion -------------------------------------------------
APP_NAME = "BibloApp"
APP_SUBTITLE = "Sistema de gestión bibliotecaria"
VERSION = "0.1.0"

# --- Rutas ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "respaldo"
# BIBLOAPP_DB permite apuntar a otra base. Lo usan las pruebas automatizadas
# para no tocar la base real.
DB_PATH = Path(os.environ.get("BIBLOAPP_DB") or (DATA_DIR / "biblioteca.db"))

# --- Roles ----------------------------------------------------------------------
ROL_ADMIN = "admin"
ROL_BIBLIOTECARIO = "bibliotecario"
ROL_AUXILIAR = "auxiliar"

ROLES = {
    ROL_ADMIN: "Administrador",
    ROL_BIBLIOTECARIO: "Bibliotecario",
    ROL_AUXILIAR: "Auxiliar",
}

# Permisos por rol. Se consultan con puede(rol, "clave").
PERMISOS = {
    ROL_ADMIN: {
        "catalogo",
        "socios",
        "prestamos",
        "vencidos",
        "reportes",
        "configuracion",
        "empleados",
        "respaldos",
    },
    ROL_BIBLIOTECARIO: {"catalogo", "socios", "prestamos", "vencidos", "reportes"},
    ROL_AUXILIAR: {"prestamos", "vencidos"},
}

# --- Estados del ejemplar -------------------------------------------------------
EJEMPLAR_DISPONIBLE = "disponible"
EJEMPLAR_PRESTADO = "prestado"
EJEMPLAR_REPARACION = "en_reparacion"
EJEMPLAR_PERDIDO = "perdido"
EJEMPLAR_BAJA = "dado_de_baja"

ESTADOS_EJEMPLAR = {
    EJEMPLAR_DISPONIBLE: "Disponible",
    EJEMPLAR_PRESTADO: "Prestado",
    EJEMPLAR_REPARACION: "En reparación",
    EJEMPLAR_PERDIDO: "Perdido",
    EJEMPLAR_BAJA: "Dado de baja",
}

# --- Estados del prestamo -------------------------------------------------------
PRESTAMO_ACTIVO = "activo"
PRESTAMO_DEVUELTO = "devuelto"
PRESTAMO_VENCIDO = "vencido"
PRESTAMO_PERDIDO = "perdido"
PRESTAMO_RECUPERADO = "recuperado"

ESTADOS_PRESTAMO = {
    PRESTAMO_ACTIVO: "Activo",
    PRESTAMO_DEVUELTO: "Devuelto",
    PRESTAMO_VENCIDO: "Vencido",
    PRESTAMO_PERDIDO: "Perdido",
    PRESTAMO_RECUPERADO: "Recuperado",
}

# --- Estados de las multas ------------------------------------------------------
MULTA_PENDIENTE = "pendiente"
MULTA_PAGADA = "pagada"
MULTA_ANULADA = "anulada"

ESTADOS_MULTA = {
    MULTA_PENDIENTE: "Pendiente",
    MULTA_PAGADA: "Pagada",
    MULTA_ANULADA: "Anulada",
}

# --- Socios ---------------------------------------------------------------------
TIPO_ESTUDIANTE = "estudiante"
TIPO_DOCENTE = "docente"
TIPO_EXTERNO = "externo"

TIPOS_SOCIO = {
    TIPO_ESTUDIANTE: "Estudiante",
    TIPO_DOCENTE: "Docente",
    TIPO_EXTERNO: "Externo",
}

SOCIO_ACTIVO = "activo"
SOCIO_SUSPENDIDO = "suspendido"
SOCIO_BAJA = "baja"

ESTADOS_SOCIO = {
    SOCIO_ACTIVO: "Activo",
    SOCIO_SUSPENDIDO: "Suspendido",
    SOCIO_BAJA: "Baja",
}

# --- Reglas de prestamo por defecto --------------------------------------------
# Se pueden sobrescribir desde la tabla Configuración (pantalla de ajustes).
DIAS_PRESTAMO = {
    TIPO_ESTUDIANTE: 7,
    TIPO_DOCENTE: 15,
    TIPO_EXTERNO: 5,
}

LIMITE_EJEMPLARES_POR_SOCIO = 3
DIAS_GRACIA_BLOQUEO = 3
DIAS_RENOVACION = 7
MAX_RENOVACIONES = 1

# Monto sugerido de la multa cuando se marca un ejemplar como perdido.
# Se guarda en centavos para no arrastrar errores de redondeo.
MULTA_PERDIDA_CENTAVOS = 1_000_000  # $ 10.000,00

# --- Catalogo de categorias -----------------------------------------------------
CATEGORIAS = [
    "Novela",
    "Cuento",
    "Poesía",
    "Teatro",
    "Ensayo",
    "Historia",
    "Ciencia",
    "Tecnología",
    "Filosofía",
    "Psicología",
    "Arte",
    "Música",
    "Infantil",
    "Juvenil",
    "Cómic",
    "Referencia",
    "Diccionario",
    "Educación",
    "Salud",
    "Cocina",
    "Viajes",
    "Biografía",
]


def puede(rol: str, permiso: str) -> bool:
    """Indica si un rol tiene un permiso determinado."""
    return permiso in PERMISOS.get(rol, set())


def asegurar_directorios() -> None:
    """Crea las carpetas de datos si no existen."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
