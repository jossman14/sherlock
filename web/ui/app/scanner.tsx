"use client";

import { useCallback, useMemo, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Status = "claimed" | "available" | "unknown" | "illegal" | "waf";

type Hasil = {
  site: string;
  url_user: string | null;
  url_main: string | null;
  status: Status;
  query_time: number | null;
  context: string | null;
};

type Fase = "idle" | "scanning" | "done" | "error" | "stopped";

const LABEL: Record<Status, string> = {
  claimed: "Ditemukan",
  available: "Tidak ada",
  unknown: "Gagal diperiksa",
  illegal: "Tidak berlaku",
  waf: "Diblokir WAF",
};

/** Urutan tampil: yang paling berarti bagi penelusur lebih dulu. */
const URUTAN: Status[] = ["claimed", "unknown", "waf", "available", "illegal"];

export function Scanner() {
  const [username, setUsername] = useState("");
  const [nsfw, setNsfw] = useState(false);
  const [fase, setFase] = useState<Fase>("idle");
  const [hasil, setHasil] = useState<Hasil[]>([]);
  const [total, setTotal] = useState(0);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [galat, setGalat] = useState("");
  const [target, setTarget] = useState("");
  const [saring, setSaring] = useState("");
  const [tampilSemua, setTampilSemua] = useState(false);
  const batal = useRef<AbortController | null>(null);

  const ditemukan = useMemo(() => hasil.filter((h) => h.status === "claimed"), [hasil]);
  const perStatus = useMemo(() => {
    const m = new Map<Status, Hasil[]>();
    for (const h of hasil) m.set(h.status, [...(m.get(h.status) ?? []), h]);
    return m;
  }, [hasil]);

  const progres = total > 0 ? Math.min(100, (hasil.length / total) * 100) : 0;

  const hentikan = useCallback(() => {
    batal.current?.abort();
    batal.current = null;
    setFase((f) => (f === "scanning" ? "stopped" : f));
  }, []);

  const mulai = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const u = username.trim();
      if (!u || fase === "scanning") return;

      batal.current?.abort();
      const ac = new AbortController();
      batal.current = ac;

      setFase("scanning");
      setHasil([]);
      setTotal(0);
      setElapsed(null);
      setGalat("");
      setTarget(u);
      setTampilSemua(false);

      try {
        const res = await fetch(
          `${API}/api/scan?username=${encodeURIComponent(u)}&nsfw=${nsfw}`,
          { signal: ac.signal, headers: { Accept: "text/event-stream" } }
        );

        // 429 / 400 datang sebagai JSON biasa, bukan aliran — dibaca dulu supaya
        // pesan sebenarnya (mis. sisa waktu tunggu) sampai ke pengguna.
        if (!res.ok || !res.body) {
          const data = await res.json().catch(() => null);
          setGalat(data?.error ?? `Permintaan gagal (${res.status}).`);
          setFase("error");
          return;
        }

        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let sisa = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          sisa += dec.decode(value, { stream: true });
          const potong = sisa.split("\n\n");
          sisa = potong.pop() ?? "";
          for (const blok of potong) {
            const baris = blok.split("\n").find((b) => b.startsWith("data: "));
            if (!baris) continue;
            const ev = JSON.parse(baris.slice(6));
            if (ev.type === "start") setTotal(ev.total);
            else if (ev.type === "result") setHasil((h) => [...h, ev as Hasil]);
            else if (ev.type === "done") {
              setElapsed(ev.elapsed);
              setFase("done");
            } else if (ev.type === "error") {
              setGalat(ev.message);
              setFase("error");
            }
          }
        }
        setFase((f) => (f === "scanning" ? "done" : f));
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setGalat("Koneksi ke pemindai terputus. Coba lagi.");
        setFase("error");
      }
    },
    [username, nsfw, fase]
  );

  const unduh = useCallback(
    (format: "json" | "csv") => {
      const isi =
        format === "json"
          ? JSON.stringify({ username: target, results: hasil }, null, 2)
          : ["situs,status,url,detik", ...hasil.map((h) =>
              [h.site, h.status, h.url_user ?? "", h.query_time ?? ""].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")
            )].join("\n");
      const url = URL.createObjectURL(new Blob([isi], { type: format === "json" ? "application/json" : "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `sherlock-${target}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [hasil, target]
  );

  const cocok = (h: Hasil) =>
    !saring || h.site.toLowerCase().includes(saring.toLowerCase());

  return (
    <main className="space-y-10">
      {/* ── Hero + kolom pencarian ───────────────────────────────── */}
      <section className="pt-6 sm:pt-12">
        <p className="eyebrow">Sherlock · {total || 400}+ situs</p>
        <h1 className="display mt-4 text-[clamp(2.4rem,1.2rem+5vw,4.5rem)]">
          Satu username,
          <br />
          <span className="text-[var(--accent)]">jejaknya di mana-mana.</span>
        </h1>
        <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-[var(--muted)]">
          Masukkan satu username, dan tiap situs dilaporkan begitu selesai diperiksa —
          tidak perlu menunggu semuanya rampung.
        </p>

        <form onSubmit={mulai} className="mt-8 flex flex-col gap-3 sm:flex-row">
          <div className="field flex flex-1 items-center gap-2 px-4 py-3">
            <span className="mono select-none text-lg text-[var(--faint)]" aria-hidden>@</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username"
              aria-label="Username yang dicari"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={64}
              className="mono w-full text-base tracking-tight sm:text-lg"
            />
            {username && (
              <button
                type="button"
                onClick={() => setUsername("")}
                aria-label="Kosongkan"
                className="text-[var(--faint)] transition hover:text-[var(--ink)]"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          {fase === "scanning" ? (
            <button type="button" onClick={hentikan} className="btn btn-ghost sm:px-6">
              Hentikan
            </button>
          ) : (
            <button type="submit" disabled={!username.trim()} className="btn btn-primary sm:px-7">
              Telusuri
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
          )}
        </form>

        <label className="mt-4 inline-flex cursor-pointer items-center gap-2 text-xs text-[var(--muted)]">
          <input
            type="checkbox"
            checked={nsfw}
            onChange={(e) => setNsfw(e.target.checked)}
            className="h-3.5 w-3.5 accent-[var(--accent)]"
          />
          Sertakan situs bertanda NSFW
        </label>
      </section>

      {galat && (
        <div role="alert" className="surface rise border-[color-mix(in_srgb,var(--failed)_45%,transparent)] p-4 text-sm">
          <span className="font-semibold text-[var(--failed)]">Gagal. </span>
          <span className="text-[var(--muted)]">{galat}</span>
        </div>
      )}

      {fase !== "idle" && !galat && (
        <>
          {/* ── Papan angka ──────────────────────────────────────── */}
          <section className="surface-hi overflow-hidden">
            <div className="grid grid-cols-2 divide-x divide-[var(--line-soft)] sm:grid-cols-4">
              <Angka label="Target" nilai={`@${target}`} aksen />
              <Angka label="Ditemukan" nilai={String(ditemukan.length)} warna="var(--claimed)" />
              <Angka label="Diperiksa" nilai={`${hasil.length}/${total || "…"}`} />
              <Angka
                label={fase === "scanning" ? "Berjalan" : "Selesai"}
                nilai={elapsed !== null ? `${elapsed}s` : fase === "scanning" ? "…" : "—"}
              />
            </div>
            <div className="relative h-1 overflow-hidden bg-[var(--line-soft)]">
              <div
                className={`h-full bg-[var(--accent)] transition-[width] duration-300 ${fase === "scanning" ? "sweep relative" : ""}`}
                style={{ width: `${progres}%` }}
                role="progressbar"
                aria-valuenow={Math.round(progres)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Kemajuan pemindaian"
              />
            </div>
          </section>

          {/* ── Temuan ───────────────────────────────────────────── */}
          <section>
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="display text-2xl">
                Temuan
                {ditemukan.length > 0 && (
                  <span className="mono ml-2 align-middle text-sm font-normal text-[var(--claimed)]">
                    {ditemukan.length} akun
                  </span>
                )}
              </h2>
              {hasil.length > 0 && (
                <div className="flex gap-2">
                  <button onClick={() => unduh("json")} className="btn btn-ghost !px-3 !py-1.5 !text-xs">JSON</button>
                  <button onClick={() => unduh("csv")} className="btn btn-ghost !px-3 !py-1.5 !text-xs">CSV</button>
                </div>
              )}
            </div>

            {ditemukan.length === 0 ? (
              <p className="mt-4 text-sm text-[var(--muted)]">
                {fase === "scanning"
                  ? "Belum ada akun yang cocok. Pemeriksaan masih berjalan…"
                  : "Tidak ada akun yang cocok dengan username ini."}
              </p>
            ) : (
              <ul className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {ditemukan.map((h) => (
                  <li key={h.site} className="rise">
                    <a
                      href={h.url_user ?? "#"}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="group block h-full rounded-[var(--r-2)] border border-[color-mix(in_srgb,var(--claimed)_28%,var(--line))] bg-[color-mix(in_srgb,var(--claimed)_6%,var(--surface))] p-4 transition hover:border-[var(--claimed)] hover:bg-[color-mix(in_srgb,var(--claimed)_11%,var(--surface))]"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold tracking-tight">{h.site}</span>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="mt-1 shrink-0 text-[var(--faint)] transition group-hover:text-[var(--claimed)]">
                          <path d="M7 17 17 7M8 7h9v9" />
                        </svg>
                      </div>
                      <p className="mono mt-2 truncate text-xs text-[var(--muted)]">{h.url_user}</p>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* ── Rincian seluruh situs ────────────────────────────── */}
          {hasil.length > ditemukan.length && (
            <section>
              <button
                onClick={() => setTampilSemua((v) => !v)}
                aria-expanded={tampilSemua}
                className="btn btn-ghost w-full !justify-between"
              >
                <span>Rincian {hasil.length} situs yang sudah diperiksa</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                  style={{ transform: tampilSemua ? "rotate(180deg)" : undefined, transition: "transform 200ms" }}>
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>

              {tampilSemua && (
                <div className="rise mt-4 space-y-6">
                  <div className="field flex items-center gap-2 px-3 py-2">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-[var(--faint)]">
                      <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
                    </svg>
                    <input
                      value={saring}
                      onChange={(e) => setSaring(e.target.value)}
                      placeholder="Saring nama situs…"
                      aria-label="Saring nama situs"
                      className="mono w-full text-sm"
                    />
                  </div>

                  {URUTAN.filter((s) => s !== "claimed").map((s) => {
                    const grup = (perStatus.get(s) ?? []).filter(cocok);
                    if (grup.length === 0) return null;
                    return (
                      <div key={s}>
                        <div className="flex items-center gap-3">
                          <h3 className="eyebrow">{LABEL[s]}</h3>
                          <span className="mono text-xs text-[var(--faint)]">{grup.length}</span>
                          <div className="rule flex-1" />
                        </div>
                        {(s === "unknown" || s === "waf") && grup.some((h) => h.context) && (
                          <p className="mt-2 text-xs text-[var(--faint)]">
                            Situs ini gagal diperiksa, bukan berarti akunnya tidak ada.
                            Arahkan kursor ke namanya untuk alasannya.
                          </p>
                        )}
                        <ul className="mt-3 flex flex-wrap gap-1.5">
                          {grup.map((h) => (
                            <li
                              key={h.site}
                              title={h.context ?? h.url_main ?? h.site}
                              className={`chip ${h.context ? "cursor-help" : ""}`}
                              style={s === "unknown" || s === "waf" ? { color: "var(--failed)", borderColor: "color-mix(in srgb, var(--failed) 25%, var(--line))" } : undefined}
                            >
                              {h.site}
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          )}
        </>
      )}

      <footer className="pt-6 text-xs leading-relaxed text-[var(--faint)]">
        Hasil &ldquo;ditemukan&rdquo; berarti ada halaman dengan nama itu, bukan bukti bahwa orangnya sama.
        Sebagian situs memakai proteksi bot, jadi statusnya bisa &ldquo;gagal diperiksa&rdquo; tanpa berarti kosong.
        Gunakan seperlunya dan patuhi ketentuan tiap situs.
      </footer>
    </main>
  );
}

function Angka({ label, nilai, warna, aksen }: { label: string; nilai: string; warna?: string; aksen?: boolean }) {
  return (
    <div className="px-4 py-4 sm:px-5">
      <p className="eyebrow">{label}</p>
      <p
        className="mono mt-1.5 truncate text-xl font-semibold tracking-tight sm:text-2xl"
        style={{ color: warna ?? (aksen ? "var(--accent)" : undefined) }}
      >
        {nilai}
      </p>
    </div>
  );
}
