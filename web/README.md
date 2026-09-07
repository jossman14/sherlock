# Sherlock Web

Antarmuka web untuk [Sherlock](https://github.com/sherlock-project/sherlock) — memeriksa
keberadaan satu username di 400+ situs, dengan hasil **mengalir langsung** per situs
alih-alih menunggu seluruh pemindaian selesai (~30 detik).

```
web/
├── api/   FastAPI tipis yang membungkus sherlock_project, mengalirkan hasil lewat SSE
└── ui/    Next.js — mem-proxy /api ke FastAPI, jadi tidak ada CORS dan SSE apa adanya
```

## Menjalankan (pengembangan)

```bash
python3 -m venv .venv && .venv/bin/pip install -e . fastapi "uvicorn[standard]"
.venv/bin/uvicorn main:app --app-dir web/api --port 8477      # API
cd web/ui && npm install && npm run dev                        # UI di :3000
```

## Menjalankan (produksi)

```bash
cd web && docker compose up -d --build
```

UI terbit di `${SHERLOCK_PORT:-8090}`; API hanya ada di jaringan internal compose.

## Pembatasan pemakaian

Satu pemindaian menembak 400+ situs sekaligus. Yang dilindungi bukan CPU server melainkan
**reputasi IP-nya** — situs besar cepat memblokir IP yang menembak berulang kali. Batas
bawaan (bisa diubah lewat environment):

| Variabel | Bawaan | Arti |
|---|---:|---|
| `SHERLOCK_RATE_MAX` | 5 | pemindaian per IP per jendela |
| `SHERLOCK_RATE_WINDOW` | 600 | panjang jendela (detik) |
| `SHERLOCK_MAX_CONCURRENT` | 4 | pemindaian serentak seluruh server |
| `SHERLOCK_MAX_CONCURRENT_IP` | 1 | pemindaian serentak per IP |
| `SHERLOCK_TIMEOUT` | 30 | batas waktu tiap situs (detik) |

## Catatan teknis yang mudah terlewat

**`Cache-Control: no-transform` pada respons SSE tidak boleh dihapus.** Tanpa itu, proxy di
depan (Next.js, nginx, CDN) akan meng-gzip aliran ini, dan gzip menahan data sampai buffernya
penuh — hasil pengukuran: potongan pertama baru sampai ke browser setelah **30 detik**,
sekaligus 87 KB. Dengan header itu, potongan pertama tiba dalam **20 milidetik**.

**Alamat API dibekukan saat build UI.** `rewrites()` Next.js masuk ke routes-manifest pada
waktu build, jadi `SHERLOCK_API_URL` diberikan sebagai build arg — menyetelnya sebagai
environment runtime saja tidak berpengaruh dan UI akan mencari API di alamat pengembangan.

**Nama layanan compose harus unik lintas VPS.** Kontainer UI ikut jaringan overlay
`dokploy-network` yang dipakai bersama seluruh aplikasi di server. Nama sependek `api` sudah
dipakai stack lain di sana, dan permintaan `/api` kami sempat mendarat di API milik aplikasi
tetangga — makanya layanannya bernama `sherlock-api`.

**`HOSTNAME=0.0.0.0` wajib di image UI.** `server.js` hasil `output: standalone` memakai
`$HOSTNAME` sebagai alamat bind, dan Docker mengisinya dengan ID kontainer; tanpa override,
Next hanya mendengar di satu antarmuka dan port yang dipublikasikan ke host menolak koneksi.

**Manifest hulu ditambal lewat `web/api/site_overrides.json`.** Sherlock memeriksa sebagian
situs besar lewat proxy pihak ketiga; ketika proxy itu mati atau memblokir IP kita, Sherlock
tidak melaporkan kegagalan melainkan "tidak ada akun". Negatif palsu yang diam seperti itu
lebih menyesatkan daripada error. Yang sudah ditambal (diuji 2026-09-07 dari VPS):

| Situs | Masalah hulu | Tindakan |
|---|---|---|
| X (Twitter) | `urlProbe` menunjuk nitter.privacydev.net yang mati → selalu "Error Connecting" | diperiksa langsung ke x.com; judul halaman membedakan ada/tidak dengan jelas |
| Instagram | membalas 429 untuk semua IP pusat data; proxy imginn.com membalas 403 | ditandai tidak andal → dilaporkan "gagal diperiksa" |
| TikTok | melaporkan "claimed" bahkan untuk username acak | ditandai tidak andal → dilaporkan "gagal diperiksa" |

Tiap entri di berkas itu wajib menyertakan alasan dan tanggal pembuktiannya, supaya tambalan
bisa dicabut lagi kalau keadaan hulu berubah.

**Status hasil bukan biner.** `claimed` berarti ada halaman dengan nama itu — bukan bukti
orangnya sama. `unknown`/`waf` berarti situsnya gagal diperiksa (proteksi bot), bukan berarti
kosong. UI menampilkan ketiganya terpisah supaya perbedaan ini tidak hilang.
