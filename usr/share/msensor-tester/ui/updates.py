"""Interface do atualizador: verificação, diálogo de novidades, download e instalação."""

import shutil
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402

from core import APP_NAME, APP_SLUG, updater  # noqa: E402
from core.debuglog import log  # noqa: E402
from core.i18n import _  # noqa: E402

AUTO_CHECK_DELAY = 3   # segundos após abrir o app
BUSY_RETRY = 5         # segundos entre tentativas enquanto um teste está rodando

# Os diálogos do atualizador usam Adw.AlertDialog (libadwaita >= 1.5). Em versões
# mais antigas, a novidade aparece só como um aviso com link para o GitHub.
_HAS_ALERT = hasattr(Adw, "AlertDialog")


class UpdateController:
    def __init__(self, window):
        self.win = window
        self.checking = False
        self.installing = False
        self.restart_on_close = False
        self._checking_toast = None

    # ------------------------------------------------------------ verificação
    def check(self, manual: bool):
        if self.checking or self.installing:
            return
        self.checking = True
        if manual:
            self._checking_toast = Adw.Toast(title=_("Checking for updates…"), timeout=0)
            self.win.toasts.add_toast(self._checking_toast)

        def worker():
            installed = updater.installed_version()
            try:
                release, error = updater.fetch_latest(), None
            except updater.UpdateError as exc:
                release, error = None, str(exc)
            GLib.idle_add(self._on_checked, release, installed, error, manual)

        threading.Thread(target=worker, daemon=True).start()

    def schedule_auto_check(self):
        GLib.timeout_add_seconds(AUTO_CHECK_DELAY, lambda: (self.check(manual=False), False)[1])

    def _on_checked(self, release, installed, error, manual):
        self.checking = False
        if self._checking_toast is not None:
            self._checking_toast.dismiss()
            self._checking_toast = None
        if error:
            if manual:  # na verificação automática, falhas ficam em silêncio
                self.win.toast(error, 6)
            else:
                log.debug("verificação automática de atualização falhou: %s", error)
            return False
        if not updater.is_newer(release.full_version, installed):
            if manual:
                self.win.toast(_("You have the latest version ({version}).").format(
                    version=updater.display_version(installed)))
            return False
        if manual:
            self.show_release(release, installed)
        else:
            self._show_when_idle(release, installed)
        return False

    def _show_when_idle(self, release, installed):
        """Na verificação automática, não interrompe um teste em andamento.

        Um diálogo aberto no meio da medição tira o foco da janela, o que cancela
        o teste quando o cursor está travado.
        """
        def attempt():
            if self.win.capture is not None:
                return True  # tenta de novo daqui a pouco
            self.show_release(release, installed)
            return False

        if attempt():
            GLib.timeout_add_seconds(BUSY_RETRY, attempt)

    # ------------------------------------------------------- diálogo do release
    def show_release(self, release: updater.Release, installed: str):
        new, current = release.version, updater.display_version(installed)
        if new == current:  # só o pkgrel mudou: mostra a versão completa
            new, current = release.full_version, installed
        body = _("Version {new} is available. You have version {current}.").format(
            new=new, current=current)

        if not _HAS_ALERT:
            toast = Adw.Toast(title=GLib.markup_escape_text(body), timeout=0)
            toast.set_button_label(_("View on GitHub"))
            toast.connect("button-clicked", lambda *_args: self._open_url(release.page_url))
            self.win.toasts.add_toast(toast)
            return

        support = updater.install_support()
        if support == "ok" and not release.asset_url:
            support = "asset"
        reasons = {
            "source": _("{app} is running from the source code, so it can't update itself. "
                        "Download the new version from GitHub.").format(app=APP_NAME),
            "pacman": _("Automatic installation requires pacman (Arch Linux). "
                        "Download the new version from GitHub."),
            "pkexec": _("Automatic installation requires pkexec (polkit). "
                        "Download the new version from GitHub."),
            "asset": _("This release has no package to install. "
                       "Download it from GitHub."),
        }
        if support != "ok":
            body += "\n\n" + reasons[support]

        dialog = Adw.AlertDialog(heading=_("Update available"), body=body)
        if release.notes:
            dialog.set_extra_child(self._notes_widget(release.notes))
        dialog.add_response("later", _("Later"))
        dialog.add_response("github", _("View on GitHub"))
        if support == "ok":
            dialog.add_response("update", _("Update"))
            dialog.set_response_appearance("update", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("update")
        dialog.set_close_response("later")
        dialog.connect("response", self._on_release_response, release)
        dialog.present(self.win)

    @staticmethod
    def _notes_widget(notes: str) -> Gtk.Widget:
        label = Gtk.Label(label=notes, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                          xalign=0, yalign=0)
        scrolled = Gtk.ScrolledWindow(child=label, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=60, max_content_height=220,
                                      propagate_natural_height=True)
        frame = Gtk.Frame(child=scrolled)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=_("What's new"), xalign=0)
        title.add_css_class("heading")
        box.append(title)
        box.append(frame)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        label.set_margin_start(10)
        label.set_margin_end(10)
        return box

    def _open_url(self, url):
        if hasattr(Gtk, "UriLauncher"):  # GTK >= 4.10
            Gtk.UriLauncher(uri=url).launch(self.win, None, None, None)
        else:
            Gtk.show_uri(self.win, url, Gdk.CURRENT_TIME)

    def _on_release_response(self, _dialog, response, release):
        if response == "github":
            self._open_url(release.page_url)
        elif response == "update":
            self._install(release)

    # ---------------------------------------------------- download e instalação
    def _install(self, release: updater.Release):
        if self.installing:
            return
        self.installing = True
        cancel = threading.Event()
        closed = threading.Event()

        bar = Gtk.ProgressBar(show_text=True)
        dialog = Adw.AlertDialog(
            heading=_("Updating {app}").format(app=APP_NAME),
            body=_("Downloading version {version}…").format(version=release.version))
        dialog.set_extra_child(bar)
        dialog.add_response("cancel", _("Cancel"))
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda *_args: cancel.set())
        dialog.connect("closed", lambda *_args: closed.set())
        dialog.present(self.win)

        last = {"pct": -1}

        def on_progress(fraction):
            pct = -2 if fraction is None else int(fraction * 100)
            if pct != last["pct"]:
                last["pct"] = pct
                GLib.idle_add(self._set_progress, bar, fraction)

        def worker():
            try:
                package = updater.download(release, on_progress, cancel)
                GLib.idle_add(self._installing_phase, dialog, bar)
                updater.install(package)
                result = None
            except updater.UpdateCancelled:
                result = "cancelled"
            except updater.UpdateError as exc:
                result = str(exc)
            except Exception as exc:  # noqa: BLE001
                log.exception("erro inesperado na atualização")
                result = _("Unexpected error: {error}").format(error=exc)
            GLib.idle_add(self._finished, dialog, closed, release, result)

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _set_progress(bar, fraction):
        if fraction is None:
            bar.pulse()
        else:
            bar.set_fraction(fraction)
            bar.set_text(f"{int(fraction * 100)}%")
        return False

    @staticmethod
    def _installing_phase(dialog, bar):
        dialog.set_body(_("Installing… Enter your password if the system asks for it."))
        dialog.set_response_enabled("cancel", False)
        dialog.set_can_close(False)
        bar.set_fraction(1.0)
        bar.set_text("")
        return False

    def _finished(self, progress_dialog, closed, release, error):
        self.installing = False
        shown = {"done": False}

        def show_result(*_args):
            if not shown["done"]:
                shown["done"] = True
                self._show_result(release, error)
            return False

        if closed.is_set():
            return show_result()
        progress_dialog.connect("closed", show_result)

        # Se a instalação terminar enquanto o diálogo ainda está abrindo, o
        # fechamento pode ser ignorado; tenta de novo até ele fechar de fato.
        def try_close():
            if closed.is_set():
                return False
            progress_dialog.set_can_close(True)
            progress_dialog.force_close()
            return True

        try_close()
        GLib.timeout_add(250, try_close)
        return False

    def _show_result(self, release, error):
        if error == "cancelled":
            self.win.toast(_("Update cancelled"))
            return False
        if error:
            dialog = Adw.AlertDialog(heading=_("Update failed"), body=error)
            dialog.add_response("close", _("Close"))
            dialog.add_response("github", _("View on GitHub"))
            dialog.set_close_response("close")
            dialog.connect("response", self._on_release_response, release)
            dialog.present(self.win)
            return False

        dialog = Adw.AlertDialog(
            heading=_("Update installed"),
            body=_("{app} {version} was installed. Restart the app to use the new version.").format(
                app=APP_NAME, version=release.version))
        dialog.add_response("later", _("Later"))
        dialog.add_response("restart", _("Restart now"))
        dialog.set_response_appearance("restart", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("restart")
        dialog.set_close_response("later")
        dialog.connect("response", self._on_installed_response)
        dialog.present(self.win)
        return False

    def _on_installed_response(self, dialog, response):
        if response == "restart":
            self.restart_on_close = True
            # A janela só fecha depois que o diálogo terminar de fechar.
            dialog.connect("closed", lambda *_args: self.win.close())

    # ---------------------------------------------------------------- reinício
    def relaunch_if_requested(self):
        """Chamado quando o app realmente encerra (MSensorApp.do_shutdown)."""
        if not self.restart_on_close:
            return
        launcher = shutil.which(APP_SLUG) or f"/usr/bin/{APP_SLUG}"
        # A pausa garante que esta instância já saiu; senão o GTK apenas
        # reativaria a janela antiga em vez de abrir o app novo.
        subprocess.Popen(["sh", "-c", 'sleep 1.5; exec "$0"', launcher],
                         start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
