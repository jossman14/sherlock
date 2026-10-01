# Sherlock (fork) + Sherlock Web

Fork dari [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) — alat OSINT
untuk mencari akun media sosial berdasarkan username di 400+ situs — dengan tambahan
**antarmuka web** (`web/`) yang mengalirkan hasil per situs secara langsung.

Dokumentasi asli proyek hulu (bahasa Inggris) ada di [`docs/README.md`](docs/README.md).
Dokumentasi rinci antarmuka web ada di [`web/README.md`](web/README.md).

## Fitur utama

- CLI Sherlock (paket `sherlock_project`, versi 0.16.1) untuk memeriksa satu atau beberapa username.
- **Sherlock Web**: API FastAPI yang membungkus `sherlock_project` dan mengalirkan hasil lewat SSE,
  plus UI Next.js yang mem-proxy `/api` ke API tersebut.
- Kartu profil dari metadata Open Graph (`GET /api/profile`), dengan URL dibangun dari manifest
  dan pemeriksaan ulang tiap redirect terhadap alamat privat (mitigasi SSRF).
- Pembatasan pemakaian per IP dan per server untuk menjaga reputasi IP.
- Verifikasi ulang tiap hasil "ditemukan" sebelum dilaporkan.
- Tambalan manifest hulu lewat `web/api/site_overrides.json` (mis. X, Instagram, TikTok).

## Tech stack

- Python 3 (Poetry, `requests`, `requests-futures`, `pandas`, dll.) — inti Sherlock
- FastAPI + Uvicorn — `web/api`
- Next.js 16, React 19, Tailwind CSS 4, TypeScript — `web/ui`
- Docker Compose (diterbitkan lewat Traefik Dokploy)

## Struktur folder

```
sherlock_project/   Kode inti Sherlock (CLI, manifest situs di resources/data.json)
tests/              Pengujian pytest
devel/              Skrip pengembangan (daftar situs, ringkasan validasi)
docs/               Dokumentasi hulu
web/api/            API FastAPI (SSE, rate limit, profil, verifikasi)
web/ui/             UI Next.js
web/docker-compose.yml
.actor/             Konfigurasi Apify Actor (dari hulu)
Dockerfile          Image CLI Sherlock (dari hulu)
```

## Cara menjalankan

CLI:

```bash
pip install -e .
sherlock <username>
```

Antarmuka web (pengembangan):

```bash
python3 -m venv .venv && .venv/bin/pip install -e . fastapi "uvicorn[standard]"
.venv/bin/uvicorn main:app --app-dir web/api --port 8477      # API
cd web/ui && npm install && npm run dev                        # UI di :3000
```

Antarmuka web (produksi):

```bash
cd web && docker compose up -d --build
```

UI terbit di port `SHERLOCK_PORT` (bawaan 8090); API hanya ada di jaringan internal compose.
Compose mengharapkan jaringan eksternal `dokploy-network` sudah ada.

Pengujian:

```bash
pytest
```

## Konfigurasi environment

Variabel untuk `web/` (semua opsional, punya nilai bawaan):

- `SHERLOCK_RATE_MAX`, `SHERLOCK_RATE_WINDOW`, `SHERLOCK_MAX_CONCURRENT`,
  `SHERLOCK_MAX_CONCURRENT_IP`, `SHERLOCK_TIMEOUT`, `SHERLOCK_PROFILE_MAX`
- `SHERLOCK_CORS_ORIGINS`
- `SHERLOCK_PORT`, `SHERLOCK_HOST` (compose)
- `SHERLOCK_API_URL` (build arg UI; dibekukan saat build)

## Lisensi

MIT (mengikuti proyek hulu), lihat [`LICENSE`](LICENSE).
