"""Tradução com gettext: textos em inglês no código, traduções em arquivos .po.

Os arquivos-fonte ficam em po/ (na raiz do repositório) e são compilados para
<prefixo>/share/locale/<idioma>/LC_MESSAGES/msensor-tester.mo (veja o Makefile).

Regra de idioma: sistemas em português (pt_BR, pt_PT, pt…) usam pt_BR; qualquer
outro idioma usa inglês. O usuário pode forçar o idioma nas Preferências (vale
após reiniciar o app).
"""

import gettext
import os

from . import APP_SLUG
from .debuglog import log

DOMAIN = APP_SLUG

# main.py fica em <prefixo>/share/msensor-tester/, então as traduções ficam em
# <prefixo>/share/locale. Isso vale tanto instalado (/usr/share/locale) quanto
# rodando direto do repositório (usr/share/locale, depois de "make mo").
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_DIR = os.path.normpath(os.path.join(_APP_DIR, "..", "locale"))

SUPPORTED = ("pt_BR", "en")

_translation = gettext.NullTranslations()
_active = "en"


def system_language():
    """Idioma do sistema, na mesma ordem de prioridade que o gettext usa."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "").split(":")[0].strip()
        if value and value.split(".")[0] not in ("C", "POSIX"):
            return value
    return "en"


def _is_portuguese(lang):
    # "pt_BR.UTF-8", "pt_PT@euro", "pt" → "pt"
    base = lang.split(".")[0].split("@")[0].replace("-", "_").split("_")[0]
    return base.lower() == "pt"


def _load(lang):
    """Carrega o .mo de `lang`; procura primeiro ao lado do app e depois no padrão do sistema."""
    for localedir in (LOCALE_DIR, None):
        try:
            return gettext.translation(DOMAIN, localedir, languages=[lang])
        except OSError:
            continue
    return None


def set_language(choice="auto"):
    global _translation, _active
    if choice not in SUPPORTED:
        choice = "pt_BR" if _is_portuguese(system_language()) else "en"

    _translation, _active = gettext.NullTranslations(), "en"
    if choice == "en":
        return

    translation = _load(choice)
    if translation is None:
        log.warning("tradução %s não encontrada (%s/%s/LC_MESSAGES/%s.mo); usando inglês",
                    choice, LOCALE_DIR, choice, DOMAIN)
        return
    _translation, _active = translation, choice


def current_language():
    return _active


def _(text):
    return _translation.gettext(text)
