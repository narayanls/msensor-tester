"""Menu → Diagnóstico: mostra o relatório de core/diagnostics.py."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from core import APP_NAME  # noqa: E402
from core import debuglog  # noqa: E402
from core.diagnostics import build_report  # noqa: E402
from core.i18n import _  # noqa: E402

LISTEN_SECONDS = 5


class DiagnosticsWindow(Adw.Window):
    def __init__(self, parent):
        super().__init__(transient_for=parent, title=f"{APP_NAME} — " + _("Diagnostics"))
        self.set_default_size(860, 700)
        self.parent_win = parent
        self._running = False

        header = Adw.HeaderBar()
        self.run_button = Gtk.Button(
            child=Adw.ButtonContent(label=_("Run again"), icon_name="view-refresh-symbolic")
        )
        self.run_button.connect("clicked", lambda *_: self.run())
        header.pack_start(self.run_button)
        self.copy_button = Gtk.Button(
            child=Adw.ButtonContent(label=_("Copy"), icon_name="edit-copy-symbolic")
        )
        self.copy_button.add_css_class("suggested-action")
        self.copy_button.connect("clicked", lambda *_: self.copy())
        header.pack_end(self.copy_button)

        self.banner = Adw.Banner()
        self.banner.set_revealed(True)

        self.view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        for side in ("top", "bottom", "left", "right"):
            getattr(self.view, f"set_{side}_margin")(14)
        scrolled = Gtk.ScrolledWindow(child=self.view, vexpand=True)

        self.toasts = Adw.ToastOverlay(child=scrolled)
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.add_top_bar(self.banner)
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)

        self.run()

    def run(self):
        if self._running:
            return
        self._running = True
        self.run_button.set_sensitive(False)
        self.copy_button.set_sensitive(False)
        self.view.get_buffer().set_text(_("Collecting information…"))
        dev = self.parent_win.current_device()
        selected = dev.path if dev else None
        self._progress(LISTEN_SECONDS)

        def worker():
            try:
                report = build_report(
                    LISTEN_SECONDS,
                    progress=lambda s: GLib.idle_add(self._progress, s),
                    selected_path=selected,
                )
            except Exception as exc:  # noqa: BLE001 - o relatório nunca deve derrubar o app
                debuglog.log.exception("diagnóstico falhou")
                report = _("The diagnostic failed") + f": {exc!r}"
            GLib.idle_add(self._done, report)

        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, seconds):
        if seconds > 0:
            self.banner.set_title(
                _("Move the mouse and click now… {s} s").format(s=seconds)
            )
        else:
            self.banner.set_title(_("Analyzing…"))
        return False

    def _done(self, report):
        self._running = False
        self.view.get_buffer().set_text(report)
        self.run_button.set_sensitive(True)
        self.copy_button.set_sensitive(True)
        log_file = debuglog.log_file()
        if log_file:
            self.banner.set_title(_("Done. Debug log: {path}").format(path=log_file))
        else:
            self.banner.set_title(_("Done. Copy the report and send it along with your question."))
        debuglog.log.debug("relatório de diagnóstico:\n%s", report)
        return False

    def copy(self):
        buf = self.view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        Gdk.Display.get_default().get_clipboard().set(text)
        self.toasts.add_toast(Adw.Toast(title=_("Report copied"), timeout=2))
