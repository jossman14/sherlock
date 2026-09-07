"""API web untuk Sherlock: satu endpoint SSE yang mengalirkan hasil per situs."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import AsyncIterator

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from profil import ambil as ambil_profil
from ratelimit import BatasLaju, Kuota
from runner import KATALOG, pindai

# Batas bawaan dipilih konservatif: satu pemindaian menembak 400+ situs sekaligus,
# jadi yang dilindungi bukan CPU kita melainkan reputasi IP VPS di mata situs-situs itu.
MAKS_PINDAI = int(os.getenv("SHERLOCK_RATE_MAX", "5"))
JENDELA = int(os.getenv("SHERLOCK_RATE_WINDOW", "600"))
MAKS_SERENTAK = int(os.getenv("SHERLOCK_MAX_CONCURRENT", "4"))
MAKS_SERENTAK_IP = int(os.getenv("SHERLOCK_MAX_CONCURRENT_IP", "1"))
TIMEOUT = int(os.getenv("SHERLOCK_TIMEOUT", "30"))
ASAL = [o for o in os.getenv("SHERLOCK_CORS_ORIGINS", "*").split(",") if o]

# Sherlock sendiri menolak username dengan karakter di luar pola ini pada sebagian situs;
# menyaring di depan mencegah permintaan sia-sia sekaligus menutup penyuntikan lewat URL.
POLA_USERNAME = re.compile(r"^[\w.\-]{1,64}$", re.UNICODE)

# Permintaan metadata jauh lebih ringan daripada pemindaian (satu situs, bukan 400),
# jadi batasnya terpisah dan longgar — tapi tetap ada, karena ia tetap menembak keluar.
MAKS_PROFIL = int(os.getenv("SHERLOCK_PROFILE_MAX", "120"))

batas = BatasLaju(MAKS_PINDAI, JENDELA)
batas_profil = BatasLaju(MAKS_PROFIL, JENDELA)
kuota = Kuota(MAKS_SERENTAK, MAKS_SERENTAK_IP)

app = FastAPI(title="Sherlock Web", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware, allow_origins=ASAL, allow_methods=["GET"], allow_headers=["*"]
)


def ip_klien(req: Request) -> str:
    """IP asli di balik reverse proxy. Hanya header terdepan yang dipakai."""
    fwd = req.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else "?"


@app.get("/api/health")
def health():
    return {"ok": True, "sites": len(KATALOG.sites())}


@app.get("/api/sites")
def sites():
    daftar = KATALOG.daftar()
    return {"total": len(daftar), "sites": daftar}


@app.get("/api/limits")
def limits(request: Request):
    """Dipakai UI untuk menampilkan sisa kuota tanpa harus gagal dulu."""
    return {
        "max_scans": MAKS_PINDAI,
        "window_seconds": JENDELA,
        "max_concurrent_per_ip": MAKS_SERENTAK_IP,
        "timeout_seconds": TIMEOUT,
    }


@app.get("/api/profile")
async def profile(request: Request, site: str = Query(..., max_length=80), username: str = Query(..., max_length=64)):
    """Metadata Open Graph satu profil: nama tampilan, bio, foto profil.

    BUKAN isi postingan — X dan Instagram menutup akses anonim ke linimasa, dan mengambilnya
    memerlukan sesi login yang melanggar ketentuan keduanya.
    """
    username = username.strip()
    if not POLA_USERNAME.match(username):
        return JSONResponse({"error": "Username tidak sah."}, status_code=400)

    boleh, tunggu = batas_profil.izinkan(ip_klien(request))
    if not boleh:
        return JSONResponse({"error": f"Terlalu banyak permintaan. Tunggu {tunggu} detik."},
                            status_code=429, headers={"Retry-After": str(tunggu)})

    url = KATALOG.url_untuk(site, username)
    if not url:
        return JSONResponse({"error": "Situs tidak dikenal."}, status_code=404)

    data = await asyncio.get_running_loop().run_in_executor(None, ambil_profil, url)
    # Judul yang isinya cuma nama situsnya sendiri ("Bitbucket") bukan nama pemilik akun.
    # Sebagian situs tidak memasang og:site_name, jadi pembandingnya diambil dari manifest.
    judul = (data.get("title") or "").strip().casefold()
    if judul and judul == site.strip().casefold():
        data = {**data, "title": None}
    return data


async def _aliran(username: str, nsfw: bool, ip: str) -> AsyncIterator[str]:
    """Bungkus generator sinkron jadi SSE tanpa memblokir event loop."""
    antre: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def kerja():
        try:
            for ev in pindai(username, sertakan_nsfw=nsfw, timeout=TIMEOUT):
                loop.call_soon_threadsafe(antre.put_nowait, ev)
        finally:
            loop.call_soon_threadsafe(antre.put_nowait, None)

    tugas = loop.run_in_executor(None, kerja)
    try:
        while True:
            ev = await antre.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
    finally:
        # Klien menutup tab → kuota harus kembali, kalau tidak slotnya bocor.
        kuota.lepas(ip)
        tugas.cancel()


@app.get("/api/scan")
async def scan(
    request: Request,
    username: str = Query(..., min_length=1, max_length=64),
    nsfw: bool = Query(False),
):
    username = username.strip()
    if not POLA_USERNAME.match(username):
        return JSONResponse(
            {"error": "Username hanya boleh huruf, angka, titik, garis bawah, dan tanda hubung."},
            status_code=400,
        )

    ip = ip_klien(request)
    boleh, tunggu = batas.izinkan(ip)
    if not boleh:
        return JSONResponse(
            {"error": f"Terlalu banyak pemindaian. Coba lagi dalam {tunggu} detik.", "retry_after": tunggu},
            status_code=429,
            headers={"Retry-After": str(tunggu)},
        )
    if not kuota.ambil(ip):
        return JSONResponse(
            {"error": "Masih ada pemindaian yang berjalan. Tunggu sampai selesai."},
            status_code=429,
        )

    batas.bersihkan()
    return StreamingResponse(
        _aliran(username, nsfw, ip),
        media_type="text/event-stream",
        headers={
            # `no-transform` WAJIB: tanpa itu proxy di depan (Next.js, nginx, CDN) meng-gzip
            # aliran ini, dan gzip menahan data sampai buffernya penuh — hasilnya baru muncul
            # sekaligus di akhir, persis yang ingin dihindari oleh streaming.
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
