"""Janela de análise com matplotlib: contagens X, Y, XY × tempo e trajetória X × Y."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

import numpy as np  # noqa: E402

from core import APP_NAME  # noqa: E402
from core.i18n import _  # noqa: E402

from .format import fmt_int  # noqa: E402

SMOOTH_MS = 8.0          # janela da média (125 Hz), igual ao "plot_fit" do MouseTester

COLORS = {
    "x": ("#1c71d8", "#62a0ea"),       # (tema claro, tema escuro)
    "y": ("#c01c28", "#f66151"),
    "single": ("#26a269", "#57e389"),
}
SMOOTH_COLORS = {
    "x": ("#0b3d7a", "#c6dcf7"),
    "y": ("#6d0f16", "#fbc3be"),
    "single": ("#0f5132", "#c4f5d4"),
}


def plot_types():
    return [
        ("xcount", _("xCount vs. Time")),
        ("ycount", _("yCount vs. Time")),
        ("xycount", _("xyCount vs. Time")),
        ("xy", _("X vs. Y")),
    ]


def open_plot_window(parent, log, initial="xycount"):
    try:
        from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - qualquer falha de import do backend
        parent.toast(_("Plots need matplotlib: {error}").format(error=exc), timeout=6)
        return None
    window = PlotWindow(parent, log, initial)
    window.present()
    return window


def smooth(x, y, width=SMOOTH_MS):
    """Média de y em fatias de tempo de `width` ms (ignora NaN)."""
    ok = np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 2:
        return x, y
    idx = np.floor((x - x[0]) / width).astype(np.int64)
    sums = np.bincount(idx, weights=y)
    counts = np.bincount(idx)
    used = counts > 0
    centers = x[0] + (np.nonzero(used)[0] + 0.5) * width
    return centers, sums[used] / counts[used]


class PlotWindow(Adw.Window):
    def __init__(self, parent, log, initial="xycount"):
        super().__init__(transient_for=parent, title=f"{APP_NAME} — {_('Plots')}")
        self.set_default_size(1040, 760)
        from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
        from matplotlib.backends.backend_gtk4 import NavigationToolbar2GTK4 as NavToolbar
        from matplotlib.figure import Figure

        # Cópia dos dados: o log original pode mudar enquanto a janela está aberta.
        self.dx = log.dx().astype(np.float64)
        self.dy = log.dy().astype(np.float64)
        self.ts = log.ts()
        self.cpi = float(log.cpi)
        self.desc = log.desc
        self.n = len(self.ts)
        self._pending = None

        self.types = plot_types()
        keys = [k for k, _l in self.types]

        # -------------------------------------------------------------- UI
        header = Adw.HeaderBar()
        controls = Gtk.Box(spacing=10)
        for side in ("top", "bottom"):
            getattr(controls, f"set_margin_{side}")(8)
        for side in ("start", "end"):
            getattr(controls, f"set_margin_{side}")(12)

        self.type_dd = Gtk.DropDown.new_from_strings([label for _k, label in self.types])
        self.type_dd.set_selected(keys.index(initial) if initial in keys else 2)
        self.type_dd.connect("notify::selected", lambda *_: self.schedule())
        controls.append(self.type_dd)

        last = max(self.n - 1, 1)
        controls.append(self._dim(_("From event")))
        self.start_spin = Gtk.SpinButton.new_with_range(0, last, 1)
        self.start_spin.set_value(0)
        self.start_spin.connect("value-changed", self._on_range_changed)
        controls.append(self.start_spin)
        controls.append(self._dim(_("to")))
        self.end_spin = Gtk.SpinButton.new_with_range(0, last, 1)
        self.end_spin.set_value(last)
        self.end_spin.connect("value-changed", self._on_range_changed)
        controls.append(self.end_spin)

        spacer = Gtk.Box(hexpand=True)
        controls.append(spacer)
        self.lines_check = Gtk.CheckButton(label=_("Lines"))
        self.stems_check = Gtk.CheckButton(label=_("Stems"))
        self.smooth_check = Gtk.CheckButton(label=_("Smoothed (8 ms)"), active=True)
        for check in (self.lines_check, self.stems_check, self.smooth_check):
            check.connect("toggled", lambda *_: self.schedule())
            controls.append(check)

        self.figure = Figure(figsize=(8, 6), dpi=100, layout="constrained")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.set_hexpand(True)
        self.canvas.set_vexpand(True)
        self.navbar = NavToolbar(self.canvas)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(controls)
        box.append(Gtk.Separator())
        box.append(self.canvas)
        box.append(self.navbar)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(box)
        self.set_content(toolbar_view)

        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self.schedule())
        self.refresh()

    @staticmethod
    def _dim(text):
        label = Gtk.Label(label=text)
        label.add_css_class("dim-label")
        return label

    # =============================================================== eventos
    def _on_range_changed(self, spin):
        a = int(self.start_spin.get_value())
        b = int(self.end_spin.get_value())
        if a >= b:
            if spin is self.start_spin:
                self.start_spin.set_value(max(b - 1, 0))
            else:
                self.end_spin.set_value(min(a + 1, self.n - 1))
            return
        self.schedule()

    def schedule(self):
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(120, self._do_refresh)

    def _do_refresh(self):
        self._pending = None
        self.refresh()
        return False

    # ================================================================ tema
    def _theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        return {
            "dark": dark,
            "bg": "#242424" if dark else "#fafafa",
            "fg": "#e8e8e8" if dark else "#1e1e1e",
            "grid": "#ffffff" if dark else "#000000",
        }

    def _color(self, name, theme):
        return COLORS[name][1 if theme["dark"] else 0]

    def _smooth_color(self, name, theme):
        return SMOOTH_COLORS[name][1 if theme["dark"] else 0]

    # =============================================================== desenho
    def _series(self, ax, x, y, name, theme, label=None, allow_smooth=True):
        color = self._color(name, theme)
        many = len(x) > 20000
        ax.plot(x, y, linestyle="none", marker="o", markersize=1.6 if many else 2.4,
                color=color, label=label, rasterized=many)
        if self.lines_check.get_active():
            ax.plot(x, y, "-", lw=0.8, color=color, alpha=0.8, rasterized=many)
        if self.stems_check.get_active():
            ax.vlines(x, 0, np.nan_to_num(y), colors=color, lw=0.6, alpha=0.6, rasterized=many)
        if allow_smooth and self.smooth_check.get_active():
            sx, sy = smooth(x, y)
            ax.plot(sx, sy, "-", lw=1.8, color=self._smooth_color(name, theme))

    def refresh(self):
        theme = self._theme()
        fig = self.figure
        fig.clear()
        fig.set_facecolor(theme["bg"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(theme["bg"])

        kind = self.types[self.type_dd.get_selected()][0]
        # Linhas/hastes/suavizado só se aplicam aos gráficos × tempo.
        for check in (self.lines_check, self.stems_check, self.smooth_check):
            check.set_sensitive(kind != "xy")
        a = int(self.start_spin.get_value())
        b = int(self.end_spin.get_value()) + 1
        ts = self.ts[a:b]
        time_label = _("Time (ms)")

        if kind == "xcount":
            self._series(ax, ts, self.dx[a:b], "single", theme)
            ax.set_xlabel(time_label)
            ax.set_ylabel(_("xCounts"))
        elif kind == "ycount":
            self._series(ax, ts, self.dy[a:b], "single", theme)
            ax.set_xlabel(time_label)
            ax.set_ylabel(_("yCounts"))
        elif kind == "xycount":
            self._series(ax, ts, self.dx[a:b], "x", theme, label="x")
            self._series(ax, ts, self.dy[a:b], "y", theme, label="y")
            ax.set_xlabel(time_label)
            ax.set_ylabel(_("Counts"))
            self._legend(ax, theme)
        elif kind == "xy":
            x = np.cumsum(self.dx[a:b])
            y = np.cumsum(self.dy[a:b])
            color = self._color("single", theme)
            ax.plot(x, y, "-", lw=1.0, color=color, alpha=0.6)
            ax.plot(x, y, linestyle="none", marker="o", markersize=2, color=color)
            ax.set_aspect("equal", adjustable="datalim")
            ax.set_xlabel(_("xCounts"))
            ax.set_ylabel(_("yCounts"))

        title = self.desc or APP_NAME
        if self.cpi > 0:
            title += f"\n{fmt_int(self.cpi)} cpi"
        ax.set_title(title, color=theme["fg"], fontsize=11)
        self._style_axes(ax, theme)
        self.canvas.draw_idle()

    @staticmethod
    def _legend(ax, theme):
        leg = ax.legend(loc="upper right", markerscale=3, frameon=True)
        leg.get_frame().set_facecolor(theme["bg"])
        leg.get_frame().set_edgecolor(theme["fg"])
        leg.get_frame().set_alpha(0.8)
        for text in leg.get_texts():
            text.set_color(theme["fg"])

    @staticmethod
    def _style_axes(ax, theme):
        fg = theme["fg"]
        ax.tick_params(colors=fg, labelsize=9)
        ax.xaxis.label.set_color(fg)
        ax.yaxis.label.set_color(fg)
        for spine in ax.spines.values():
            spine.set_color(fg)
            spine.set_alpha(0.35)
        ax.grid(True, color=theme["grid"], alpha=0.12, lw=0.8)
