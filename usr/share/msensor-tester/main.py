#!/usr/bin/env python3
"""MSensor Tester: teste de rastreio do sensor e de polling rate de mouses."""

import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from core import APP_ID, APP_NAME, APP_VERSION  # noqa: E402
from core import debuglog, i18n  # noqa: E402
from core.settings import Settings  # noqa: E402

USAGE = f"""{APP_NAME} {APP_VERSION}

Uso: msensor-tester [opções]

  -d, --debug        log detalhado no terminal e em ~/.cache/msensor-tester/debug.log
  --diagnose [SEG]   imprime um relatório de diagnóstico (escuta os mouses por SEG s, padrão 5)
  -v, --version      mostra a versão
  -h, --help         mostra esta ajuda
"""


def parse_args(argv):
    """Separa as opções do app das que vão para o GTK."""
    opts = {"debug": os.environ.get("MSENSOR_DEBUG", "") not in ("", "0"), "diagnose": None}
    rest = [argv[0]]
    args = argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-d", "--debug"):
            opts["debug"] = True
        elif arg == "--diagnose":
            seconds = 5
            if i + 1 < len(args) and args[i + 1].isdigit():
                seconds = int(args[i + 1])
                i += 1
            opts["diagnose"] = seconds
        elif arg in ("-v", "--version"):
            print(f"{APP_NAME} {APP_VERSION}")
            sys.exit(0)
        elif arg in ("-h", "--help"):
            print(USAGE)
            sys.exit(0)
        else:
            rest.append(arg)
        i += 1
    return opts, rest


import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

CSS = """
.hz-value {
  font-size: 76px;
  font-weight: 800;
  font-feature-settings: "tnum";
}
.hz-unit { font-size: 22px; font-weight: 600; opacity: 0.6; }
.hz-caption { font-size: 0.9em; font-weight: bold; opacity: 0.65; letter-spacing: 1px; }
.stat-tile { padding: 12px 14px; }
.stat-value { font-size: 22px; font-weight: 700; font-feature-settings: "tnum"; }
.stat-label { font-size: 0.85em; opacity: 0.7; }
.instructions { padding: 18px 20px; }
.recording { color: @error_color; }
.badge {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.85em;
  font-weight: bold;
  background: alpha(@accent_bg_color, 0.15);
  color: @accent_color;
}
.numeric { font-feature-settings: "tnum"; }
.graph-card { padding: 10px 12px 6px 12px; }
.test-pad {
  background: @window_bg_color;
  border: 2px dashed alpha(@accent_color, 0.55);
  border-radius: 18px;
  margin: 12px;
}
"""


class MSensorApp(Adw.Application):
    def __init__(self, settings):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = settings
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(APP_ID)

        provider = Gtk.CssProvider()
        try:
            provider.load_from_string(CSS)  # GTK >= 4.12
        except AttributeError:
            provider.load_from_data(CSS, -1)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        for name, callback, accels in (
            ("quit", lambda *_: self.quit(), ["<primary>q"]),
            ("preferences", self._on_preferences, ["<primary>comma"]),
            ("about", self._on_about, []),
            ("diagnostics", self._on_diagnostics, []),
            ("check-updates", self._on_check_updates, []),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    def do_activate(self):
        from ui.window import MainWindow

        if self.window is None:
            self.window = MainWindow(self, self.settings)
            self.window.updates.schedule_auto_check()
        self.window.present()

    def do_shutdown(self):
        # Depois de "Reiniciar agora" no atualizador, abre a versão nova.
        if self.window is not None:
            self.window.updates.relaunch_if_requested()
        Adw.Application.do_shutdown(self)

    def _on_check_updates(self, *_args):
        if self.window:
            self.window.updates.check(manual=True)

    def _on_preferences(self, *_args):
        from ui.dialogs import show_preferences

        if self.window:
            show_preferences(self.window)

    def _on_diagnostics(self, *_args):
        from ui.diagnostics_window import DiagnosticsWindow

        if self.window:
            DiagnosticsWindow(self.window).present()

    def _on_about(self, *_args):
        from ui.dialogs import show_about

        if self.window:
            show_about(self.window)


def main():
    opts, argv = parse_args(sys.argv)
    debuglog.setup(opts["debug"])
    settings = Settings()
    i18n.set_language(settings.get("language"))

    if opts["diagnose"] is not None:
        from core.diagnostics import run_cli

        return run_cli(opts["diagnose"])

    log = debuglog.log
    log.debug("%s %s — Python %s, GTK %d.%d.%d, libadwaita %d.%d.%d", APP_NAME, APP_VERSION,
              sys.version.split()[0], Gtk.get_major_version(), Gtk.get_minor_version(),
              Gtk.get_micro_version(), Adw.get_major_version(), Adw.get_minor_version(),
              Adw.get_micro_version())
    log.debug("sessão: XDG_SESSION_TYPE=%s XDG_CURRENT_DESKTOP=%s idioma=%s config=%s",
              os.environ.get("XDG_SESSION_TYPE"), os.environ.get("XDG_CURRENT_DESKTOP"),
              i18n.current_language(), settings.path)
    app = MSensorApp(settings)
    return app.run(argv)


if __name__ == "__main__":
    sys.exit(main())
