import Link from "next/link";

/** Shown for an expediente that doesn't exist, and for any unknown URL. */
export default function NotFound() {
  return (
    <div className="mx-auto max-w-prose py-12 text-center">
      <p className="field-label">No encontrado</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">
        Esta licitación no está en el corpus
      </h1>
      <p className="mt-3 text-sm text-muted">
        O nunca se ingirió, o su expediente se escribe de otra forma. Compass sólo guarda
        el vertical de servicios informáticos (división CPV 72).
      </p>
      <Link
        href="/"
        className="mt-6 inline-block text-sm text-accent underline underline-offset-2"
      >
        Volver a los matches
      </Link>
    </div>
  );
}
