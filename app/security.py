"""Hash y verificación de contraseñas con PBKDF2-SHA256 (sin dependencias extra)."""

from __future__ import annotations

import hashlib
import hmac
import os

_ALGORITMO = "pbkdf2_sha256"
_ITERACIONES = 260_000


def hashear_password(password: str) -> str:
    """Devuelve un hash con formato algoritmo$iteraciones$salt$hash."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía")

    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERACIONES
    ).hex()
    return f"{_ALGORITMO}${_ITERACIONES}${salt}${digest}"


def verificar_password(password: str, hash_guardado: str) -> bool:
    """Compara una contraseña en claro contra el hash almacenado."""
    if not password or not hash_guardado:
        return False

    try:
        algoritmo, iteraciones, salt, digest = hash_guardado.split("$")
    except ValueError:
        return False

    if algoritmo != _ALGORITMO:
        return False

    calculado = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iteraciones)
    ).hex()
    return hmac.compare_digest(calculado, digest)
