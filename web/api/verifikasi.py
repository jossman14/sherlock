"""Verifikasi ulang tiap klaim "ditemukan" dengan satu permintaan HTTP sendiri.

Sebagian besar entri manifest Sherlock memakai `errorType: "message"`: ia hanya
mencari kalimat error di dalam badan respons dan MENGABAIKAN kode status. Dua
kelas halaman karenanya lolos sebagai "akun ditemukan":

  * halaman tantangan Cloudflare (HTTP 403, "Just a moment...") — situsnya
    memblokir kita, bukan menjawab;
  * halaman 404 yang kalimat errornya sudah berubah sejak manifest ditulis.

Terukur 2026-09-08 untuk satu username: AllMyLinks/DMOJ/DigitalSpy membalas 403
dan Hive/Jupyter/NICommunityForum membalas 404 — keenamnya dilaporkan ditemukan.
Memeriksa kode status sekali lagi menutup kedua kelas itu sekaligus, tanpa perlu
menambal manifest situs demi situs.
"""

from __future__ import annotations

import requests

_KEPALA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


def putusan(kode: int) -> tuple[str, str] | None:
    """None berarti klaim "ditemukan" tetap berdiri; selain itu (status, alasan)."""
    if kode in (401, 403, 429):
        return "unknown", f"Situs memblokir pemeriksaan dari server ini (HTTP {kode}) — keberadaan akun tidak bisa dipastikan."
    if kode in (404, 410):
        return "available", f"Verifikasi ulang: halaman profil tidak ada (HTTP {kode})."
    if kode >= 500:
        return "unknown", f"Situs sedang bermasalah (HTTP {kode}) — hasilnya tidak bisa dipercaya."
    return None


def periksa_ulang(url: str, timeout: int = 15) -> tuple[str, str] | None:
    # URL selalu berasal dari manifest (lihat KatalogSitus.url_untuk), tidak pernah
    # dari masukan pengguna, sehingga tidak ada peluang menembak alamat internal.
    try:
        r = requests.get(url, headers=_KEPALA, timeout=timeout, allow_redirects=True, stream=True)
        kode = r.status_code
        r.close()
    except requests.RequestException as e:
        return "unknown", f"Verifikasi ulang gagal terhubung: {type(e).__name__}."
    return putusan(kode)


if __name__ == "__main__":
    assert putusan(200) is None
    assert putusan(301) is None
    assert putusan(403)[0] == "unknown"
    assert putusan(429)[0] == "unknown"
    assert putusan(404)[0] == "available"
    assert putusan(410)[0] == "available"
    assert putusan(503)[0] == "unknown"
    print("ok")
