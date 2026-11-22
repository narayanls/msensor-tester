"""Tradução simples: textos em inglês no código, pt_BR em translations.py.

Sistemas com idioma português usam pt_BR; qualquer outro idioma usa inglês.
O usuário pode forçar o idioma nas Preferências (vale após reiniciar o app).
"""

import os

from .translations import PT_BR

_active = None


def system_language():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value and value not in ("C", "POSIX", "C.UTF-8"):
            return value.split(":")[0]
    return "en"


def set_language(choice="auto"):
    global _active
    if choice == "auto":
        choice = "pt_BR" if system_language().lower().startswith("pt") else "en"
    _active = PT_BR if choice == "pt_BR" else None


def current_language():
    return "pt_BR" if _active is PT_BR else "en"


def _(text):
    if _active is None:
        return text
    return _active.get(text, text)
