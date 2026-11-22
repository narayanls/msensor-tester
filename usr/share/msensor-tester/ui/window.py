"""Janela principal: seletor de mouse, abas Sensor / Polling rate e ciclo de captura."""

import errno
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from core import APP_NAME  # noqa: E402
from core.capture import Capture, CaptureError, DeviceDetector, probe_grab  # noqa: E402
from core.debuglog import log  # noqa: E402
from core.devices import list_mice  # noqa: E402
from core.i18n import _  # noqa: E402

from .dialogs import show_busy_dialog, show_permission_dialog  # noqa: E402
from .polling_page import PollingPage  # noqa: E402
from .sensor_page import SensorPage  # noqa: E402


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, settings):
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(940, 800)
        self.settings = settings
        self.devices = []
        self.busy_paths = set()
        self.capture = None
        self.detector = None
        self._detector_timer = None
        self._updating_devices = False

        # ----------------------------------------------------------- header
        header = Adw.HeaderBar()

        self.stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)

        device_box = Gtk.Box(spacing=4)
        self.device_model = Gtk.StringList()
        self.device_dropdown = Gtk.DropDown(model=self.device_model)
        self.device_dropdown.set_tooltip_text(_("Mouse to test"))
        self.device_dropdown.set_factory(self._label_factory(ellipsize=True))
        self.device_dropdown.set_list_factory(self._label_factory(ellipsize=False))
        self.device_dropdown.connect("notify::selected", self._on_device_selected)
        device_box.append(self.device_dropdown)

        self.detect_button = Gtk.Button(icon_name="find-location-symbolic")
        self.detect_button.set_tooltip_text(_("Detect: move the mouse you want to test"))
        self.detect_button.connect("clicked", lambda *_: self.start_detection())
        device_box.append(self.detect_button)

        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        self.refresh_button.set_tooltip_text(_("Refresh the list of mice"))
        self.refresh_button.connect("clicked", lambda *_: self.refresh_devices())
        device_box.append(self.refresh_button)
        header.pack_start(device_box)

        menu = Gio.Menu()
        menu.append(_("Preferences"), "app.preferences")
        menu.append(_("Diagnostics…"), "app.diagnostics")
        menu.append(_("About MSensor Tester"), "app.about")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        menu_button.set_tooltip_text(_("Main menu"))
        header.pack_end(menu_button)

        # ----------------------------------------------------------- banner
        self.banner = Adw.Banner(
            title=_("No permission to read the mice"),
            button_label=_("How to fix"),
        )
        self.banner.connect("button-clicked", lambda *_: show_permission_dialog(self))

        # ------------------------------------------------------------ pages
        self.sensor_page = SensorPage(self)
        self.polling_page = PollingPage(self)
        self.stack.add_titled_with_icon(
            self.sensor_page, "sensor", _("Sensor"), "input-mouse-symbolic"
        )
        self.stack.add_titled_with_icon(
            self.polling_page, "polling", _("Polling rate"), "power-profile-performance-symbolic"
        )
        self.stack.connect("notify::visible-child", self._on_page_changed)

        self.toasts = Adw.ToastOverlay(child=self.stack)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.add_top_bar(self.banner)
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)

        # ---------------------------------------------------------- teclado
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys)

        self.connect("notify::is-active", self._on_active_changed)
        self.connect("close-request", self._on_close_request)

        self.refresh_devices()

    # ================================================================ helpers
    @staticmethod
    def _label_factory(ellipsize):
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            label = Gtk.Label(xalign=0)
            if ellipsize:
                label.set_ellipsize(Pango.EllipsizeMode.END)
                label.set_max_width_chars(26)
                label.set_width_chars(16)
            item.set_child(label)

        def bind(_f, item):
            item.get_child().set_label(item.get_item().get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

    def toast(self, text, timeout=3):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout))

    # =============================================================== devices
    def refresh_devices(self, select_path=None):
        previous = self.current_device()
        wanted_key = previous.key if previous else self.settings.get("device_key")

        self.devices = list_mice()
        log.debug("dispositivos: %d mouse(s) encontrado(s)", len(self.devices))
        for dev in self.devices:
            log.debug("  %s %r bus=%s id=%s phys=%r legível=%s", dev.path, dev.name, dev.bus_label,
                      dev.usb_id, dev.phys, dev.readable)
        self._updating_devices = True
        self.device_model.splice(0, self.device_model.get_n_items(), [])
        self.busy_paths = set()
        for dev in self.devices:
            label = dev.label()
            if not dev.readable:
                label += " — " + _("no permission")
            else:
                state, _err = probe_grab(dev.path)
                if state == "busy":
                    self.busy_paths.add(dev.path)
                    label += " — " + _("in exclusive use")
                elif dev.is_virtual:
                    label += " — " + _("virtual")
            self.device_model.append(label)

        index = None
        for i, dev in enumerate(self.devices):
            if select_path and dev.path == select_path:
                index = i
                break
            if index is None and wanted_key and dev.key == wanted_key:
                index = i
        if index is None:
            usable = [i for i, d in enumerate(self.devices)
                      if d.readable and d.path not in self.busy_paths]
            readable = [i for i, d in enumerate(self.devices) if d.readable]
            index = (usable or readable or [0])[0]
        if self.devices:
            self.device_dropdown.set_selected(index)
        self._updating_devices = False

        self.device_dropdown.set_sensitive(bool(self.devices))
        if not self.devices:
            self.device_model.append(_("No mouse found"))
        missing_permission = any(not d.readable for d in self.devices)
        self.banner.set_revealed(missing_permission)
        self._on_device_selected()

    def current_device(self):
        if not self.devices:
            return None
        index = self.device_dropdown.get_selected()
        if index == Gtk.INVALID_LIST_POSITION or index >= len(self.devices):
            return None
        return self.devices[index]

    def _on_device_selected(self, *_args):
        if self._updating_devices:
            return
        dev = self.current_device()
        if dev:
            log.debug("selecionado: %s %r", dev.path, dev.name)
            self.device_dropdown.set_tooltip_text(
                f"{dev.name}\n{dev.path} · {dev.bus_label} · {dev.usb_id}"
            )
            self.settings.set("device_key", dev.key)

    def start_detection(self):
        if self.capture is not None:
            return
        self.stop_detection()
        paths = [d.path for d in list_mice() if d.readable]
        if not paths:
            show_permission_dialog(self)
            return
        self.detector = DeviceDetector(paths)
        if not self.detector.start():
            self.detector = None
            show_permission_dialog(self)
            return
        self.detect_button.add_css_class("accent")
        self.toast(_("Move the mouse you want to test…"), timeout=4)
        self._detector_deadline = GLib.get_monotonic_time() + 10_000_000
        self._detector_timer = GLib.timeout_add(50, self._poll_detection)

    def _poll_detection(self):
        if self.detector is None:
            return False
        path = self.detector.poll()
        if path or GLib.get_monotonic_time() > self._detector_deadline:
            self.stop_detection()
            if path:
                self.refresh_devices(select_path=path)
                dev = self.current_device()
                if dev:
                    self.toast(_("Selected: {name}").format(name=dev.name))
            else:
                self.toast(_("No movement detected."))
            return False
        return True

    def stop_detection(self):
        if self._detector_timer:
            GLib.source_remove(self._detector_timer)
            self._detector_timer = None
        if self.detector:
            self.detector.stop()
            self.detector = None
        self.detect_button.remove_css_class("accent")

    # =============================================================== capture
    def open_capture(self, grab=None):
        """Abre o mouse selecionado. Retorna Capture ou None (já avisando o usuário)."""
        self.stop_detection()
        dev = self.current_device()
        if dev is None:
            self.toast(_("No mouse selected."))
            return None
        if not dev.readable:
            log.debug("open_capture: %s sem permissão de leitura", dev.path)
            show_permission_dialog(self)
            return None
        state, err = probe_grab(dev.path)
        log.debug("open_capture: sonda de exclusividade em %s → %s (errno=%s)", dev.path, state, err)
        if state == "busy":
            show_busy_dialog(self, dev, self.devices)
            return None
        cap = Capture(dev.path)
        try:
            cap.start()
        except CaptureError as exc:
            if str(exc) == "permission":
                show_permission_dialog(self)
            else:
                self.toast(_("Could not open the mouse: {error}").format(error=exc))
            return None

        if grab is None:
            grab = self.settings.get("grab_device")
        if grab and not cap.set_grab(True):
            if cap.grab_errno == errno.EBUSY:
                reason = _(
                    "another program already has exclusive access to it "
                    "(input-remapper, keyd, kanata…)"
                )
            else:
                reason = os.strerror(cap.grab_errno) if cap.grab_errno else "?"
            self.toast(
                _("Could not lock the cursor: {reason}. The test continues without the lock.").format(
                    reason=reason
                ),
                timeout=6,
            )
        self.capture = cap
        self._set_busy(True)
        log.debug("open_capture: teste iniciado em %s (trava=%s)", dev.path, cap.grabbed)
        return cap

    def close_capture(self):
        cap = self.capture
        self.capture = None
        if cap is not None:
            cap.stop()
        self._set_busy(False)
        return cap

    def _set_busy(self, busy):
        for widget in (self.device_dropdown, self.detect_button, self.refresh_button):
            widget.set_sensitive(not busy and (widget is not self.device_dropdown or bool(self.devices)))

    def select_device(self, path):
        for i, dev in enumerate(self.devices):
            if dev.path == path:
                self.device_dropdown.set_selected(i)
                return True
        return False

    def warn_no_events(self):
        """Avisa quando o teste está aberto há alguns segundos sem nenhum evento."""
        dev = self.current_device()
        name = dev.name if dev else "?"
        log.warning("nenhum evento recebido de %s", dev.path if dev else "?")
        toast = Adw.Toast(
            title=GLib.markup_escape_text(
                _("Nothing received from “{name}”. Is this the mouse you are moving?").format(name=name)
            ),
            timeout=10,
        )
        toast.set_button_label(_("Diagnostics"))
        toast.set_action_name("app.diagnostics")
        self.toasts.add_toast(toast)

    def cancel_tests(self, reason=None):
        self.sensor_page.cancel_test()
        self.polling_page.cancel_test()
        if reason:
            self.toast(reason, timeout=4)

    # ================================================================ events
    def _on_key_pressed(self, _ctrl, keyval, _keycode, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        page = self.stack.get_visible_child()
        if keyval == Gdk.KEY_Escape:
            if self.capture is not None:
                page.on_escape()
                return True
            return False
        if keyval == Gdk.KEY_F1:
            page.on_f1()
            return True
        if keyval == Gdk.KEY_F2:
            page.on_f2()
            return True
        if keyval == Gdk.KEY_F3:
            page.on_f3()
            return True
        return False

    def _on_page_changed(self, *_args):
        if self.capture is not None:
            self.cancel_tests()

    def _on_active_changed(self, *_args):
        # Segurança: se a janela perder o foco com o cursor travado, o usuário
        # não conseguiria apertar Esc aqui — então o teste é interrompido.
        if not self.is_active() and self.capture is not None and self.capture.grabbed:
            self.cancel_tests(_("Test stopped because the window lost focus."))

    def _on_close_request(self, *_args):
        self.stop_detection()
        self.sensor_page.cancel_test()
        self.polling_page.cancel_test()
        self.close_capture()
        return False
