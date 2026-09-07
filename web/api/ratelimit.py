"""Pembatas laju sederhana per IP, disimpan di memori.

Sengaja tanpa Redis: satu proses, satu VPS. Kalau nanti diskalakan ke beberapa
replika, ganti isi kelas ini — antarmuka `izinkan()` tetap sama.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class BatasLaju:
    def __init__(self, maks: int, jendela_detik: int):
        self.maks = maks
        self.jendela = jendela_detik
        self._log: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def izinkan(self, kunci: str) -> tuple[bool, int]:
        """(boleh, detik_tunggu). Menghapus jejak yang sudah lewat jendela."""
        sekarang = time.time()
        with self._lock:
            jejak = self._log[kunci]
            while jejak and sekarang - jejak[0] > self.jendela:
                jejak.popleft()
            if len(jejak) >= self.maks:
                return False, int(self.jendela - (sekarang - jejak[0])) + 1
            jejak.append(sekarang)
            return True, 0

    def bersihkan(self) -> None:
        """Buang kunci yang jejaknya sudah kosong agar dict tidak tumbuh terus."""
        sekarang = time.time()
        with self._lock:
            for k in [k for k, v in self._log.items() if not v or sekarang - v[-1] > self.jendela]:
                del self._log[k]


class Kuota:
    """Pembatas jumlah pemindaian yang berjalan bersamaan."""

    def __init__(self, maks_global: int, maks_per_ip: int):
        self._sem = threading.BoundedSemaphore(maks_global)
        self._maks_ip = maks_per_ip
        self._per_ip: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def ambil(self, ip: str) -> bool:
        with self._lock:
            if self._per_ip[ip] >= self._maks_ip:
                return False
            self._per_ip[ip] += 1
        if not self._sem.acquire(blocking=False):
            with self._lock:
                self._per_ip[ip] -= 1
            return False
        return True

    def lepas(self, ip: str) -> None:
        with self._lock:
            if self._per_ip[ip] > 0:
                self._per_ip[ip] -= 1
                if self._per_ip[ip] == 0:
                    del self._per_ip[ip]
        try:
            self._sem.release()
        except ValueError:
            pass
