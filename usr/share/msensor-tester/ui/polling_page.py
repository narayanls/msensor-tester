"""Aba "Polling rate": medidor ao vivo + resumo estatístico."""

import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.debuglog import log  # noqa: E402
from core.i18n import _  # noqa: E402
from core.stats import LivePolling, histogram, nearest_rate  # noqa: E402

from .format import fmt_hz, fmt_int, fmt_num, fmt_percent, fmt_us  # noqa: E402
from .live_graph import HistogramView, RateGraph  # noqa: E402

IDLE, ARMED, RUNNING = range(3)
TICK_MS = 16
HIST_EVERY = 8           # atualiza o histograma a cada N ticks
ARM_TIMEOUT_S = 30
NO_EVENTS_S = 4
DURATIONS = (5, 10, 20, 30, 60)


class PollingPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.settings = win.settings
        self.live = LivePolling()
        self.state = IDLE
        self.capture = None
        self._timer = None
        self._ticks = 0
        self._armed_at = 0.0
        self._clock = time.monotonic_ns
        self._dropped = 0

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        clamp = Adw.Clamp(maximum_size=900, tightening_threshold=600)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        for side in ("top", "bottom"):
            getattr(content, f"set_margin_{side}")(20)
        for side in ("start", "end"):
            getattr(content, f"set_margin_{side}")(16)
        clamp.set_child(content)
        scrolled.set_child(clamp)
        self.append(scrolled)

        # ---------------------------------------------------- número grande
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, halign=Gtk.Align.CENTER)
        self.caption = Gtk.Label(label=_("CURRENT"))
        self.caption.add_css_class("hz-caption")
        number_row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.hz_label = Gtk.Label(label="—")
        self.hz_label.add_css_class("hz-value")
        unit = Gtk.Label(label="Hz", valign=Gtk.Align.BASELINE)
        unit.add_css_class("hz-unit")
        number_row.append(self.hz_label)
        number_row.append(unit)
        self.badge = Gtk.Label(halign=Gtk.Align.CENTER)
        self.badge.add_css_class("badge")
        self.badge.set_visible(False)
        hero.append(self.caption)
        hero.append(number_row)
        hero.append(self.badge)
        content.append(hero)

        # ------------------------------------------------------- mini-cards
        tiles = Gtk.Box(spacing=10, homogeneous=True)
        self.tile_avg = self._tile(tiles, _("Average"))
        self.tile_peak = self._tile(tiles, _("Peak"))
        self.tile_reports = self._tile(tiles, _("Reports"))
        self.tile_time = self._tile(tiles, _("Time left"))
        content.append(tiles)

        # ----------------------------------------------------------- controles
        controls = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        dur_label = Gtk.Label(label=_("Duration"))
        dur_label.add_css_class("dim-label")
        self.duration_dd = Gtk.DropDown.new_from_strings([f"{d} s" for d in DURATIONS])
        saved = self.settings.get("polling_duration")
        self.duration_dd.set_selected(DURATIONS.index(saved) if saved in DURATIONS else 1)
        self.duration_dd.connect(
            "notify::selected",
            lambda dd, _p: self.settings.set("polling_duration", DURATIONS[dd.get_selected()]),
        )
        self.start_btn = Gtk.Button()
        self.start_btn.add_css_class("pill")
        self.start_btn.add_css_class("suggested-action")
        self.start_btn.connect("clicked", lambda *_: self.toggle())
        controls.append(dur_label)
        controls.append(self.duration_dd)
        controls.append(self.start_btn)
        content.append(controls)

        self.instructions = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.instructions.add_css_class("dim-label")
        content.append(self.instructions)

        # ------------------------------------------------------------ gráficos
        self.graph = RateGraph(220)
        content.append(self._card(_("Polling rate over time"), self.graph))
        self.hist = HistogramView(170)
        content.append(self._card(_("Interval between reports"), self.hist))

        # ------------------------------------------------------------- resumo
        self.results = Adw.PreferencesGroup(
            title=_("Detailed result"),
            description=_("Pauses in movement are excluded from the calculations."),
        )
        self.rows = {}
        for key, title, subtitle in (
            ("nominal", _("Detected rate"), _("Nearest standard rate")),
            ("average", _("Average rate"), _("Reports per second while moving")),
            ("range", _("Peak / lowest"), _("Best and worst 100 ms windows")),
            ("mean", _("Mean / median interval"), None),
            ("minmax", _("Shortest / longest interval"), None),
            ("std", _("Jitter (standard deviation)"), _("Lower is more stable")),
            ("pct", _("Percentiles 1% / 99%"), None),
            ("within", _("Intervals within ±25%"), _("Share of intervals close to the nominal value")),
            ("count", _("Reports / active time"), None),
            ("pauses", _("Pauses"), _("Times the movement stopped during the test")),
            ("dropped", _("Kernel buffer overflows"), _("Should be zero")),
        ):
            row = Adw.ActionRow(title=title)
            if subtitle:
                row.set_subtitle(subtitle)
            value = Gtk.Label(label="—", xalign=1, selectable=True)
            value.add_css_class("numeric")
            row.add_suffix(value)
            self.results.add(row)
            self.rows[key] = value
        self.results.set_visible(False)
        content.append(self.results)

        self._set_idle()

    # ================================================================ widgets
    @staticmethod
    def _tile(parent, title):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("card")
        box.add_css_class("stat-tile")
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("stat-label")
        value = Gtk.Label(label="—", xalign=0)
        value.add_css_class("stat-value")
        box.append(label)
        box.append(value)
        parent.append(box)
        return value

    @staticmethod
    def _card(title, child):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("card")
        box.add_css_class("graph-card")
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("heading")
        box.append(label)
        box.append(child)
        return box

    def _duration(self):
        return DURATIONS[self.duration_dd.get_selected()]

    def _set_button(self, running):
        if running:
            self.start_btn.set_child(
                Adw.ButtonContent(label=_("Cancel (Esc)"), icon_name="media-playback-stop-symbolic")
            )
            self.start_btn.remove_css_class("suggested-action")
            self.start_btn.add_css_class("destructive-action")
        else:
            self.start_btn.set_child(
                Adw.ButtonContent(label=_("Start test (F1)"), icon_name="media-playback-start-symbolic")
            )
            self.start_btn.remove_css_class("destructive-action")
            self.start_btn.add_css_class("suggested-action")
        self.duration_dd.set_sensitive(not running)

    def _set_idle(self):
        self._set_button(False)
        self.instructions.set_label(
            _(
                "Click “Start test” and move the mouse quickly in all directions "
                "(circles work well). The timer starts with the first movement."
            )
        )

    # ============================================================== keyboard
    def on_escape(self):
        self.cancel_test()

    def on_f1(self):
        if self.state == IDLE:
            self.start_test()

    def on_f2(self):
        pass

    def on_f3(self):
        pass

    # ================================================================= teste
    def toggle(self):
        if self.state == IDLE:
            self.start_test()
        else:
            self.cancel_test()

    def start_test(self):
        if self.state != IDLE:
            return
        cap = self.win.open_capture()
        if cap is None:
            return
        self.capture = cap
        # Os tempos do kernel e o "agora" precisam estar no mesmo relógio.
        self._clock = time.monotonic_ns if cap.monotonic else time.time_ns
        self.live.reset()
        self.state = ARMED
        self._ticks = 0
        self._armed_at = time.monotonic()
        self._dropped = 0
        self._warned = False
        log.debug("polling: teste armado (%d s), aguardando movimento", self._duration())
        self.graph.set_data([], self._duration(), None)
        self.hist.clear()
        self.results.set_visible(False)
        self.badge.set_visible(False)
        self.caption.set_label(_("CURRENT"))
        self.hz_label.set_label("—")
        for tile in (self.tile_avg, self.tile_peak, self.tile_reports):
            tile.set_label("—")
        self.tile_time.set_label(f"{self._duration()} s")
        self._set_button(True)
        hint = _("Move the mouse to start…")
        if cap.grabbed:
            hint += " " + _("The cursor is locked; press Esc to cancel.")
        else:
            hint += " " + _("The cursor moves normally; this does not affect the measurement.")
        self.instructions.set_label(hint)
        self._timer = GLib.timeout_add(TICK_MS, self._tick)

    def cancel_test(self):
        if self.state == IDLE:
            return
        self._stop_capture()
        self.state = IDLE
        self.hz_label.set_label("—")
        self.caption.set_label(_("CURRENT"))
        self.tile_time.set_label("—")
        self._set_idle()
        self.instructions.set_label(_("Test cancelled."))

    def _stop_capture(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        if self.capture is not None:
            self._dropped = self.capture.dropped
            self.win.close_capture()
            self.capture = None

    def _now_us(self):
        return self._clock() // 1000

    def _tick(self):
        cap = self.capture
        if cap is None:
            self._timer = None
            return False

        reports = cap.drain()
        if reports:
            self.live.feed(reports)

        if cap.error:
            self._timer = None
            self._stop_capture()
            self.state = IDLE
            self._set_idle()
            self.instructions.set_label(_("The mouse was disconnected."))
            self.win.refresh_devices()
            return False

        duration = self._duration()
        now = self._now_us()

        if self.state == ARMED:
            if not self._warned and cap.raw_events == 0 and time.monotonic() - self._armed_at > NO_EVENTS_S:
                self._warned = True
                self.win.warn_no_events()
                self.instructions.set_label(
                    _("No event has arrived from this device yet. Use Menu → Diagnostics.")
                )
            if self.live.started:
                log.debug("polling: primeiro movimento → RUNNING")
                self.state = RUNNING
                self.instructions.set_label(
                    _("Keep moving the mouse!")
                    + (" " + _("Esc cancels.") if cap.grabbed else "")
                )
            elif time.monotonic() - self._armed_at > ARM_TIMEOUT_S:
                self._timer = None
                self.cancel_test()
                self.instructions.set_label(_("No movement detected. Test cancelled."))
                return False
            else:
                return True

        hz = self.live.sample(now)
        elapsed = self.live.elapsed_s(now)
        self.hz_label.set_label(fmt_int(round(hz)) if hz else "—")
        self.tile_reports.set_label(fmt_int(len(self.live.t)))
        self.tile_time.set_label(f"{fmt_num(max(duration - elapsed, 0), 1)} s")
        if self.live.peak:
            self.tile_peak.set_label(fmt_hz(self.live.peak, 0))
        valid = [v for _t, v in self.live.history if v]
        if valid:
            self.tile_avg.set_label(fmt_hz(sum(valid) / len(valid), 0))
        nominal = nearest_rate(self.live.peak) if self.live.peak else None
        self.graph.set_data(self.live.history, duration, nominal)

        self._ticks += 1
        if self._ticks % HIST_EVERY == 0:
            intervals = self.live.recent_intervals()
            if len(intervals):
                counts, edges = histogram(intervals, nominal)
                self.hist.set_data(counts, edges, 1e6 / nominal if nominal else None)

        if elapsed >= duration:
            self._timer = None
            self._finish()
            return False
        return True

    def _finish(self):
        self._stop_capture()
        self.state = IDLE
        summary = self.live.summary()
        log.debug("polling: fim — %d relatórios, média=%s Hz, nominal=%s, pico=%s, pausas=%d",
                  summary.reports, summary.average_hz, summary.nominal_hz, summary.peak_hz,
                  summary.pauses)
        self._set_idle()

        if not summary.valid:
            self.instructions.set_label(_("Not enough data. Move the mouse continuously during the test."))
            return

        dev = self.win.current_device()
        if dev is not None and dev.is_virtual:
            self.instructions.set_label(
                _("Test finished.") + " " + _(
                    "Note: this is a virtual device; the rate shown is the rate at which "
                    "the program that creates it forwards the events, not the mouse's."
                )
            )
        else:
            self.instructions.set_label(_("Test finished."))
        self.caption.set_label(_("AVERAGE"))
        self.hz_label.set_label(fmt_int(round(summary.average_hz)))
        self.badge.set_label(_("Detected: {rate} Hz").format(rate=fmt_int(summary.nominal_hz)))
        self.badge.set_visible(True)
        self.tile_avg.set_label(fmt_hz(summary.average_hz, 0))
        self.tile_peak.set_label(fmt_hz(summary.peak_hz, 0))
        self.tile_reports.set_label(fmt_int(summary.reports))
        self.tile_time.set_label("0 s")

        nominal_us = 1e6 / summary.nominal_hz
        counts, edges = histogram(summary.intervals_us, summary.nominal_hz)
        self.hist.set_data(counts, edges, nominal_us)
        self.graph.set_data(self.live.history, self._duration(), summary.nominal_hz)

        r = self.rows
        r["nominal"].set_label(f"{fmt_int(summary.nominal_hz)} Hz · {fmt_us(nominal_us)}")
        r["average"].set_label(fmt_hz(summary.average_hz))
        r["range"].set_label(f"{fmt_hz(summary.peak_hz, 0)} / {fmt_hz(summary.low_hz, 0)}")
        r["mean"].set_label(f"{fmt_us(summary.interval_mean_us)} / {fmt_us(summary.interval_median_us)}")
        r["minmax"].set_label(f"{fmt_us(summary.interval_min_us)} / {fmt_us(summary.interval_max_us)}")
        r["std"].set_label(fmt_us(summary.interval_std_us))
        r["pct"].set_label(f"{fmt_us(summary.interval_p1_us)} / {fmt_us(summary.interval_p99_us)}")
        r["within"].set_label(fmt_percent(summary.within_25))
        r["count"].set_label(f"{fmt_int(summary.reports)} · {fmt_num(summary.active_s, 2)} s")
        r["pauses"].set_label(fmt_int(summary.pauses))
        r["dropped"].set_label(fmt_int(self._dropped))
        self.results.set_visible(True)
