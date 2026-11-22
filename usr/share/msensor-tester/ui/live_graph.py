"""Gráficos leves desenhados com Cairo para a atualização ao vivo (60 fps).

O matplotlib fica para a janela de análise; aqui precisamos de velocidade.
"""

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gdk, Gtk, Pango, PangoCairo  # noqa: E402

from core.i18n import _  # noqa: E402

from .format import fmt_int, fmt_num  # noqa: E402

FALLBACK_ACCENT = "#3584e4"
PAD_LEFT = 52
PAD_RIGHT = 12
PAD_TOP = 10
PAD_BOTTOM = 26


def nice_step(span, target_ticks=5):
    if span <= 0:
        return 1
    raw = span / target_ticks
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            return mult * mag
    return 10 * mag


class _BaseGraph(Gtk.DrawingArea):
    def __init__(self, height):
        super().__init__()
        self.set_content_height(height)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)
        style = Adw.StyleManager.get_default()
        style.connect("notify::dark", lambda *_: self.queue_draw())
        if hasattr(style, "get_accent_color_rgba"):
            style.connect("notify::accent-color", lambda *_: self.queue_draw())

    # ---------------------------------------------------------------- cores
    def _fg(self):
        if hasattr(self, "get_color"):
            return self.get_color()
        rgba = Gdk.RGBA()
        rgba.parse("#ffffff" if Adw.StyleManager.get_default().get_dark() else "#000000")
        return rgba

    def _accent(self):
        style = Adw.StyleManager.get_default()
        if hasattr(style, "get_accent_color_rgba"):
            return style.get_accent_color_rgba()
        rgba = Gdk.RGBA()
        rgba.parse(FALLBACK_ACCENT)
        return rgba

    # ---------------------------------------------------------------- texto
    def _text(self, cr, text, x, y, align="left", valign="middle", alpha=0.65, size=8.5):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription.from_string(f"Sans {size}")
        layout.set_font_description(font)
        layout.set_text(text, -1)
        w, h = layout.get_pixel_size()
        if align == "right":
            x -= w
        elif align == "center":
            x -= w / 2
        if valign == "middle":
            y -= h / 2
        elif valign == "bottom":
            y -= h
        fg = self._fg()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, alpha)
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)

    def _grid(self, cr, x0, y0, x1, y1, xmax, ymax, xstep, ystep, xfmt, yfmt):
        fg = self._fg()
        w = x1 - x0
        h = y1 - y0
        cr.set_line_width(1)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.10)
        v = 0.0
        while v <= ymax + 1e-9:
            y = y1 - v / ymax * h
            cr.move_to(x0, round(y) + 0.5)
            cr.line_to(x1, round(y) + 0.5)
            v += ystep
        cr.stroke()
        v = 0.0
        while v <= ymax + 1e-9:
            y = y1 - v / ymax * h
            self._text(cr, yfmt(v), x0 - 6, y, align="right")
            v += ystep
        v = 0.0
        while v <= xmax + 1e-9:
            x = x0 + v / xmax * w
            self._text(cr, xfmt(v), x, y1 + 5, align="center", valign="top")
            v += xstep
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.25)
        cr.move_to(x0, round(y1) + 0.5)
        cr.line_to(x1, round(y1) + 0.5)
        cr.stroke()

    def _empty(self, cr, width, height, text):
        self._text(cr, text, width / 2, height / 2, align="center", alpha=0.45, size=10)


class RateGraph(_BaseGraph):
    """Polling rate (Hz) ao longo do teste."""

    def __init__(self, height=220):
        super().__init__(height)
        self.points = []        # [(t_s, hz | None)]
        self.duration = 10.0
        self.nominal = None

    def set_data(self, points, duration, nominal=None):
        self.points = points
        self.duration = max(duration, 1.0)
        self.nominal = nominal
        self.queue_draw()

    def clear(self):
        self.points = []
        self.nominal = None
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        x0, y0 = PAD_LEFT, PAD_TOP
        x1, y1 = width - PAD_RIGHT, height - PAD_BOTTOM
        if x1 <= x0 or y1 <= y0:
            return
        values = [hz for _t, hz in self.points if hz is not None]
        top = max(values) if values else 0
        if self.nominal:
            top = max(top, self.nominal)
        if top <= 0:
            top = 1000
        ystep = nice_step(top * 1.15)
        ymax = math.ceil(top * 1.12 / ystep) * ystep
        xstep = nice_step(self.duration, 6)
        self._grid(
            cr, x0, y0, x1, y1, self.duration, ymax, xstep, ystep,
            lambda v: f"{fmt_num(v, 0 if xstep >= 1 else 1)} s",
            lambda v: fmt_int(v),
        )

        if self.nominal:
            fg = self._fg()
            y = y1 - self.nominal / ymax * (y1 - y0)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.45)
            cr.set_dash([4, 4])
            cr.move_to(x0, round(y) + 0.5)
            cr.line_to(x1, round(y) + 0.5)
            cr.stroke()
            cr.set_dash([])
            self._text(cr, f"{fmt_int(self.nominal)} Hz", x1 - 4, y - 3, align="right",
                       valign="bottom", alpha=0.7)

        if not values:
            self._empty(cr, width, height, _("Move the mouse to start"))
            return

        accent = self._accent()
        sx = (x1 - x0) / self.duration
        sy = (y1 - y0) / ymax

        # Área preenchida + linha, interrompendo nos trechos parados (None).
        segments = []
        current = []
        for t, hz in self.points:
            if hz is None:
                if current:
                    segments.append(current)
                current = []
                continue
            current.append((x0 + min(t, self.duration) * sx, y1 - hz * sy))
        if current:
            segments.append(current)

        for seg in segments:
            if len(seg) < 2:
                continue
            cr.move_to(seg[0][0], y1)
            for x, y in seg:
                cr.line_to(x, y)
            cr.line_to(seg[-1][0], y1)
            cr.close_path()
            cr.set_source_rgba(accent.red, accent.green, accent.blue, 0.15)
            cr.fill()
            cr.move_to(*seg[0])
            for x, y in seg[1:]:
                cr.line_to(x, y)
            cr.set_source_rgba(accent.red, accent.green, accent.blue, 1.0)
            cr.set_line_width(2)
            cr.set_line_join(1)  # ROUND
            cr.stroke()


class HistogramView(_BaseGraph):
    """Distribuição dos intervalos entre relatórios."""

    def __init__(self, height=170):
        super().__init__(height)
        self.counts = None
        self.edges = None
        self.nominal_us = None

    def set_data(self, counts, edges, nominal_us=None):
        self.counts = counts
        self.edges = edges
        self.nominal_us = nominal_us
        self.queue_draw()

    def clear(self):
        self.counts = None
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        x0, y0 = PAD_LEFT, PAD_TOP
        x1, y1 = width - PAD_RIGHT, height - PAD_BOTTOM
        if x1 <= x0 or y1 <= y0:
            return
        if self.counts is None or len(self.counts) == 0 or self.counts.sum() == 0:
            self._grid(cr, x0, y0, x1, y1, 3000, 100, 500, 25,
                       lambda v: fmt_int(v), lambda v: f"{fmt_int(v)}%")
            self._empty(cr, width, height, _("No data yet"))
            return

        total = float(self.counts.sum())
        pct = self.counts / total * 100.0
        xmax = float(self.edges[-1])
        top = float(pct.max())
        ystep = nice_step(top * 1.1, 4)
        ymax = math.ceil(top * 1.08 / ystep) * ystep
        use_ms = xmax >= 5000
        xstep = nice_step(xmax, 6)

        def xfmt(v):
            if use_ms:
                return f"{fmt_num(v / 1000, 1 if xstep < 1000 else 0)} ms"
            return f"{fmt_int(v)} µs"

        self._grid(cr, x0, y0, x1, y1, xmax, ymax, xstep, ystep, xfmt,
                   lambda v: f"{fmt_num(v, 0 if ystep >= 1 else 1)}%")

        accent = self._accent()
        sx = (x1 - x0) / xmax
        sy = (y1 - y0) / ymax
        cr.set_source_rgba(accent.red, accent.green, accent.blue, 0.85)
        for i, p in enumerate(pct):
            if p <= 0:
                continue
            left = x0 + self.edges[i] * sx
            right = x0 + self.edges[i + 1] * sx
            h = p * sy
            cr.rectangle(left + 0.5, y1 - h, max(right - left - 1, 1), h)
        cr.fill()

        if self.nominal_us:
            fg = self._fg()
            x = x0 + self.nominal_us * sx
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.5)
            cr.set_dash([4, 4])
            cr.move_to(round(x) + 0.5, y0)
            cr.line_to(round(x) + 0.5, y1)
            cr.stroke()
            cr.set_dash([])
