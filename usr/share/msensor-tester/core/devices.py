"""Descoberta de mouses via sysfs (/sys/class/input/eventN).

Não precisa de permissão especial: o sysfs é legível por qualquer usuário.
A permissão só é necessária para abrir /dev/input/eventN (ver capture.py).
"""

import glob
import os
import re
import struct
from dataclasses import dataclass

from . import UDEV_RULE_NAME

REL_X = 0x00
REL_Y = 0x01
BTN_LEFT = 0x110

_LONG_BITS = struct.calcsize("l") * 8

_BUS_NAMES = {
    0x03: "USB",
    0x05: "Bluetooth",
    0x06: "Virtual",
    0x11: "PS/2",
    0x18: "I2C",
    0x19: "Host",
}


def _read(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return default


def _parse_bitmask(text):
    """Converte o bitmask do sysfs ("1f0000 0 0 ...", palavras de 'long', MSB primeiro)."""
    value = 0
    for word in text.split():
        try:
            value = (value << _LONG_BITS) | int(word, 16)
        except ValueError:
            return 0
    return value


def _has_bit(mask, bit):
    return bool(mask >> bit & 1)


@dataclass
class MouseDevice:
    path: str          # /dev/input/eventN
    event: int         # N
    name: str
    bustype: int
    vendor: int
    product: int
    phys: str
    uniq: str

    @property
    def readable(self):
        return os.access(self.path, os.R_OK)

    @property
    def bus_label(self):
        return _BUS_NAMES.get(self.bustype, f"bus {self.bustype:#x}")

    @property
    def key(self):
        """Identificador estável (o número do eventN muda entre boots/replugs)."""
        return f"{self.vendor:04x}:{self.product:04x}:{self.name}:{self.phys}"

    @property
    def is_virtual(self):
        """Dispositivo criado por software (uinput), ex.: o de um remapeador."""
        return self.bustype in (0x06, 0x19) or "uinput" in self.phys.lower()

    @property
    def usb_id(self):
        return f"{self.vendor:04x}:{self.product:04x}"

    def label(self):
        return f"{self.name} ({self.bus_label})"


def list_mice():
    """Lista os dispositivos com REL_X, REL_Y e BTN_LEFT (mouses e trackballs)."""
    devices = []
    for sys_dir in glob.glob("/sys/class/input/event*"):
        match = re.search(r"event(\d+)$", sys_dir)
        if not match:
            continue
        dev = os.path.join(sys_dir, "device")
        rel = _parse_bitmask(_read(os.path.join(dev, "capabilities/rel"), "0"))
        key = _parse_bitmask(_read(os.path.join(dev, "capabilities/key"), "0"))
        if not (_has_bit(rel, REL_X) and _has_bit(rel, REL_Y) and _has_bit(key, BTN_LEFT)):
            continue

        def hexval(name):
            try:
                return int(_read(os.path.join(dev, "id", name), "0"), 16)
            except ValueError:
                return 0

        number = int(match.group(1))
        devices.append(
            MouseDevice(
                path=f"/dev/input/event{number}",
                event=number,
                name=_read(os.path.join(dev, "name"), f"event{number}"),
                bustype=hexval("bustype"),
                vendor=hexval("vendor"),
                product=hexval("product"),
                phys=_read(os.path.join(dev, "phys")),
                uniq=_read(os.path.join(dev, "uniq")),
            )
        )

    # Dispositivos reais (USB/Bluetooth) primeiro, virtuais por último.
    def sort_key(d):
        virtual = d.bustype in (0x06, 0x19)
        return (virtual, not d.readable, d.event)

    devices.sort(key=sort_key)
    return devices


def virtual_counterparts(device, mice):
    """Dispositivos virtuais que provavelmente repassam os eventos de `device`.

    Remapeadores costumam criar um mouse virtual com o nome do original
    (ex.: "Mouse Remapper (INSTANT USB GAMING MOUSE )").
    """
    base = device.name.strip().lower()
    virtual = [m for m in mice if m.path != device.path and m.is_virtual and m.readable]
    named = [m for m in virtual if base and base in m.name.lower()]
    return named or virtual


def udev_rule_installed():
    for base in ("/usr/lib/udev/rules.d", "/etc/udev/rules.d", "/lib/udev/rules.d"):
        if os.path.exists(os.path.join(base, UDEV_RULE_NAME)):
            return True
    return False


def bundled_udev_rule():
    """Caminho da regra quando o app roda direto da árvore do repositório."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.normpath(
        os.path.join(here, "..", "..", "..", "lib", "udev", "rules.d", UDEV_RULE_NAME)
    )
    return candidate if os.path.exists(candidate) else None
