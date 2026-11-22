"""Registro de eventos do mouse, compatível com o CSV do MouseTester.

Formato do arquivo (igual ao original para Windows):
    linha 1: descrição
    linha 2: CPI
    linha 3: xCount,yCount,Time (ms),buttonflags
    demais : dx,dy,tempo_ms,flags   (dy positivo = para cima)
"""

import math
from array import array

import numpy as np

DEFAULT_DESC = "MSensor Tester"
DEFAULT_CPI = 400.0
CSV_HEADER = "xCount,yCount,Time (ms),buttonflags"


class MouseLog:
    def __init__(self):
        self.desc = DEFAULT_DESC
        self.cpi = DEFAULT_CPI
        self.clear()

    # ------------------------------------------------------------- dados
    def clear(self):
        self._dx = array("i")
        self._dy = array("i")
        self._t_us = array("q")     # tempo bruto do kernel (µs); vazio se carregado de CSV
        self._ts_ms = array("d")    # tempo relativo em ms (preenchido por finalize/load)
        self._flags = array("H")

    def add_report(self, report):
        """Adiciona um capture.Report (dy no padrão evdev: positivo = para baixo)."""
        self._dx.append(report.dx)
        self._dy.append(-report.dy)
        self._t_us.append(report.t_us)
        self._flags.append(report.buttons & 0xFFFF)

    def finalize(self):
        """Calcula os tempos relativos (ms) a partir do primeiro evento."""
        if not self._t_us:
            return
        t0 = self._t_us[0]
        self._ts_ms = array("d", ((t - t0) / 1000.0 for t in self._t_us))

    def __len__(self):
        return len(self._dx)

    @property
    def count(self):
        return len(self._dx)

    # ------------------------------------------------------ vetores numpy
    def dx(self):
        return np.array(self._dx, dtype=np.int64)

    def dy(self):
        return np.array(self._dy, dtype=np.int64)

    def ts(self):
        if len(self._ts_ms) != len(self._dx):
            self.finalize()
        return np.array(self._ts_ms, dtype=np.float64)

    def flags(self):
        return np.array(self._flags, dtype=np.int64)

    def motion_ts(self):
        """Tempos (ms) apenas dos relatórios com movimento — base do polling rate."""
        ts = self.ts()
        moving = (self.dx() != 0) | (self.dy() != 0)
        return ts[moving]

    # --------------------------------------------------------- resumo
    def delta_x(self):
        return int(sum(self._dx))

    def delta_y(self):
        return int(sum(self._dy))

    def path(self):
        return float(sum(math.hypot(x, y) for x, y in zip(self._dx, self._dy)))

    def duration_ms(self):
        ts = self._ts_ms if len(self._ts_ms) == len(self._dx) else None
        if ts is None:
            self.finalize()
            ts = self._ts_ms
        return ts[-1] - ts[0] if len(ts) > 1 else 0.0

    def counts_to_cm(self, counts):
        if self.cpi <= 0:
            return float("nan")
        return counts / self.cpi * 2.54

    # -------------------------------------------------------- arquivo
    def save(self, filename):
        ts = self.ts()
        with open(filename, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{self.desc.replace(chr(10), ' ')}\n")
            fh.write(f"{self.cpi:g}\n")
            fh.write(CSV_HEADER + "\n")
            # 3 casas decimais em ms = resolução de 1 µs (a do kernel).
            for x, y, t, f in zip(self._dx, self._dy, ts.tolist(), self._flags):
                fh.write(f"{x},{y},{t:.3f},{f}\n")

    def load(self, filename):
        """Carrega um CSV do MSensor Tester ou do MouseTester (Windows)."""
        with open(filename, encoding="utf-8-sig", errors="replace") as fh:
            lines = fh.read().splitlines()
        if len(lines) < 3:
            raise ValueError("arquivo incompleto")

        desc = lines[0].strip()
        cpi = float(lines[1].strip().replace(",", "."))
        self.clear()
        for line in lines[3:]:
            parts = line.strip().split(",")
            if len(parts) not in (3, 4):
                continue
            try:
                x = int(parts[0])
                y = int(parts[1])
                t = float(parts[2])
                f = int(parts[3]) if len(parts) == 4 else 0
            except ValueError:
                continue
            self._dx.append(x)
            self._dy.append(y)
            self._ts_ms.append(t)
            self._flags.append(f & 0xFFFF)
        self.desc = desc
        self.cpi = cpi
