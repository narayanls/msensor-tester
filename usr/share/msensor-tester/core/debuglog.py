"""Log de depuração.

Ativado com `msensor-tester --debug` (ou MSENSOR_DEBUG=1). Escreve no terminal
e em ~/.cache/msensor-tester/debug.log. Sem --debug, só avisos e erros vão
para o terminal.
"""

import logging
import os
import sys

from . import APP_SLUG

LOGGER_NAME = "msensor"
log = logging.getLogger(LOGGER_NAME)
_enabled = False
_log_file = None


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, APP_SLUG)


def setup(debug=False):
    global _enabled, _log_file
    _enabled = debug
    log.handlers.clear()
    log.propagate = False
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s", "%H:%M:%S")

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    console.setLevel(logging.DEBUG if debug else logging.WARNING)
    log.addHandler(console)

    if debug:
        try:
            os.makedirs(cache_dir(), exist_ok=True)
            _log_file = os.path.join(cache_dir(), "debug.log")
            fh = logging.FileHandler(_log_file, mode="w", encoding="utf-8")
            fh.setFormatter(fmt)
            fh.setLevel(logging.DEBUG)
            log.addHandler(fh)
        except OSError as exc:
            _log_file = None
            log.warning("não foi possível criar o arquivo de log: %s", exc)

    log.setLevel(logging.DEBUG if debug else logging.WARNING)
    if debug:
        log.debug("modo debug ativo; log em %s", _log_file or "(só terminal)")


def enabled():
    return _enabled


def log_file():
    return _log_file
