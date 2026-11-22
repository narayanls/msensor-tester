"""Aba "Sensor": equivalente ao MouseTester (Medir CPI, Coletar, gráficos, CSV)."""

import math
import os
import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

import numpy as np  # noqa: E402

from core.capture import LEFT_DOWN, LEFT_UP  # noqa: E402
from core.debuglog import log  # noqa: E402
from core.i18n import _  # noqa: E402
from core.mouselog import MouseLog  # noqa: E402
from core.stats import summarize  # noqa: E402

from .format import fmt_hz, fmt_int, fmt_num  # noqa: E402
from .test_pad import TestPad  # noqa: E402

IDLE, MEASURE_WAIT, MEASURE, COLLECT_WAIT, COLLECT = range(5)
TICK_MS = 33
MAX_TEST_SECONDS = 600
NO_EVENTS_S = 4
STATE_NAMES = {0: "IDLE", 1: "MEASURE_WAIT", 2: "MEASURE", 3: "COLLECT_WAIT", 4: "COLLECT"}


class SensorPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.settings = win.settings
        self.log = MouseLog()
        self.log.cpi = float(self.settings.get("cpi"))
        self.log.desc = self.settings.get("description")
        self.state = IDLE
        self.capture = None
        self._timer = None
        self._started_us = 0
        self._syncing = False
        self._sx = self._sy = 0
        self._path = 0.0

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        clamp = Adw.Clamp(maximum_size=760, tightening_threshold=560)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        for side in ("top", "bottom"):
            getattr(content, f"set_margin_{side}")(24)
        for side in ("start", "end"):
            getattr(content, f"set_margin_{side}")(16)
        clamp.set_child(content)
        scrolled.set_child(clamp)
        overlay = Gtk.Overlay(child=scrolled, vexpand=True)
        self.pad = TestPad()
        overlay.add_overlay(self.pad)
        self.append(overlay)

        # ------------------------------------------------- cartão de status
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("card")
        card.add_css_class("instructions")
        self.status_title = Gtk.Label(xalign=0, wrap=True)
        self.status_title.add_css_class("title-3")
        self.status_text = Gtk.Label(xalign=0, wrap=True, selectable=False)
        self.status_live = Gtk.Label(xalign=0)
        self.status_live.add_css_class("numeric")
        self.status_live.add_css_class("dim-label")
        card.append(self.status_title)
        card.append(self.status_text)
        card.append(self.status_live)
        content.append(card)

        # ------------------------------------------------------------ botões
        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        row1 = Gtk.Box(spacing=10, homogeneous=True)
        row2 = Gtk.Box(spacing=10, homogeneous=True)

        self.btn_measure = self._button(_("Measure CPI"), "find-location-symbolic", self.start_measure)
        self.btn_collect = self._button(_("Collect (F1)"), "media-record-symbolic", self.start_collect)
        self.btn_collect.add_css_class("suggested-action")
        self.btn_plot = self._button(_("Plots (F3)"), "applications-graphics-symbolic", self.open_plots)
        self.btn_save = self._button(_("Save CSV"), "document-save-symbolic", self.save_csv)
        self.btn_load = self._button(_("Open CSV"), "document-open-symbolic", self.load_csv)
        for b in (self.btn_measure, self.btn_collect):
            row1.append(b)
        for b in (self.btn_plot, self.btn_save, self.btn_load):
            row2.append(b)
        actions.append(row1)
        actions.append(row2)
        content.append(actions)

        # ---------------------------------------------------- configurações
        group = Adw.PreferencesGroup(title=_("Settings"))
        self.desc_row = Adw.EntryRow(title=_("Description"))
        self.desc_row.set_text(self.log.desc)
        self.desc_row.connect("changed", self._on_desc_changed)
        group.add(self.desc_row)

        self.cpi_row = Adw.SpinRow.new_with_range(1, 100000, 50)
        self.cpi_row.set_title(_("CPI (DPI)"))
        self.cpi_row.set_subtitle(_("Type the mouse value or use “Measure CPI”"))
        self.cpi_row.set_digits(0)
        self.cpi_row.set_value(self.log.cpi)
        self.cpi_row.connect("notify::value", self._on_cpi_changed)
        group.add(self.cpi_row)
        content.append(group)

        # --------------------------------------------------------- resultado
        result = Adw.PreferencesGroup(title=_("Result"))
        self.val_events = self._result_row(result, _("Events"))
        self.val_duration = self._result_row(result, _("Duration"))
        self.val_sum_x = self._result_row(result, _("Sum X"))
        self.val_sum_y = self._result_row(result, _("Sum Y"))
        self.val_path = self._result_row(result, _("Path"))
        self.val_rate = self._result_row(result, _("Average report rate"))
        content.append(result)

        self._set_idle_text()
        self._update_summary()
        self._update_buttons()

    # ================================================================ widgets
    @staticmethod
    def _button(label, icon, callback):
        content = Adw.ButtonContent(label=label, icon_name=icon)
        button = Gtk.Button(child=content)
        button.add_css_class("pill")
        button.connect("clicked", lambda *_: callback())
        return button

    @staticmethod
    def _result_row(group, title):
        row = Adw.ActionRow(title=title)
        value = Gtk.Label(label="—", xalign=1, selectable=True)
        value.add_css_class("numeric")
        row.add_suffix(value)
        group.add(row)
        return value

    def _set_status(self, title, text, live=""):
        self.status_title.set_label(title)
        self.status_text.set_label(text)
        self.status_live.set_label(live)
        self.status_live.set_visible(bool(live))

    def _set_idle_text(self):
        self._set_status(
            _("Ready"),
            _(
                "Type the correct CPI, or use “Measure CPI”.\n"
                "Then use “Collect” (records while the left button is held), "
                "or open a CSV file."
            ),
        )

    def _update_buttons(self):
        busy = self.state != IDLE
        self.btn_measure.set_sensitive(not busy)
        self.btn_collect.set_sensitive(not busy)
        self.btn_plot.set_sensitive(not busy)
        self.btn_save.set_sensitive(not busy and self.log.count > 0)
        self.btn_load.set_sensitive(not busy)

    # ============================================================== settings
    def _on_desc_changed(self, row):
        self.log.desc = row.get_text()
        if not self._syncing:
            self.settings.set("description", self.log.desc)

    def _on_cpi_changed(self, row, _pspec):
        self.log.cpi = float(row.get_value())
        if not self._syncing:
            self.settings.set("cpi", self.log.cpi)
        self._update_summary()

    # ============================================================== keyboard
    def on_escape(self):
        self.cancel_test()

    def on_f1(self):
        if self.state == IDLE:
            self.start_collect()

    def on_f2(self):
        pass

    def on_f3(self):
        if self.state == IDLE:
            self.open_plots()

    # ================================================================= tests
    def _begin(self, state):
        if self.state != IDLE:
            return False
        cap = self.win.open_capture()
        if cap is None:
            return False
        self.capture = cap
        self.log.clear()
        self._sx = self._sy = 0
        self._path = 0.0
        self._warned = False
        self.state = state
        log.debug("sensor: estado → %s", STATE_NAMES[state])
        self._started_us = GLib.get_monotonic_time()
        self._timer = GLib.timeout_add(TICK_MS, self._tick)
        self._update_buttons()
        return True

    def _end(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        dropped = self.capture.dropped if self.capture else 0
        if self.capture is not None:
            self.win.close_capture()
            self.capture = None
        if self.state != IDLE:
            log.debug("sensor: fim do teste (%s) — %d relatórios no log", STATE_NAMES[self.state],
                      self.log.count)
        self.state = IDLE
        self.pad.close()
        self.log.finalize()
        self._update_buttons()
        if dropped:
            self.win.toast(
                _("Warning: the kernel discarded data {n} time(s) (buffer overflow).").format(n=dropped),
                timeout=5,
            )

    def _pad_hint(self, key_hint):
        if self.capture is not None and self.capture.grabbed:
            return _("The cursor is locked during the test.") + " " + key_hint
        return key_hint

    def start_measure(self):
        if not self._begin(MEASURE_WAIT):
            return
        dist = self.settings.get("measure_distance_cm")
        self.pad.show_test(
            _("Measure CPI"),
            _(
                "With the cursor over this area:\n"
                "1. Press and hold the left mouse button\n"
                "2. Move the mouse {dist} cm in a straight line (use a ruler)\n"
                "3. Release the left button"
            ).format(dist=fmt_num(dist, 1 if dist % 1 else 0)),
            self._pad_hint(_("Esc cancels.")),
        )

    def start_collect(self):
        if not self._begin(COLLECT_WAIT):
            return
        self.pad.show_test(
            _("Collect"),
            _(
                "With the cursor over this area:\n"
                "1. Press and hold the left mouse button\n"
                "2. Move the mouse\n"
                "3. Release the left button"
            ),
            self._pad_hint(_("Esc cancels.")),
        )

    def cancel_test(self):
        if self.state == IDLE:
            return
        self._end()
        self.log.clear()
        self._update_summary()
        self._update_buttons()
        self._set_status(_("Cancelled"), _("The test was cancelled."))

    def _live_text(self):
        unit = _("counts")
        if self.state == MEASURE:
            counts = math.hypot(self._sx, self._sy)
            text = f"{fmt_int(round(counts))} {unit}"
            cpi = self.log.cpi
            if cpi > 0:
                text += " · " + _("≈ {cm} cm at the current CPI").format(
                    cm=fmt_num(counts / cpi * 2.54, 1)
                )
            return text
        cm = fmt_num(self.log.counts_to_cm(self._path), 1)
        return _("Events: {n}").format(n=fmt_int(self.log.count)) + f" · {cm} cm"

    def _add(self, report):
        self.log.add_report(report)
        self._sx += report.dx
        self._sy += report.dy
        self._path += math.hypot(report.dx, report.dy)

    def _tick(self):
        cap = self.capture
        if cap is None:
            self._timer = None
            return False
        reports = cap.drain()
        for report in reports:
            if self.state == MEASURE_WAIT:
                if report.buttons & LEFT_DOWN:
                    self._add(report)
                    self.state = MEASURE
                    log.debug("sensor: botão esquerdo pressionado → MEASURE")
                    self.pad.set_title(_("Measuring…"), recording=True)
            elif self.state == MEASURE:
                self._add(report)
                if report.buttons & LEFT_UP:
                    self._finish_measure()
                    return False
            elif self.state == COLLECT_WAIT:
                if report.buttons & LEFT_DOWN:
                    self._add(report)
                    self.state = COLLECT
                    log.debug("sensor: botão esquerdo pressionado → COLLECT")
                    self.pad.set_title(_("Collecting…"), recording=True)
            elif self.state == COLLECT:
                self._add(report)
                if report.buttons & LEFT_UP:
                    self._finish_collect()
                    return False

        if self.state in (MEASURE, COLLECT):
            self.pad.set_live(self._live_text())

        waited = (GLib.get_monotonic_time() - self._started_us) / 1e6
        if not self._warned and cap.raw_events == 0 and waited > NO_EVENTS_S:
            self._warned = True
            self.win.warn_no_events()
            self.pad.hint.set_label(
                _("No event has arrived from this device yet. Use Menu → Diagnostics.")
            )
            self.pad.hint.set_visible(True)

        if cap.error:
            self._timer = None
            self._end()
            self._set_status(_("Mouse disconnected"), _("The device stopped responding."))
            self.win.refresh_devices()
            return False

        elapsed = (GLib.get_monotonic_time() - self._started_us) / 1e6
        if elapsed > MAX_TEST_SECONDS:
            self.win.toast(_("Recording time limit reached."))
            self._timer = None
            self.cancel_test()
            return False
        return True

    def _finish_measure(self):
        self._timer = None
        self._end()
        dist_cm = float(self.settings.get("measure_distance_cm"))
        counts = math.hypot(self.log.delta_x(), self.log.delta_y())
        cpi = round(counts / (dist_cm / 2.54))
        if cpi > 0:
            self.cpi_row.set_value(cpi)
            self._set_status(
                _("Measured CPI: {cpi}").format(cpi=fmt_int(cpi)),
                _("{counts} counts over {dist} cm.").format(
                    counts=fmt_int(round(counts)), dist=fmt_num(dist_cm, 1 if dist_cm % 1 else 0)
                )
                + "\n"
                + _("Now use “Collect”."),
            )
        else:
            self._set_status(_("Measure CPI"), _("No movement was recorded. Try again."))
        self._update_summary()

    def _finish_collect(self):
        self._timer = None
        self._end()
        self._show_done()

    def _show_done(self):
        self._update_summary()
        if self.log.count == 0:
            self._set_status(_("No data"), _("No movement was recorded."))
            return
        self._set_status(
            _("Done"),
            _("Press “Plots” (F3) to view the data or “Save CSV” to keep the log."),
        )

    # ================================================================ summary
    def _update_summary(self):
        n = self.log.count
        if n == 0:
            for label in (self.val_events, self.val_duration, self.val_sum_x,
                          self.val_sum_y, self.val_path, self.val_rate):
                label.set_label("—")
            return
        unit = _("counts")
        dx, dy, path = self.log.delta_x(), self.log.delta_y(), self.log.path()
        self.val_events.set_label(fmt_int(n))
        self.val_duration.set_label(f"{fmt_num(self.log.duration_ms() / 1000, 3)} s")
        self.val_sum_x.set_label(f"{fmt_int(dx)} {unit} · {fmt_num(abs(self.log.counts_to_cm(dx)), 1)} cm")
        self.val_sum_y.set_label(f"{fmt_int(dy)} {unit} · {fmt_num(abs(self.log.counts_to_cm(dy)), 1)} cm")
        self.val_path.set_label(f"{fmt_int(round(path))} {unit} · {fmt_num(self.log.counts_to_cm(path), 1)} cm")

        t_us = np.round(self.log.motion_ts() * 1000).astype(np.int64)
        summary = summarize(t_us)
        if summary.valid:
            self.val_rate.set_label(
                _("{avg} (nominal {nominal} Hz)").format(
                    avg=fmt_hz(summary.average_hz), nominal=fmt_int(summary.nominal_hz)
                )
            )
        else:
            self.val_rate.set_label("—")

    # ================================================================== plots
    def open_plots(self):
        if self.log.count < 2:
            self.win.toast(_("No data to plot yet."))
            return
        from .plot_window import open_plot_window

        open_plot_window(self.win, self.log)

    # ==================================================================== CSV
    def _csv_filter(self):
        filters = Gio.ListStore.new(Gtk.FileFilter)
        csv = Gtk.FileFilter()
        csv.set_name(_("CSV files"))
        csv.add_pattern("*.csv")
        csv.add_pattern("*.CSV")
        everything = Gtk.FileFilter()
        everything.set_name(_("All files"))
        everything.add_pattern("*")
        filters.append(csv)
        filters.append(everything)
        return filters

    def _initial_folder(self, dialog):
        folder = self.settings.get("last_folder")
        if folder and os.path.isdir(folder):
            dialog.set_initial_folder(Gio.File.new_for_path(folder))

    def save_csv(self):
        if self.log.count == 0:
            return
        dialog = Gtk.FileDialog(title=_("Save log"), modal=True)
        dialog.set_filters(self._csv_filter())
        self._initial_folder(dialog)
        safe = re.sub(r"[^\w\-. ]+", "_", self.log.desc).strip() or "msensor"
        dialog.set_initial_name(f"{safe}.csv")
        dialog.save(self.win, None, self._on_save_done)

    def _on_save_done(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path:
            return
        try:
            self.log.save(path)
        except OSError as exc:
            self.win.toast(_("Could not save: {error}").format(error=exc.strerror or exc))
            return
        self.settings.set("last_folder", os.path.dirname(path))
        self.win.toast(_("Saved {name}").format(name=os.path.basename(path)))

    def load_csv(self):
        dialog = Gtk.FileDialog(title=_("Open log"), modal=True)
        dialog.set_filters(self._csv_filter())
        self._initial_folder(dialog)
        dialog.open(self.win, None, self._on_open_done)

    def _on_open_done(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path:
            return
        try:
            self.log.load(path)
        except (OSError, ValueError) as exc:
            self.win.toast(_("Could not open the file: {error}").format(error=exc))
            return
        self.settings.set("last_folder", os.path.dirname(path))
        self._syncing = True
        self.desc_row.set_text(self.log.desc)
        if self.log.cpi > 0:
            self.cpi_row.set_value(self.log.cpi)
        self._syncing = False
        self.log.cpi = float(self.cpi_row.get_value())
        self._update_summary()
        self._update_buttons()
        self._set_status(
            _("File loaded"), os.path.basename(path)
        )
        if self.log.count > 1:
            self.open_plots()
