import { Scanner } from "./scanner";

export const dynamic = "force-static";

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-6xl px-5 pb-24 sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-4 py-6">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="grid h-9 w-9 place-items-center rounded-[var(--r-1)] border border-[var(--line)] bg-[var(--surface)] text-[var(--accent)]"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="11" cy="11" r="6.5" />
              <path d="m20 20-4.2-4.2" />
            </svg>
          </span>
          <div>
            <p className="text-sm font-semibold tracking-tight">Sherlock</p>
            <p className="eyebrow mt-0.5">Pencarian jejak username</p>
          </div>
        </div>
        <a
          href="https://github.com/sherlock-project/sherlock"
          target="_blank"
          rel="noreferrer noopener"
          className="chip transition hover:border-[var(--faint)] hover:text-[var(--ink)]"
        >
          sherlock-project · MIT
        </a>
      </header>

      <Scanner />
    </div>
  );
}
