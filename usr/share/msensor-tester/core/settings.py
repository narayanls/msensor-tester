"""Preferências em ~/.config/msensor-tester/settings.json."""

import json
import os

from . import APP_SLUG

DEFAULTS = {
    "cpi": 400.0,
    "description": "MSensor Tester",
    "device_key": "",
    # Trava (EVIOCGRAB) desligada por padrão: falha quando outro programa já tem
    # o mouse com exclusividade. A chave antiga "lock_cursor" é descartada.
    "grab_device": False,
    "polling_duration": 10,
    "measure_distance_cm": 10.0,
    "language": "auto",        # auto | pt_BR | en
    "last_folder": "",
}


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_SLUG)


class Settings:
    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), "settings.json")
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                stored = json.load(fh)
        except (OSError, ValueError):
            return
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
                    self.data[key] = value
                elif key in DEFAULTS and isinstance(DEFAULTS[key], float) and isinstance(value, int):
                    self.data[key] = float(value)

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value, save=True):
        self.data[key] = value
        if save:
            self.save()
