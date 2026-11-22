"""Diálogos: permissão, preferências e sobre."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from core import APP_ID, APP_NAME, APP_VERSION, APP_WEBSITE, UDEV_RULE_NAME  # noqa: E402
from core.devices import bundled_udev_rule, udev_rule_installed  # noqa: E402
from core.i18n import _  # noqa: E402

# Adw.AlertDialog / PreferencesDialog / AboutDialog existem a partir da libadwaita 1.5.
_HAS_ALERT = hasattr(Adw, "AlertDialog")
_HAS_PREFS_DIALOG = hasattr(Adw, "PreferencesDialog")
_HAS_ABOUT_DIALOG = hasattr(Adw, "AboutDialog")

RULE_TEXT = (
    'SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_MOUSE}=="1", '
    'ENV{ID_INPUT_KEYBOARD}!="1", TAG+="uaccess"'
)
RELOAD_CMDS = (
    "sudo udevadm control --reload\n"
    "sudo udevadm trigger --subsystem-match=input --action=change"
)


def _alert(parent, heading, body):
    if _HAS_ALERT:
        return Adw.AlertDialog(heading=heading, body=body)
    return Adw.MessageDialog(transient_for=parent, modal=True, heading=heading, body=body)


def _present(dialog, parent):
    if _HAS_ALERT and isinstance(dialog, Adw.Dialog):
        dialog.present(parent)
    else:
        dialog.present()


def _code_block(text, after=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    label = Gtk.Label(label=text, selectable=True, wrap=True, xalign=0)
    label.add_css_class("monospace")
    label.set_focusable(False)   # evita abrir com todo o texto selecionado
    label.set_margin_top(10)
    label.set_margin_bottom(10)
    label.set_margin_start(12)
    label.set_margin_end(12)
    box.append(Gtk.Frame(child=label))
    if after:
        note = Gtk.Label(label=after, wrap=True, justify=Gtk.Justification.CENTER)
        box.append(note)
    return box


def show_permission_dialog(parent):
    body = _(
        "Reading the raw sensor data requires access to /dev/input. The package "
        "installs a udev rule that grants this access only to mice, and only to "
        "the user logged in at the computer (keyboards are not included)."
    )
    if udev_rule_installed():
        body += "\n\n" + _(
            "The rule is installed but has not been applied to the connected mice "
            "yet. Unplug and reconnect the mouse, or run:"
        )
        commands = RELOAD_CMDS
    else:
        body += "\n\n" + _("The rule was not found. Install it with:")
        source = bundled_udev_rule()
        if source:
            install = f"sudo install -Dm644 '{source}' /etc/udev/rules.d/{UDEV_RULE_NAME}"
        else:
            install = f"echo '{RULE_TEXT}' | sudo tee /etc/udev/rules.d/{UDEV_RULE_NAME}"
        commands = install + "\n" + RELOAD_CMDS
    dialog = _alert(parent, _("Permission needed"), body)
    dialog.set_extra_child(
        _code_block(commands, _("Then press the refresh button next to the mouse list."))
    )
    dialog.add_response("ok", _("OK"))
    dialog.set_default_response("ok")
    _present(dialog, parent)


def show_busy_dialog(parent, device, devices=()):
    from core.devices import virtual_counterparts
    from core.diagnostics import likely_grabbers, running_grabbers

    body = _(
        "The kernel is delivering the events of “{name}” only to another program "
        "(exclusive access), so MSensor Tester receives nothing."
    ).format(name=device.name)
    culprits = likely_grabbers(device.path)
    if culprits:
        lines = "\n".join(
            f"• {c['comm']} (pid {c['pid']}): {c['cmdline'][:100]}" for c in culprits
        )
        body += "\n\n" + _("Process holding the mouse:") + "\n" + lines
        body += "\n\n" + _(
            "To measure the real mouse, close that program (for example: kill {pids}) "
            "and press the refresh button."
        ).format(pids=" ".join(str(c["pid"]) for c in culprits))
    else:
        grabbers = sorted({label for _pid, label, _cmd in running_grabbers()})
        if grabbers:
            body += "\n\n" + _("Running program that usually does this: {who}.").format(who=", ".join(grabbers))
        body += "\n\n" + _(
            "To measure the real mouse, close that program and press the refresh button."
        )

    virtual = virtual_counterparts(device, list(devices))
    if virtual:
        body += "\n\n" + _(
            "You can also test the virtual device “{name}”, which receives the events. "
            "The CPI and tracking stay valid, but the polling rate will be the rate at "
            "which that program forwards the events, not the mouse's."
        ).format(name=virtual[0].name)

    dialog = _alert(parent, _("Mouse in exclusive use"), body)
    dialog.add_response("diag", _("Diagnostics"))
    if virtual:
        dialog.add_response("virtual", _("Use virtual device"))
        dialog.set_response_appearance("virtual", Adw.ResponseAppearance.SUGGESTED)
    dialog.add_response("ok", _("OK"))
    dialog.set_default_response("virtual" if virtual else "ok")

    def on_response(_d, response):
        if response == "diag":
            parent.get_application().activate_action("diagnostics", None)
        elif response == "virtual" and virtual:
            parent.select_device(virtual[0].path)
            parent.toast(_("Virtual device selected. Start the test again."))

    dialog.connect("response", on_response)
    _present(dialog, parent)


def show_preferences(win):
    settings = win.settings

    if _HAS_PREFS_DIALOG:
        dialog = Adw.PreferencesDialog()
    else:
        dialog = Adw.PreferencesWindow(transient_for=win, modal=True)
    dialog.set_title(_("Preferences"))

    page = Adw.PreferencesPage()

    tests = Adw.PreferencesGroup(title=_("Tests"))
    lock = Adw.SwitchRow(
        title=_("Lock the cursor during tests"),
        subtitle=_(
            "Optional. Fails if another program has exclusive access to the mouse "
            "(input-remapper, keyd, kanata…). The measurement is the same with or without it."
        ),
    )
    lock.set_active(settings.get("grab_device"))
    lock.connect("notify::active", lambda row, _p: settings.set("grab_device", row.get_active()))
    tests.add(lock)

    distance = Adw.SpinRow.new_with_range(1, 100, 0.5)
    distance.set_title(_("CPI measurement distance (cm)"))
    distance.set_subtitle(_("How far you move the mouse in “Measure CPI”"))
    distance.set_digits(1)
    distance.set_value(settings.get("measure_distance_cm"))
    distance.connect(
        "notify::value", lambda row, _p: settings.set("measure_distance_cm", row.get_value())
    )
    tests.add(distance)
    page.add(tests)

    lang_group = Adw.PreferencesGroup(title=_("Language"))
    codes = ["auto", "pt_BR", "en"]
    model = Gtk.StringList.new([_("Automatic (system)"), "Português (Brasil)", "English"])
    lang = Adw.ComboRow(title=_("Interface language"), model=model)
    lang.set_subtitle(_("Takes effect after restarting the app"))
    current = settings.get("language")
    lang.set_selected(codes.index(current) if current in codes else 0)
    lang.connect("notify::selected", lambda row, _p: settings.set("language", codes[row.get_selected()]))
    lang_group.add(lang)
    page.add(lang_group)

    dialog.add(page)
    if _HAS_PREFS_DIALOG:
        dialog.present(win)
    else:
        dialog.present()


def show_about(win):
    kwargs = dict(
        application_name=APP_NAME,
        application_icon=APP_ID,
        version=APP_VERSION,
        developer_name="narayanls",
        license_type=Gtk.License.GPL_3_0,
        website=APP_WEBSITE,
        issue_url=APP_WEBSITE + "/issues",
        comments=_(
            "Mouse sensor tracking and polling rate tester for Linux. Reads the raw "
            "sensor data directly from evdev, with microsecond kernel timestamps."
        ),
    )
    if _HAS_ABOUT_DIALOG:
        about = Adw.AboutDialog(**kwargs)
    else:
        about = Adw.AboutWindow(transient_for=win, modal=True, **kwargs)
    about.add_credit_section(_("Inspired by"), ["MouseTester (microe1) https://github.com/microe1/MouseTester"])
    if _HAS_ABOUT_DIALOG:
        about.present(win)
    else:
        about.present()
