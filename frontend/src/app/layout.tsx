import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

// Used for expedientes, CPV codes, scores and the elapsed timer -- everything where the
// characters are data rather than prose.
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Compass — radar de licitaciones públicas",
    // Tender pages set their own full title (see their `generateMetadata`), so this only
    // covers anything that doesn't.
    template: "%s",
  },
  description:
    "Las licitaciones de PLACSP que encajan con tu perfil, con el pliego leído y un veredicto citado.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        {/* First stop for a keyboard user, and invisible until focused: the header links
            come before the content on every page. */}
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-10 focus:rounded-sm focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:shadow-lifted"
        >
          Saltar al contenido
        </a>

        <header className="border-b border-border bg-surface">
          <div className="mx-auto flex max-w-5xl flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-4 sm:px-6">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Compass
            </Link>
            <span className="text-sm text-muted">radar de licitaciones públicas</span>
            <Link
              href="/perfil"
              className="ml-auto text-sm text-muted hover:text-foreground"
            >
              Tu perfil
            </Link>
          </div>
        </header>

        <main
          id="contenido"
          className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6"
        >
          {children}
        </main>

        <footer className="border-t border-border px-4 py-5 text-center text-xs leading-relaxed text-muted sm:px-6">
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
