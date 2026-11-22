"""Formatação de números conforme o idioma da interface (1.234,5 × 1,234.5)."""

import math

from core.i18n import current_language


def _localize(text):
    if current_language() == "pt_BR":
        return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


def fmt_int(value):
    if value is None:
        return "—"
    return _localize(f"{int(value):,}")


def fmt_num(value, digits=1):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "—"
    return _localize(f"{value:,.{digits}f}")


def fmt_hz(value, digits=1):
    if value is None:
        return "—"
    return f"{fmt_num(value, digits)} Hz"


def fmt_us(value):
    """Intervalo em µs; acima de 10 ms mostra em ms."""
    if value is None:
        return "—"
    if value >= 10_000:
        return f"{fmt_num(value / 1000, 2)} ms"
    return f"{fmt_num(value, 1)} µs"


def fmt_percent(fraction):
    if fraction is None:
        return "—"
    return f"{fmt_num(fraction * 100, 1)} %"
