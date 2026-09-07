"""Self-check pembatas laju — jalankan: python web/api/test_ratelimit.py"""
import time
from ratelimit import BatasLaju, Kuota

b = BatasLaju(maks=3, jendela_detik=1)
assert all(b.izinkan("a")[0] for _ in range(3)), "3 permintaan pertama harus lolos"
boleh, tunggu = b.izinkan("a")
assert not boleh and tunggu >= 1, "permintaan ke-4 harus ditolak dengan saran tunggu"
assert b.izinkan("b")[0], "IP lain tidak boleh ikut kena batas"
time.sleep(1.05)
assert b.izinkan("a")[0], "jendela lewat → kuota pulih"

k = Kuota(maks_global=2, maks_per_ip=1)
assert k.ambil("x") and not k.ambil("x"), "satu IP dibatasi satu pemindaian serentak"
assert k.ambil("y"), "IP kedua masih boleh"
assert not k.ambil("z"), "batas global menahan IP ketiga"
k.lepas("x")
assert k.ambil("z"), "slot yang dilepas bisa dipakai lagi"

print("ratelimit self-check OK")
