"""Pruebas del hash de contraseñas (PBKDF2-SHA256)."""

from __future__ import annotations

import pytest

from app.security import hashear_password, verificar_password


def test_el_hash_guarda_algoritmo_iteraciones_salt_y_digest() -> None:
    partes = hashear_password("clave-segura").split("$")

    assert len(partes) == 4
    assert partes[0] == "pbkdf2_sha256"
    assert partes[1] == "260000"
    assert len(partes[2]) == 32  # salt de 16 bytes en hexadecimal
    assert len(partes[3]) == 64  # digest de 32 bytes en hexadecimal


def test_verifica_la_contrasena_correcta() -> None:
    assert verificar_password("clave-segura", hashear_password("clave-segura"))


def test_rechaza_la_contrasena_incorrecta() -> None:
    assert not verificar_password("otra-clave", hashear_password("clave-segura"))


def test_dos_cuentas_con_la_misma_clave_no_comparten_hash() -> None:
    """El salt aleatorio evita que dos hashes iguales delaten la misma clave."""
    assert hashear_password("clave-segura") != hashear_password("clave-segura")


def test_no_se_puede_hashear_una_clave_vacia() -> None:
    with pytest.raises(ValueError):
        hashear_password("")


def test_verificar_con_clave_vacia_devuelve_false() -> None:
    assert not verificar_password("", hashear_password("clave-segura"))


@pytest.mark.parametrize(
    "guardado",
    [
        "",
        "basura",
        "pbkdf2_sha256$260000$abc",
        "pbkdf2_sha256$260000$abc$def$ghi",
        "otro_algoritmo$260000$abc$def",
    ],
)
def test_un_hash_corrupto_no_autentica(guardado: str) -> None:
    assert not verificar_password("clave-segura", guardado)
