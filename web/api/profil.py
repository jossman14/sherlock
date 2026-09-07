"""Metadata profil dari tag Open Graph — data yang situs memang terbitkan untuk pratinjau tautan.

Sengaja TIDAK mengambil isi postingan: X dan Instagram sudah menutup akses anonim ke linimasa,
dan mengambilnya butuh sesi login yang melanggar ketentuan keduanya. Yang diambil di sini hanya
og:title/description/image — persis yang muncul saat tautan ditempel di WhatsApp atau Slack.
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
import threading
import time
from urllib.parse import urlparse

import requests

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BATAS_BYTE = 512 * 1024   # cukup untuk <head>; halaman raksasa dipotong, bukan diunduh penuh
TIMEOUT = 8
MAKS_REDIRECT = 3
TTL_CACHE = 900

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def _publik(host: str) -> bool:
    """Tolak host yang menunjuk ke jaringan internal.

    Wajib ada meski URL-nya dibangun dari manifest: sebuah situs bisa mengalihkan kita ke
    169.254.169.254 (metadata cloud) atau ke alamat privat, dan permintaan itu berangkat dari
    dalam VPS. Tiap lompatan redirect diperiksa ulang, bukan hanya URL pertama.
    """
    try:
        for keluarga, _, _, _, alamat in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(alamat[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


_META = re.compile(
    r"""<meta[^>]+(?:property|name)\s*=\s*["']([^"']+)["'][^>]*content\s*=\s*["']([^"']*)["']"""
    r"""|<meta[^>]+content\s*=\s*["']([^"']*)["'][^>]*(?:property|name)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_DIMINATI = {"og:title", "og:description", "og:image", "og:site_name", "description", "twitter:image"}


def _urai(teks: str) -> dict:
    meta: dict[str, str] = {}
    for m in _META.finditer(teks):
        kunci = (m.group(1) or m.group(4) or "").lower()
        nilai = m.group(2) if m.group(1) else m.group(3)
        if kunci in _DIMINATI and nilai and kunci not in meta:
            meta[kunci] = html.unescape(nilai.strip())
    judul = _TITLE.search(teks)
    nama_situs = meta.get("og:site_name")
    tajuk = meta.get("og:title") or (html.unescape(judul.group(1).strip()) if judul else None)
    # Sebagian situs mengisi og:title dengan nama situsnya sendiri ("Bitbucket"), bukan nama
    # pemilik akun. Menampilkannya sebagai "nama tampilan" itu keliru, jadi dibuang.
    if tajuk and nama_situs and tajuk.strip().casefold() == nama_situs.strip().casefold():
        tajuk = None
    return {
        "title": tajuk,
        "description": meta.get("og:description") or meta.get("description"),
        "image": meta.get("og:image") or meta.get("twitter:image"),
        "site_name": meta.get("og:site_name"),
    }


def ambil(url: str) -> dict:
    """Metadata satu halaman profil. Hasilnya di-cache agar tidak menembak situs berulang."""
    sekarang = time.time()
    with _lock:
        simpan = _cache.get(url)
        if simpan and sekarang - simpan[0] < TTL_CACHE:
            return simpan[1]

    hasil: dict = {"url": url, "title": None, "description": None, "image": None, "site_name": None}
    tujuan = url
    try:
        for _ in range(MAKS_REDIRECT + 1):
            host = urlparse(tujuan).hostname or ""
            if urlparse(tujuan).scheme not in ("http", "https") or not _publik(host):
                hasil["error"] = "Alamat tujuan tidak diizinkan."
                break
            r = requests.get(
                tujuan,
                headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
                timeout=TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
            if r.is_redirect or r.is_permanent_redirect:
                tujuan = requests.compat.urljoin(tujuan, r.headers.get("location", ""))
                r.close()
                continue
            if r.status_code >= 400:
                hasil["error"] = f"Situs membalas {r.status_code}."
                r.close()
                break
            potongan = r.raw.read(BATAS_BYTE, decode_content=True) or b""
            r.close()
            hasil.update(_urai(potongan.decode("utf-8", "ignore")))
            hasil["final_url"] = tujuan
            break
        else:
            hasil["error"] = "Terlalu banyak pengalihan."
    except requests.RequestException as e:
        hasil["error"] = f"Gagal mengambil: {type(e).__name__}"

    with _lock:
        _cache[url] = (sekarang, hasil)
        if len(_cache) > 2000:  # jaga jejak memori tetap kecil
            for k in [k for k, (t, _) in _cache.items() if sekarang - t > TTL_CACHE]:
                _cache.pop(k, None)
    return hasil
