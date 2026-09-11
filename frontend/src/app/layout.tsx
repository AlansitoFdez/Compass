import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Compass — radar de licitaciones públicas",
  description:
    "Las licitaciones de PLACSP que encajan con tu perfil, con el pliego leído y un veredicto citado.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="border-b border-border bg-surface">
          <div className="mx-auto flex max-w-5xl items-baseline gap-3 px-6 py-4">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Compass
            </Link>
            <span className="text-sm text-muted">
              radar de licitaciones públicas
            </span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
          {children}
        </main>
        <footer className="border-t border-border px-6 py-4 text-center text-xs text-muted">
          Datos reales de{" "}
          <a
            className="underline underline-offset-2 hover:text-foreground"
            href="https://contrataciondelestado.es"
            target="_blank"
            rel="noreferrer"
          >
            PLACSP
          </a>
          . El veredicto lo calcula el código, nunca el modelo.
        </footer>
      </body>
    </html>
  );
}
