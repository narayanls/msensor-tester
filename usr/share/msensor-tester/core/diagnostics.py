"""Relatório de diagnóstico: por que o app não recebe os eventos do mouse?

Usado por `msensor-tester --diagnose` (terminal) e por Menu → Diagnóstico.
Não depende de GTK. Tudo aqui funciona sem root; o que exige root é avisado.
"""

import glob
import grp
import os
import platform
import pwd
import re
import stat
import sys
import time

import numpy as np

from . import APP_NAME, APP_VERSION
from .capture import Capture, CaptureError, probe_grab
from .devices import (
    BTN_LEFT, REL_X, REL_Y, _has_bit, _parse_bitmask, _read, list_mice, udev_rule_installed,
    virtual_counterparts,
)
from .i18n import _
from .stats import summarize

EVDEV_MINOR_BASE = 64
REL_WHEEL = 0x08
KEY_A = 30

# Programas conhecidos por agarrar (EVIOCGRAB) mouses/teclados e reemitir os
# eventos por um dispositivo virtual.
KNOWN_GRABBERS = {
    "input-remapper": "input-remapper",
    "input-remapper-service": "input-remapper",
    "input-remapper-reader-service": "input-remapper",
    "keyd": "keyd",
    "kanata": "kanata",
    "logid": "logiops (logid)",
    "udevmon": "interception-tools (udevmon)",
    "intercept": "interception-tools",
    "xremap": "xremap",
    "evsieve": "evsieve",
    "kmonad": "kmonad",
    "otd-daemon": "OpenTabletDriver",
    "OpenTabletDriver.Daemon": "OpenTabletDriver",
    "makima": "makima",
    "mouseless": "mouseless",
    "warpd": "warpd",
    "sunshine": "Sunshine",
    "gamescope": "gamescope",
    "ydotoold": "ydotool (ydotoold)",
    "hawck-inputd": "hawck",
    "actkbd": "actkbd",
}


# ============================================================================ coleta
def _os_release():
    text = _read("/etc/os-release")
    match = re.search(r'^PRETTY_NAME="?([^"\n]*)"?', text, re.M)
    return match.group(1) if match else "?"


def _udev_props(event_number):
    """Propriedades e tags do banco do udev (/run/udev/data/c13:MINOR)."""
    path = f"/run/udev/data/c13:{EVDEV_MINOR_BASE + event_number}"
    props, tags = {}, set()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("E:") and "=" in line:
                    key, value = line[2:].split("=", 1)
                    props[key] = value
                elif line[:2] in ("G:", "Q:"):
                    tags.add(line[2:])
    except OSError:
        return None, set()
    return props, tags


def input_devices():
    """Todos os nós /dev/input/eventN com informações para o relatório."""
    out = []
    for sys_dir in sorted(glob.glob("/sys/class/input/event*"),
                          key=lambda p: int(re.search(r"(\d+)$", p).group(1))):
        n = int(re.search(r"(\d+)$", sys_dir).group(1))
        dev = os.path.join(sys_dir, "device")
        rel = _parse_bitmask(_read(os.path.join(dev, "capabilities/rel"), "0"))
        key = _parse_bitmask(_read(os.path.join(dev, "capabilities/key"), "0"))
        absm = _parse_bitmask(_read(os.path.join(dev, "capabilities/abs"), "0"))
        path = f"/dev/input/event{n}"
        try:
            st = os.stat(path)
            mode = stat.filemode(st.st_mode)
            owner = pwd.getpwuid(st.st_uid).pw_name
            group = grp.getgrgid(st.st_gid).gr_name
        except (OSError, KeyError):
            mode = owner = group = "?"
        props, tags = _udev_props(n)
        out.append({
            "n": n,
            "path": path,
            "name": _read(os.path.join(dev, "name"), "?"),
            "phys": _read(os.path.join(dev, "phys")),
            "bus": _read(os.path.join(dev, "id/bustype"), "0"),
            "vid": _read(os.path.join(dev, "id/vendor"), "0"),
            "pid": _read(os.path.join(dev, "id/product"), "0"),
            "rel_xy": _has_bit(rel, REL_X) and _has_bit(rel, REL_Y),
            "wheel": _has_bit(rel, REL_WHEEL),
            "btn_left": _has_bit(key, BTN_LEFT),
            "keys": bin(key).count("1"),
            "letters": _has_bit(key, KEY_A),
            "abs": absm != 0,
            "readable": os.access(path, os.R_OK),
            "mode": mode,
            "owner": owner,
            "group": group,
            "udev": props,
            "tags": tags,
        })
    return out


def running_grabbers():
    """Processos conhecidos por agarrar dispositivos (lê /proc/*/comm, sem root)."""
    found = []
    for comm_path in glob.glob("/proc/[0-9]*/comm"):
        comm = _read(comm_path)
        pid = comm_path.split("/")[2]
        cmdline = _read(f"/proc/{pid}/cmdline").replace("\x00", " ").strip()
        names = {comm}
        if cmdline:
            first = os.path.basename(cmdline.split(" ")[0])
            names.add(first)
            # scripts python: "python3 /usr/bin/input-remapper-service"
            for part in cmdline.split(" ")[:3]:
                names.add(os.path.basename(part))
        for name in names:
            label = KNOWN_GRABBERS.get(name)
            if label:
                found.append((int(pid), label, cmdline[:120] or comm))
                break
    return sorted(found)


UINPUT_PATHS = ("/dev/uinput", "/dev/input/uinput")


def scan_fds(watch=()):
    """{pid: set(destinos)} dos descritores de input/uinput visíveis + nº de processos ocultos.

    `watch` acrescenta caminhos específicos a observar (ex.: os mouses listados).
    """
    watch = set(watch)
    result = {}
    hidden = 0
    for fd_dir in glob.glob("/proc/[0-9]*/fd"):
        pid = int(fd_dir.split("/")[2])
        try:
            entries = os.listdir(fd_dir)
        except OSError:
            hidden += 1
            continue
        targets = set()
        for entry in entries:
            try:
                target = os.readlink(os.path.join(fd_dir, entry))
            except OSError:
                continue
            if target.startswith("/dev/input/event") or target in UINPUT_PATHS or target in watch:
                targets.add(target)
        if targets:
            result[pid] = targets
    return result, hidden


def process_info(pid):
    comm = _read(f"/proc/{pid}/comm") or "?"
    cmdline = _read(f"/proc/{pid}/cmdline").replace("\x00", " ").strip()
    return comm, cmdline


def open_input_fds(fds=None):
    """{"/dev/input/eventN": {"comm(pid)", ...}} para processos visíveis."""
    if fds is None:
        fds, hidden = scan_fds()
    else:
        hidden = 0
    result = {}
    for pid, targets in fds.items():
        comm, _cmd = process_info(pid)
        for target in targets:
            if target not in UINPUT_PATHS:
                result.setdefault(target, set()).add(f"{comm}({pid})")
    return result, hidden


def likely_grabbers(path, fds=None):
    """Processos com `path` aberto que também criam dispositivos virtuais (uinput).

    É o padrão de qualquer remapeador: agarra o mouse real e reemite os
    eventos por um mouse virtual. O compositor também abre o mouse, mas não
    usa uinput, então fica de fora.
    """
    if fds is None:
        fds, _hidden = scan_fds(watch=[path])
    found = []
    for pid, targets in sorted(fds.items()):
        if path in targets and targets & set(UINPUT_PATHS):
            comm, cmdline = process_info(pid)
            found.append({"pid": pid, "comm": comm, "cmdline": cmdline})
    return found


def listen(paths, seconds, progress=None):
    """Escuta os dispositivos ao mesmo tempo e devolve estatísticas por caminho."""
    caps = {}
    errors = {}
    for path in paths:
        cap = Capture(path)
        try:
            cap.start()
        except CaptureError as exc:
            errors[path] = str(exc)
            continue
        caps[path] = cap
    times = {p: [] for p in caps}
    clicks = {p: 0 for p in caps}
    deadline = time.monotonic() + seconds
    last_tick = None
    while True:
        now = time.monotonic()
        remaining = deadline - now
        if progress:
            tick = max(int(remaining + 0.999), 0)
            if tick != last_tick:
                last_tick = tick
                progress(tick)
        for path, cap in caps.items():
            for r in cap.drain():
                if r.dx or r.dy:
                    times[path].append(r.t_us)
                if r.buttons & 0x0155:   # qualquer botão pressionado
                    clicks[path] += 1
        if remaining <= 0:
            break
        time.sleep(0.05)
    results = {}
    for path, cap in caps.items():
        summary = summarize(np.array(times[path], dtype=np.int64))
        results[path] = {
            "raw": cap.raw_events,
            "rel": cap.rel_events,
            "key": cap.key_events,
            "motion": len(times[path]),
            "clicks": clicks[path],
            "dropped": cap.dropped,
            "error": cap.error,
            "rate": summary.average_hz,
            "nominal": summary.nominal_hz,
        }
        cap.stop()
    for path, err in errors.items():
        results[path] = {"open_error": err}
    return results


# ========================================================================= relatório
def build_report(listen_seconds=5, progress=None, selected_path=None):
    lines = []
    add = lines.append

    add(f"=== {APP_NAME} {APP_VERSION} — " + _("diagnostic report") + " ===")
    add(time.strftime("%Y-%m-%d %H:%M:%S"))
    add("")

    # ------------------------------------------------------------------ sistema
    add("## " + _("System"))
    user = pwd.getpwuid(os.getuid()).pw_name
    groups = sorted({grp.getgrgid(g).gr_name for g in os.getgroups() if _safe_group(g)})
    add(f"  {_('Distribution')}: {_os_release()}")
    add(f"  Kernel: {platform.release()}")
    add(f"  {_('Session')}: XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE', '?')} "
        f"XDG_CURRENT_DESKTOP={os.environ.get('XDG_CURRENT_DESKTOP', '?')}")
    add(f"  Python: {sys.version.split()[0]}")
    add(f"  {_('User')}: {user} (uid {os.getuid()}) — {_('groups')}: {', '.join(groups) or '-'}")
    add(f"  {_('udev rule installed')}: {_('yes') if udev_rule_installed() else _('NO')}")
    add("")

    # -------------------------------------------------------------- dispositivos
    devices = input_devices()
    mice = list_mice()
    mouse_paths = {m.path for m in mice}
    add("## " + _("Input devices") + f" ({len(devices)})")
    for d in devices:
        kind = []
        if d["path"] in mouse_paths:
            kind.append(_("MOUSE"))
        if d["letters"]:
            kind.append(_("keyboard"))
        if d["abs"] and not d["rel_xy"]:
            kind.append(_("absolute (touchpad/tablet)"))
        kind = ", ".join(kind) or _("other")
        add(f"  event{d['n']:<3} {d['name']}")
        add(f"           {_('type')}: {kind} | bus {d['bus']} {d['vid']}:{d['pid']} | {d['phys'] or '-'}")
        caps = []
        if d["rel_xy"]:
            caps.append("REL_X/Y")
        if d["wheel"]:
            caps.append("WHEEL")
        if d["btn_left"]:
            caps.append("BTN_LEFT")
        caps.append(_("{n} keys/buttons").format(n=d["keys"]))
        add(f"           {_('capabilities')}: {' '.join(caps)}")
        perm = _("readable") if d["readable"] else _("NOT readable")
        add(f"           {_('permission')}: {d['mode']} {d['owner']}:{d['group']} → {perm}")
        if d["path"] in mouse_paths:
            if d["udev"] is None:
                add(f"           udev: {_('database not available')}")
            else:
                idm = d["udev"].get("ID_INPUT_MOUSE", "-")
                idk = d["udev"].get("ID_INPUT_KEYBOARD", "-")
                uacc = "uaccess" in d["tags"]
                add(f"           udev: ID_INPUT_MOUSE={idm} ID_INPUT_KEYBOARD={idk} "
                    f"tag uaccess={_('yes') if uacc else _('no')}")
    add("")

    # ------------------------------------------------------------ exclusividade
    add("## " + _("Exclusive access (EVIOCGRAB) by other programs"))
    fds, hidden = scan_fds(watch=[m.path for m in mice])
    busy = []
    busy_culprits = {}
    for m in mice:
        if not m.readable:
            add(f"  {m.path} {m.name}: {_('not tested (no permission)')}")
            continue
        state, err = probe_grab(m.path)
        text = {
            "free": _("free"),
            "busy": _("BUSY — another program has exclusive access; events do not reach this app"),
            "unsupported": _("not supported"),
        }.get(state, f"{_('error')} {os.strerror(err) if err else ''}")
        add(f"  {m.path} {m.name}: {text}")
        if state == "busy":
            busy.append(m)
            culprits = likely_grabbers(m.path, fds)
            busy_culprits[m.path] = culprits
            for c in culprits:
                add(f"           {_('likely responsible')}: {c['comm']} (pid {c['pid']}) — {c['cmdline'][:160]}")
            for v in virtual_counterparts(m, mice):
                add(f"           {_('virtual device that receives the events')}: {v.path} {v.name}")
    if not mice:
        add("  " + _("no mouse found"))
    add("")

    grabbers = running_grabbers()
    add("## " + _("Known input-grabbing programs running"))
    if grabbers:
        for pid, label, cmd in grabbers:
            add(f"  {label}: pid {pid} — {cmd}")
    else:
        add("  " + _("none found"))
    open_map, _hidden = open_input_fds(fds)
    uinput_users = sorted(pid for pid, t in fds.items() if t & set(UINPUT_PATHS))
    add("## " + _("Processes with input devices open (visible to this user)"))
    if open_map:
        def event_number(t):
            match = re.search(r"(\d+)$", t)
            return int(match.group(1)) if match else 0

        for target in sorted(open_map, key=event_number):
            add(f"  {target}: {', '.join(sorted(open_map[target]))}")
    else:
        add("  " + _("none visible"))
    if hidden and os.getuid() != 0:
        add("  " + _("({n} processes of other users/root are not visible; run with sudo to see them)").format(n=hidden))
    add("## " + _("Processes that create virtual input devices (uinput)"))
    if uinput_users:
        for pid in uinput_users:
            comm, cmdline = process_info(pid)
            add(f"  {comm} (pid {pid}) — {cmdline[:160]}")
    else:
        add("  " + _("none visible"))
    add("")

    # ------------------------------------------------------------------- escuta
    listen_paths = [m.path for m in mice if m.readable]
    results = {}
    add("## " + _("Listening test ({s} s) — move the mouse and click").format(s=listen_seconds))
    if listen_paths and listen_seconds > 0:
        results = listen(listen_paths, listen_seconds, progress)
        names = {m.path: m.name for m in mice}
        for path in listen_paths:
            r = results.get(path, {})
            mark = "  <== " + _("selected") if path == selected_path else ""
            if "open_error" in r:
                add(f"  {path} {names[path]}: {_('could not open')}: {r['open_error']}{mark}")
                continue
            rate = f"{r['rate']:.0f} Hz ({_('nominal')} {r['nominal']})" if r["rate"] else "-"
            add(f"  {path} {names[path]}{mark}")
            add(f"           {_('raw events')}: {r['raw']} (REL {r['rel']}, KEY {r['key']}) | "
                f"{_('motion reports')}: {r['motion']} | {_('clicks')}: {r['clicks']} | "
                f"{_('rate')}: {rate} | SYN_DROPPED: {r['dropped']}"
                + (f" | {_('error')}: {r['error']}" if r["error"] else ""))
    else:
        add("  " + _("nothing to listen to (no readable mouse)"))
    add("")

    # --------------------------------------------------------------- conclusões
    add("## " + _("Conclusions"))
    hints = []
    if not mice:
        hints.append(_("No mouse (REL_X + REL_Y + BTN_LEFT) was found in /sys/class/input."))
    unreadable = [m for m in mice if not m.readable]
    if unreadable:
        if not udev_rule_installed():
            hints.append(_("Some mice are not readable and the udev rule is not installed."))
        else:
            hints.append(_("Some mice are not readable even with the udev rule installed: "
                           "reconnect the mouse or run 'sudo udevadm trigger --subsystem-match=input "
                           "--action=change'. The rule only works for the user logged in locally."))
    if busy:
        hint = _("These mice are grabbed by another program: {names}. While that happens, the "
                 "kernel delivers the events only to that program.").format(
                     names=", ".join(m.name for m in busy))
        culprits = [c for m in busy for c in busy_culprits.get(m.path, [])]
        if culprits:
            who = "; ".join(f"{c['comm']} (pid {c['pid']}): {c['cmdline'][:120]}" for c in culprits)
            hint += " " + _("Likely culprit: {who}.").format(who=who)
            hint += " " + _("To stop it: kill {pids}").format(pids=" ".join(str(c["pid"]) for c in culprits)) + "."
        elif grabbers:
            hint += " " + _("Likely culprit: {who}.").format(who=", ".join(sorted({g[1] for g in grabbers})))
        hint += " " + _("Close it during the test, or select the virtual device it creates "
                        "(the polling rate will then be that of the virtual device).")
        hints.append(hint)
    moving = [p for p, r in results.items() if r.get("motion")]
    silent = [p for p, r in results.items() if "open_error" not in r and not r.get("raw")]
    if results and not moving:
        hints.append(_("No movement was received from any mouse during the listening test. "
                       "If you moved the mouse, it is probably grabbed by another program."))
    elif selected_path and selected_path in silent and moving:
        hints.append(_("The selected device received nothing, but {other} did: select it in the "
                       "list (or use the Detect button).").format(other=", ".join(moving)))
    if not hints:
        hints.append(_("No problem detected."))
    for h in hints:
        add("  - " + h)
    return "\n".join(lines)


def _safe_group(gid):
    try:
        grp.getgrgid(gid)
        return True
    except KeyError:
        return False


def run_cli(listen_seconds=5):
    """Imprime o relatório no terminal (msensor-tester --diagnose)."""
    print(_("Collecting information… during the listening test, move the mouse and click."),
          file=sys.stderr)

    def progress(remaining):
        print(f"\r  {_('Move the mouse now')}… {remaining:2d} s ", end="", file=sys.stderr, flush=True)

    report = build_report(listen_seconds, progress)
    print("\r" + " " * 40 + "\r", end="", file=sys.stderr)
    print(report)
    return 0
