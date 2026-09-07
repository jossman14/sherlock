"""Menjalankan Sherlock sebagai aliran hasil, bukan sekali jadi.

Sherlock aslinya sinkron dan baru mengembalikan apa pun setelah seluruh situs
selesai diperiksa — untuk 400+ situs itu puluhan detik dengan layar kosong.
QueryNotify adalah kait resmi yang dipanggil per situs, jadi di sinilah tiap
hasil dititipkan ke antrean supaya bisa dikirim ke browser saat itu juga.
"""

from __future__ import annotations

import json
import pathlib
import queue
import threading
import time
from dataclasses import dataclass, asdict
from typing import Iterator

from sherlock_project.notify import QueryNotify
from sherlock_project.result import QueryStatus
from sherlock_project.sherlock import sherlock
from sherlock_project.sites import SitesInformation


@dataclass
class Hasil:
    site: str
    url_user: str | None
    url_main: str | None
    status: str          # claimed | available | unknown | illegal | waf
    query_time: float | None
    context: str | None


class _Antrean(QueryNotify):
    """QueryNotify yang menaruh tiap hasil ke queue alih-alih mencetaknya."""

    def __init__(self, q: queue.Queue, sites: dict[str, dict]):
        super().__init__()
        self._q = q
        self._sites = sites

    def update(self, result):  # dipanggil sherlock() sekali per situs
        info = self._sites.get(result.site_name, {})
        status = str(result.status).lower()
        context = result.context

        # Situs yang terbukti tidak bisa diperiksa dengan jujur dari server ini dilaporkan
        # sebagai "gagal diperiksa", bukan sebagai jawaban. Diamnya negatif palsu jauh lebih
        # menyesatkan bagi penelusur daripada kegagalan yang terang-terangan.
        alasan = TIDAK_ANDAL.get(result.site_name)
        if alasan:
            status = "unknown"
            context = alasan

        self._q.put(
            Hasil(
                site=result.site_name,
                url_user=result.site_url_user,
                url_main=info.get("urlMain"),
                status=status,
                query_time=round(result.query_time, 3) if result.query_time else None,
                context=context,
            )
        )

    def start(self, message=None):
        pass

    def finish(self, message=None):
        pass


_OVERRIDE = json.loads((pathlib.Path(__file__).parent / "site_overrides.json").read_text("utf-8"))
PATCH: dict[str, dict] = _OVERRIDE.get("patch", {})
TIDAK_ANDAL: dict[str, str] = _OVERRIDE.get("tidak_andal", {})


class KatalogSitus:
    """Manifest situs Sherlock, diambil sekali lalu disegarkan berkala.

    Tanpa cache, tiap pemindaian menarik ulang manifest dari jaringan — lambat
    dan membuat kita jadi klien yang berisik bagi data.sherlockproject.xyz.
    """

    def __init__(self, ttl_detik: int = 6 * 3600):
        self._ttl = ttl_detik
        self._lock = threading.Lock()
        self._sites: SitesInformation | None = None
        self._diambil = 0.0

    def sites(self) -> SitesInformation:
        with self._lock:
            if self._sites is None or time.time() - self._diambil > self._ttl:
                s = SitesInformation()
                # Tambalan diterapkan setiap kali manifest disegarkan, bukan sekali saat impor —
                # kalau tidak, manifest baru akan diam-diam mengembalikan entri yang rusak.
                for nama, tambalan in PATCH.items():
                    situs = s.sites.get(nama)
                    if situs is None:
                        continue
                    bersih = {k: v for k, v in tambalan.items() if not k.startswith("_")}
                    situs.information = {**situs.information, **bersih}
                    # urlProbe lama harus dibuang, bukan ditimpa: selama ia ada, Sherlock
                    # memakainya dan url langsung yang baru tidak pernah tersentuh.
                    if "urlProbe" not in bersih:
                        situs.information.pop("urlProbe", None)
                self._sites = s
                self._diambil = time.time()
            return self._sites

    def data(self, sertakan_nsfw: bool) -> dict[str, dict]:
        s = self.sites()
        return {
            site.name: site.information
            for site in s
            if sertakan_nsfw or not site.is_nsfw
        }

    def url_untuk(self, nama_situs: str, username: str) -> str | None:
        """URL profil dibangun DARI MANIFEST, bukan dari masukan pengguna.

        Endpoint metadata karenanya tidak pernah menerima URL bebas — itu yang menutup
        peluang server dipakai menembak alamat internal (SSRF).
        """
        for s in self.sites():
            if s.name == nama_situs:
                return s.url_username_format.replace("{}", username)
        return None

    def daftar(self) -> list[dict]:
        return [
            {"name": s.name, "url_main": s.information.get("urlMain"), "nsfw": bool(s.is_nsfw)}
            for s in self.sites()
        ]


KATALOG = KatalogSitus()


def pindai(
    username: str,
    *,
    sertakan_nsfw: bool = False,
    timeout: int = 30,
    hanya: list[str] | None = None,
) -> Iterator[dict]:
    """Hasilkan event dict berurutan: mulai → hasil per situs → selesai.

    sherlock() dijalankan di thread terpisah karena ia memblokir sampai semua
    situs selesai; generator ini membaca antrean sambil menunggu.
    """
    site_data = KATALOG.data(sertakan_nsfw)
    if hanya:
        pilih = {n.casefold() for n in hanya}
        site_data = {k: v for k, v in site_data.items() if k.casefold() in pilih}
    if not site_data:
        yield {"type": "error", "message": "Tidak ada situs yang cocok dengan filter."}
        return

    q: queue.Queue = queue.Queue()
    notify = _Antrean(q, site_data)
    galat: list[BaseException] = []

    def kerja():
        try:
            sherlock(username, site_data, notify, timeout=timeout)
        except BaseException as e:  # noqa: BLE001 — apa pun yang gagal harus sampai ke klien
            galat.append(e)
        finally:
            q.put(None)  # sentinel selesai

    t = threading.Thread(target=kerja, daemon=True)
    mulai = time.time()
    t.start()

    yield {"type": "start", "username": username, "total": len(site_data)}

    selesai = 0
    ketemu = 0
    while True:
        item = q.get()
        if item is None:
            break
        selesai += 1
        if item.status == str(QueryStatus.CLAIMED).lower():
            ketemu += 1
        yield {"type": "result", "done": selesai, **asdict(item)}

    if galat:
        yield {"type": "error", "message": f"{type(galat[0]).__name__}: {galat[0]}"}
        return

    yield {
        "type": "done",
        "total": len(site_data),
        "checked": selesai,
        "found": ketemu,
        "elapsed": round(time.time() - mulai, 2),
    }
