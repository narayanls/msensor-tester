"""Estatísticas de polling rate.

O mouse só envia relatórios quando há movimento, então pausas não podem
entrar na média. A estratégia:

1. A sequência de relatórios é dividida em "trechos ativos" sempre que o
   intervalo entre dois relatórios passa de um limite (gap).
2. A taxa de cada janela/trecho é (n - 1) / duração — contar relatórios por
   tempo é imune ao agrupamento de interrupções do controlador USB (xHCI),
   que às vezes entrega dois relatórios quase juntos e depois uma pausa.
3. A taxa nominal (125, 250 ... 8000 Hz) é a taxa padrão mais próxima do
   percentil 90 das janelas — i.e. o que o mouse entrega quando está
   sendo movido rápido o bastante.
"""

import math
from array import array
from bisect import bisect_left
from dataclasses import dataclass, field

import numpy as np

STANDARD_RATES = (125, 250, 500, 1000, 2000, 4000, 8000)
ROUGH_GAP_US = 20_000
WINDOW_US = 100_000


def nearest_rate(hz):
    if not hz or hz <= 0 or not math.isfinite(hz):
        return None
    return min(STANDARD_RATES, key=lambda r: abs(math.log(hz / r)))


def split_segments(t_us, gap_us):
    """Índices (início, fim) inclusivos dos trechos sem pausas maiores que gap_us."""
    if len(t_us) == 0:
        return []
    breaks = np.nonzero(np.diff(t_us) > gap_us)[0]
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [len(t_us) - 1]))
    return list(zip(starts.tolist(), ends.tolist()))


def windowed_rates(t_us, gap_us, window_us=WINDOW_US):
    """Taxa (Hz) em janelas de ~window_us dentro de cada trecho ativo."""
    rates = []
    for start, end in split_segments(t_us, gap_us):
        seg = t_us[start : end + 1]
        if len(seg) < 3:
            continue
        edges = np.arange(seg[0], seg[-1] + window_us, window_us)
        idx = np.searchsorted(seg, edges)
        for a, b in zip(idx[:-1], idx[1:]):
            n = b - a
            if n < 3:
                continue
            span = seg[b - 1] - seg[a]
            if span < window_us * 0.5:
                continue
            rates.append((n - 1) / span * 1e6)
    return np.array(rates, dtype=np.float64)


@dataclass
class PollingSummary:
    reports: int = 0
    active_s: float = 0.0
    nominal_hz: int | None = None
    average_hz: float | None = None
    peak_hz: float | None = None
    low_hz: float | None = None
    interval_mean_us: float | None = None
    interval_median_us: float | None = None
    interval_min_us: float | None = None
    interval_max_us: float | None = None
    interval_std_us: float | None = None
    interval_p1_us: float | None = None
    interval_p99_us: float | None = None
    within_25: float | None = None     # fração dos intervalos a ±25% do nominal
    pauses: int = 0
    intervals_us: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def valid(self):
        return self.average_hz is not None


def summarize(t_us):
    """Resumo completo a partir dos tempos (µs) dos relatórios com movimento."""
    t_us = np.asarray(t_us, dtype=np.int64)
    summary = PollingSummary(reports=int(len(t_us)))
    if len(t_us) < 3:
        return summary

    rough = windowed_rates(t_us, ROUGH_GAP_US)
    if len(rough):
        reference = float(np.percentile(rough, 90))
    else:
        segs = split_segments(t_us, ROUGH_GAP_US)
        n = sum(e - s for s, e in segs)
        span = sum(int(t_us[e] - t_us[s]) for s, e in segs)
        reference = n / span * 1e6 if span > 0 else 0
    nominal = nearest_rate(reference)
    if nominal is None:
        return summary
    nominal_us = 1e6 / nominal
    gap = max(3 * nominal_us, 2000.0)

    segs = split_segments(t_us, gap)
    n_intervals = sum(e - s for s, e in segs)
    span = sum(int(t_us[e] - t_us[s]) for s, e in segs)
    if n_intervals <= 0 or span <= 0:
        return summary

    windows = windowed_rates(t_us, gap)
    diffs = np.diff(t_us).astype(np.float64)
    valid = diffs[diffs <= gap]

    summary.nominal_hz = nominal
    summary.average_hz = n_intervals / span * 1e6
    summary.active_s = span / 1e6
    summary.pauses = max(len(segs) - 1, 0)
    if len(windows):
        summary.peak_hz = float(windows.max())
        summary.low_hz = float(windows.min())
    if len(valid):
        summary.interval_mean_us = float(valid.mean())
        summary.interval_median_us = float(np.median(valid))
        summary.interval_min_us = float(valid.min())
        summary.interval_max_us = float(valid.max())
        summary.interval_std_us = float(valid.std())
        summary.interval_p1_us = float(np.percentile(valid, 1))
        summary.interval_p99_us = float(np.percentile(valid, 99))
        close = np.abs(valid - nominal_us) <= 0.25 * nominal_us
        summary.within_25 = float(close.mean())
        summary.intervals_us = valid
    return summary


class LivePolling:
    """Acompanha o polling rate em tempo real durante o teste."""

    def __init__(self, window_us=200_000, idle_us=120_000):
        self.window_us = window_us
        self.idle_us = idle_us
        self.reset()

    def reset(self):
        self.t = array("q")
        self.history = []          # [(segundos desde o início, Hz ou None)]
        self.t_start = None
        self.peak = None

    def feed(self, reports):
        for r in reports:
            if r.dx or r.dy:
                self.t.append(r.t_us)
        if self.t_start is None and self.t:
            self.t_start = self.t[0]

    @property
    def started(self):
        return self.t_start is not None

    def elapsed_s(self, now_us):
        if self.t_start is None:
            return 0.0
        return max(0.0, (now_us - self.t_start) / 1e6)

    def current_hz(self, now_us):
        """Taxa na última janela; None se o mouse está parado."""
        t = self.t
        if len(t) < 3 or now_us - t[-1] > self.idle_us:
            return None
        first = bisect_left(t, t[-1] - self.window_us)
        n = len(t) - first
        if n < 3:
            return None
        span = t[-1] - t[first]
        if span <= 0:
            return None
        hz = (n - 1) / span * 1e6
        if span >= self.window_us * 0.5 and (self.peak is None or hz > self.peak):
            self.peak = hz
        return hz

    def sample(self, now_us):
        hz = self.current_hz(now_us)
        if self.t_start is not None:
            self.history.append((self.elapsed_s(now_us), hz))
        return hz

    def recent_intervals(self, max_count=20000):
        t = self.t
        if len(t) < 2:
            return np.zeros(0)
        tail = np.array(t[-(max_count + 1):], dtype=np.int64)
        return np.diff(tail).astype(np.float64)

    def summary(self):
        return summarize(np.array(self.t, dtype=np.int64))


def histogram(intervals_us, nominal_hz, bins=60):
    """Histograma dos intervalos de 0 até 3x o intervalo nominal."""
    if nominal_hz:
        upper = 3e6 / nominal_hz
    elif len(intervals_us):
        upper = float(np.percentile(intervals_us, 99)) * 1.5
    else:
        upper = 3000.0
    counts, edges = np.histogram(np.clip(intervals_us, 0, upper), bins=bins, range=(0, upper))
    return counts, edges
