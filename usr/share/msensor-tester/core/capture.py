"""Leitura direta do evdev (/dev/input/eventN) em uma thread dedicada.

É o equivalente Linux do Raw Input usado pelo MouseTester no Windows:
- contagens brutas do sensor (REL_X/REL_Y), sem aceleração do ponteiro;
- carimbo de tempo em microssegundos atribuído pelo kernel (CLOCK_MONOTONIC),
  então atrasos do Python/GTK não distorcem as medições;
- cada quadro entre dois SYN_REPORT corresponde a um relatório HID do mouse.

Opcionalmente o dispositivo é "agarrado" (EVIOCGRAB): os eventos deixam de
chegar ao compositor e o cursor fica parado enquanto o teste roda. O grab é
liberado ao fechar o descritor, inclusive se o processo morrer.

Atenção: se OUTRO programa agarrou o dispositivo (input-remapper, keyd,
kanata...), o kernel entrega os eventos só para ele e nós não recebemos nada.
probe_grab() detecta essa situação.
"""

import errno
import fcntl
import os
import select
import struct
import threading
import time
from typing import NamedTuple

from .debuglog import log

# --- Constantes de linux/input-event-codes.h ---------------------------------
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03
EV_MSC = 0x04
SYN_REPORT = 0
SYN_DROPPED = 3
REL_X = 0x00
REL_Y = 0x01
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112
BTN_SIDE = 0x113
BTN_EXTRA = 0x114

# Flags de botão no formato do Raw Input do Windows (RI_MOUSE_*), para manter
# o CSV compatível com o MouseTester original. (pressionado, solto)
BUTTON_FLAGS = {
    BTN_LEFT: (0x0001, 0x0002),
    BTN_RIGHT: (0x0004, 0x0008),
    BTN_MIDDLE: (0x0010, 0x0020),
    BTN_SIDE: (0x0040, 0x0080),
    BTN_EXTRA: (0x0100, 0x0200),
}
LEFT_DOWN = 0x0001
LEFT_UP = 0x0002

# struct input_event { struct timeval time; __u16 type; __u16 code; __s32 value; }
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
READ_EVENTS = 1024
STATS_INTERVAL_S = 1.0


def _IOW(kind, nr, size):
    return (1 << 30) | (size << 16) | (ord(kind) << 8) | nr


EVIOCGRAB = _IOW("E", 0x90, 4)
EVIOCSCLOCKID = _IOW("E", 0xA0, 4)
CLOCK_MONOTONIC = 1


class Report(NamedTuple):
    """Um relatório do mouse. dy segue o evdev: positivo = para baixo."""

    t_us: int
    dx: int
    dy: int
    buttons: int


class CaptureError(Exception):
    pass


def probe_grab(path):
    """Verifica se outro programa tem acesso exclusivo (EVIOCGRAB) ao dispositivo.

    Retorna (estado, errno): "free", "busy" (outro programa agarrou),
    "unsupported" (não é evdev) ou "error". O grab de teste dura microssegundos.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as exc:
        return "error", exc.errno
    try:
        fcntl.ioctl(fd, EVIOCGRAB, 1)
    except OSError as exc:
        state = "busy" if exc.errno == errno.EBUSY else (
            "unsupported" if exc.errno in (errno.ENOTTY, errno.EINVAL) else "error"
        )
        return state, exc.errno
    else:
        try:
            fcntl.ioctl(fd, EVIOCGRAB, 0)
        except OSError:
            pass
        return "free", None
    finally:
        os.close(fd)


class Capture:
    """Lê um dispositivo evdev em segundo plano e acumula Reports."""

    def __init__(self, path):
        self.path = path
        self.fd = None
        self.grabbed = False
        self.dropped = 0          # quantas vezes o kernel avisou SYN_DROPPED
        self.error = None         # texto do erro se a thread morrer (ex.: mouse desconectado)
        self.monotonic = False    # True se os tempos estão em CLOCK_MONOTONIC
        self.grab_errno = None    # errno da última tentativa de grab que falhou
        # Contadores (lidos pela UI/diagnóstico; escritos só pela thread)
        self.bytes_read = 0
        self.raw_events = 0       # todos os input_event lidos (qualquer tipo)
        self.reports = 0          # quadros entregues (movimento ou botão)
        self.rel_events = 0
        self.key_events = 0
        self.other_events = 0
        self._buffer = []
        self._lock = threading.Lock()
        self._thread = None
        self._wake_r = None
        self._wake_w = None

    # ------------------------------------------------------------------ ciclo
    def start(self):
        log.debug("capture: abrindo %s", self.path)
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        except PermissionError as exc:
            log.warning("capture: sem permissão para abrir %s: %s", self.path, exc)
            raise CaptureError("permission") from exc
        except OSError as exc:
            log.warning("capture: falha ao abrir %s: %s", self.path, exc)
            raise CaptureError(str(exc)) from exc

        try:
            fcntl.ioctl(self.fd, EVIOCSCLOCKID, struct.pack("i", CLOCK_MONOTONIC))
            self.monotonic = True
        except OSError as exc:
            log.debug("capture: EVIOCSCLOCKID falhou (%s); usando relógio padrão", exc)

        self._wake_r, self._wake_w = os.pipe()
        self._thread = threading.Thread(target=self._run, name="evdev-reader", daemon=True)
        self._thread.start()
        log.debug("capture: lendo %s (fd=%s, relógio %s)", self.path, self.fd,
                  "MONOTONIC" if self.monotonic else "REALTIME")

    def stop(self):
        if self._thread is not None:
            try:
                os.write(self._wake_w, b"x")
            except OSError:
                pass
            self._thread.join(timeout=2)
            self._thread = None
        self.set_grab(False)
        for fd in (self.fd, self._wake_r, self._wake_w):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        if self.fd is not None:
            log.debug(
                "capture: fechado %s — %d bytes, %d eventos brutos (rel=%d key=%d outros=%d), "
                "%d relatórios, %d SYN_DROPPED, erro=%s",
                self.path, self.bytes_read, self.raw_events, self.rel_events, self.key_events,
                self.other_events, self.reports, self.dropped, self.error,
            )
        self.fd = self._wake_r = self._wake_w = None

    @property
    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def set_grab(self, grab):
        """Trava (True) ou libera (False) o dispositivo. Retorna True se conseguiu."""
        if self.fd is None:
            return False
        if grab == self.grabbed:
            return True
        try:
            fcntl.ioctl(self.fd, EVIOCGRAB, 1 if grab else 0)
        except OSError as exc:
            self.grab_errno = exc.errno
            log.debug("capture: EVIOCGRAB(%d) falhou em %s: [%s] %s", int(grab), self.path,
                      errno.errorcode.get(exc.errno, exc.errno), exc.strerror)
            if not grab:
                self.grabbed = False
            return False
        self.grabbed = grab
        log.debug("capture: EVIOCGRAB(%d) ok em %s", int(grab), self.path)
        return True

    def drain(self):
        """Devolve (e remove) os relatórios acumulados desde a última chamada."""
        with self._lock:
            out = self._buffer
            self._buffer = []
        return out

    def discard(self):
        self.drain()

    # ---------------------------------------------------------------- thread
    def _run(self):
        fd = self.fd
        wake = self._wake_r
        unpack = struct.iter_unpack
        chunk = EVENT_SIZE * READ_EVENTS
        debug = log.isEnabledFor(10)  # logging.DEBUG

        dx = dy = buttons = 0
        dropping = False
        leftover = b""
        first_logged = False
        next_stats = time.monotonic() + STATS_INTERVAL_S
        last_counts = (0, 0)

        while True:
            try:
                ready, _, _ = select.select([fd, wake], [], [], 0.5)
            except OSError as exc:
                self.error = str(exc)
                log.error("capture: select falhou: %s", exc)
                return
            if wake in ready:
                return

            if debug and time.monotonic() >= next_stats:
                next_stats = time.monotonic() + STATS_INTERVAL_S
                ev = self.raw_events - last_counts[0]
                rp = self.reports - last_counts[1]
                last_counts = (self.raw_events, self.reports)
                log.debug("capture: %s — último segundo: %d eventos brutos, %d relatórios "
                          "(total %d / %d)", self.path, ev, rp, self.raw_events, self.reports)

            if fd not in ready:
                continue
            try:
                data = os.read(fd, chunk)
            except BlockingIOError:
                continue
            except OSError as exc:
                self.error = "disconnected" if exc.errno == errno.ENODEV else str(exc)
                log.warning("capture: leitura falhou em %s: %s", self.path, exc)
                return
            if not data:
                self.error = "disconnected"
                log.warning("capture: fim de arquivo em %s", self.path)
                return
            self.bytes_read += len(data)

            # O evdev sempre entrega eventos inteiros, mas guardamos a sobra por
            # segurança (e para funcionar com FIFOs nos testes).
            if leftover:
                data = leftover + data
            usable = len(data) - (len(data) % EVENT_SIZE)
            leftover = data[usable:]
            batch = []
            for sec, usec, etype, code, value in unpack(EVENT_FORMAT, data[:usable]):
                self.raw_events += 1
                if etype == EV_REL:
                    self.rel_events += 1
                    if code == REL_X:
                        dx += value
                    elif code == REL_Y:
                        dy += value
                elif etype == EV_KEY:
                    self.key_events += 1
                    flags = BUTTON_FLAGS.get(code)
                    if flags is not None and value in (0, 1):
                        buttons |= flags[0] if value == 1 else flags[1]
                elif etype == EV_SYN:
                    if code == SYN_REPORT:
                        if dropping:
                            dropping = False
                        elif dx or dy or buttons:
                            batch.append(Report(sec * 1_000_000 + usec, dx, dy, buttons))
                        dx = dy = buttons = 0
                    elif code == SYN_DROPPED:
                        # O buffer do kernel transbordou: descarta até o próximo SYN_REPORT.
                        self.dropped += 1
                        dropping = True
                        dx = dy = buttons = 0
                        log.warning("capture: SYN_DROPPED em %s (total %d)", self.path, self.dropped)
                else:
                    self.other_events += 1
            if batch:
                self.reports += len(batch)
                if not first_logged:
                    first_logged = True
                    r = batch[0]
                    log.debug("capture: primeiro relatório de %s: dx=%d dy=%d botões=%#x t=%d µs",
                              self.path, r.dx, r.dy, r.buttons, r.t_us)
                with self._lock:
                    self._buffer.extend(batch)


class DeviceDetector:
    """Escuta vários mouses (sem grab) e identifica qual deles foi movido."""

    def __init__(self, paths, threshold=40):
        self.paths = list(paths)
        self.threshold = threshold
        self.result = None
        self._captures = []

    def start(self):
        for path in self.paths:
            cap = Capture(path)
            try:
                cap.start()
            except CaptureError:
                continue
            self._captures.append(cap)
        log.debug("detector: escutando %d dispositivo(s): %s", len(self._captures),
                  ", ".join(c.path for c in self._captures))
        return bool(self._captures)

    def poll(self):
        """Chamar periodicamente; devolve o caminho do mouse movido ou None."""
        if self.result:
            return self.result
        for cap in self._captures:
            reports = cap.drain()
            total = sum(abs(r.dx) + abs(r.dy) for r in reports)
            cap.detector_total = getattr(cap, "detector_total", 0) + total
            if cap.detector_total >= self.threshold:
                self.result = cap.path
                log.debug("detector: movimento em %s", cap.path)
                break
        return self.result

    def stop(self):
        for cap in self._captures:
            cap.stop()
        self._captures = []
