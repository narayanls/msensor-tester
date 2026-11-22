"""Área de teste que cobre a aba Sensor durante Medir CPI / Coletar / Log.

Sem a trava do cursor, os cliques e arrastes do teste chegariam à área de
trabalho. Esta camada resolve isso sem precisar de exclusividade no mouse:

- ela fica por cima dos botões da aba, então um clique durante o teste não
  aciona nada no app;
- quando o botão é pressionado dentro da janela, o sistema (Wayland ou X11)
  entrega o arraste inteiro ao app até o botão ser solto, mesmo que o cursor
  saia da janela — nada é arrastado ou selecionado na área de trabalho.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class TestPad(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("test-pad")
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_visible(False)
        self._on_button = None

        inner = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        inner.set_vexpand(True)
        inner.set_margin_start(32)
        inner.set_margin_end(32)

        self.icon = Gtk.Image(icon_name="input-mouse-symbolic", pixel_size=64)
        self.icon.add_css_class("dim-label")
        self.title = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.title.add_css_class("title-1")
        self.text = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=52)
        self.live = Gtk.Label(justify=Gtk.Justification.CENTER)
        self.live.add_css_class("title-3")
        self.live.add_css_class("numeric")
        self.hint = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.hint.add_css_class("dim-label")
        self.button = Gtk.Button(halign=Gtk.Align.CENTER)
        self.button.add_css_class("pill")
        self.button.add_css_class("destructive-action")
        self.button.connect("clicked", self._clicked)

        for widget in (self.icon, self.title, self.text, self.live, self.hint, self.button):
            inner.append(widget)
        self.append(inner)

    def _clicked(self, *_args):
        if self._on_button:
            self._on_button()

    def show_test(self, title, text, hint="", button_label=None, on_button=None):
        self.title.set_label(title)
        self.title.remove_css_class("recording")
        self.text.set_label(text)
        self.hint.set_label(hint)
        self.hint.set_visible(bool(hint))
        self.live.set_label("")
        self.live.set_visible(False)
        self._on_button = on_button
        self.button.set_visible(bool(button_label))
        if button_label:
            self.button.set_label(button_label)
        self.set_visible(True)

    def set_title(self, title, recording=False):
        self.title.set_label(title)
        if recording:
            self.title.add_css_class("recording")
        else:
            self.title.remove_css_class("recording")

    def set_live(self, text):
        self.live.set_label(text)
        self.live.set_visible(bool(text))

    def close(self):
        self.set_visible(False)
        self._on_button = None
