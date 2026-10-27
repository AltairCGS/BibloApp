"""Utilidades de texto compartidas por los servicios."""

from __future__ import annotations

import unicodedata


def normalizar(texto: str | None) -> str:
    """Pasa a minúsculas y quita tildes para comparar de forma tolerante."""
    if not texto:
        return ""

    plano = unicodedata.normalize("NFKD", str(texto))
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return plano.lower().strip()
