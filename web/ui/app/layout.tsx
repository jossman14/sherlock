import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sherlock — Pencarian Jejak Username",
  description:
    "Periksa keberadaan satu username di ratusan situs sekaligus. Antarmuka web untuk Sherlock, hasil mengalir langsung saat tiap situs selesai diperiksa.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
