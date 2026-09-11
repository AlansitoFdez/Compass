"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { saveProvider, triggerBackfill, type Provider } from "@/lib/api";

/**
 * The screen someone sees the first time they open Compass.
 *
 * Until 5.4 this was a Python file to edit (`providers/seed.py`) holding one company's
 * real data. The profile is not configuration: it is what the funnel filters and ranks
 * against, and what the verdict compares a pliego's requirements to, so every field here
 * changes which licitaciones appear and whether the answer is APTO.
 *
 * Each field says what it decides, next to the field, rather than in a help page nobody
 * opens. That is not decoration -- a description written as a marketing sentence and one
 * written as a description of the work produce very different rankings, and there is no
 * way for the reader to know that unless it is said here.
 */

/** Splits a comma-or-newline separated field into trimmed, non-empty entries. */
function toList(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

/** An empty numeric field means "not declared", which is a real state, not zero. */
function toDecimal(value: string): string | null {
  const trimmed = value.trim().replace(",", ".");
  return trimmed === "" ? null : trimmed;
}

function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
  htmlFor: string;
}) {
  return (
    // A column with the control pushed to the bottom, so two fields side by side line
    // their inputs up even when one hint wraps to more lines than the other.
    <div className="flex h-full flex-col">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      <p className="mt-0.5 text-xs leading-relaxed text-muted">{hint}</p>
      <div className="mt-auto pt-1.5">{children}</div>
    </div>
  );
}

const INPUT_CLASS =
  "w-full rounded-sm border border-border bg-background px-3 py-2 text-sm " +
  "placeholder:text-muted focus:border-accent focus:outline-none";

export function ProviderForm({
  initial,
  corpusIsEmpty,
}: {
  initial: Provider | null;
  corpusIsEmpty: boolean;
}) {
  const router = useRouter();
  const [description, setDescription] = useState(initial?.description ?? "");
  const [cpvCodes, setCpvCodes] = useState((initial?.cpv_codes ?? []).join(", "));
  const [minBudget, setMinBudget] = useState(initial?.min_budget ?? "");
  const [maxBudget, setMaxBudget] = useState(initial?.max_budget ?? "");
  const [annualRevenue, setAnnualRevenue] = useState(initial?.annual_revenue ?? "");
  const [certifications, setCertifications] = useState(
    (initial?.certifications ?? []).join(", "),
  );
  const [locations, setLocations] = useState((initial?.locations ?? []).join(", "));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      await saveProvider({
        description: description.trim(),
        cpv_codes: toList(cpvCodes),
        min_budget: toDecimal(minBudget),
        max_budget: toDecimal(maxBudget),
        annual_revenue: toDecimal(annualRevenue),
        certifications: toList(certifications),
        locations: toList(locations),
      });
      // Only on a first run, and only once: with tenders already ingested, re-downloading
      // three monthly archives would cost minutes to upsert rows that are already there.
      if (corpusIsEmpty) await triggerBackfill();
      router.push("/");
      router.refresh();
    } catch {
      setError(
        "No se pudo guardar el perfil. Comprueba que la API está levantada y vuelve a intentarlo.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Card as="section" className="space-y-5 p-5 sm:p-6">
        <Field
          label="A qué se dedica tu empresa"
          hint="El texto que se compara con el título de cada licitación, por palabras y por significado. Descríbelo como describirías el trabajo, no como un eslogan: los términos concretos (tecnologías, tipo de servicio, sector) son los que encuentran licitaciones."
          htmlFor="description"
        >
          <textarea
            id="description"
            required
            rows={5}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Desarrollamos aplicaciones web a medida y mantenemos portales institucionales para el sector público…"
            className={INPUT_CLASS}
          />
        </Field>

        <Field
          label="Tus códigos CPV"
          hint="Filtro duro: una licitación tiene que compartir al menos uno contigo para llegar al ranking. Separados por comas. Compass v1 sólo ingiere la división 72 (servicios informáticos), así que códigos de otras divisiones no encontrarán nada."
          htmlFor="cpv"
        >
          <input
            id="cpv"
            required
            value={cpvCodes}
            onChange={(event) => setCpvCodes(event.target.value)}
            placeholder="72200000, 72262000, 72400000"
            className={`${INPUT_CLASS} font-mono`}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Importe mínimo (€)"
            hint="Filtro duro. En blanco, sin mínimo."
            htmlFor="min-budget"
          >
            <input
              id="min-budget"
              inputMode="decimal"
              value={minBudget}
              onChange={(event) => setMinBudget(event.target.value)}
              placeholder="10000"
              className={`${INPUT_CLASS} tabular`}
            />
          </Field>
          <Field
            label="Importe máximo (€)"
            hint="Filtro duro. Una licitación sin importe publicado queda fuera si pones cualquiera de los dos."
            htmlFor="max-budget"
          >
            <input
              id="max-budget"
              inputMode="decimal"
              value={maxBudget}
              onChange={(event) => setMaxBudget(event.target.value)}
              placeholder="200000"
              className={`${INPUT_CLASS} tabular`}
            />
          </Field>
        </div>

        <Field
          label="Facturación anual (€)"
          hint="No filtra nada: se usa en el veredicto. Si un pliego exige una cifra de negocio mínima superior a ésta, el veredicto es NO APTO con la cláusula citada. En blanco, esa exigencia sale como reserva en vez de como bloqueo."
          htmlFor="revenue"
        >
          <input
            id="revenue"
            inputMode="decimal"
            value={annualRevenue}
            onChange={(event) => setAnnualRevenue(event.target.value)}
            placeholder="450000"
            className={`${INPUT_CLASS} tabular`}
          />
        </Field>

        <Field
          label="Certificaciones que tienes"
          hint="También para el veredicto: una certificación exigida que no declares bloquea la candidatura. Escríbelas como vengan en el certificado; la comparación tolera variantes (ISO 27001 encaja con ISO/IEC 27001:2013)."
          htmlFor="certifications"
        >
          <input
            id="certifications"
            value={certifications}
            onChange={(event) => setCertifications(event.target.value)}
            placeholder="ENS, ISO 27001"
            className={INPUT_CLASS}
          />
        </Field>

        <Field
          label="Ámbito geográfico"
          hint="Filtro duro sobre el lugar de ejecución. En blanco, sin restricción — que suele ser lo que quieres al empezar."
          htmlFor="locations"
        >
          <input
            id="locations"
            value={locations}
            onChange={(event) => setLocations(event.target.value)}
            placeholder="Asturias, Madrid"
            className={INPUT_CLASS}
          />
        </Field>
      </Card>

      {error !== null ? (
        <p
          role="alert"
          className="rounded-sm border border-verdict-fail/40 bg-verdict-fail-soft px-3 py-2 text-sm text-verdict-fail"
        >
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={isSaving}>
          {isSaving ? "Guardando…" : "Guardar perfil"}
        </Button>
        {corpusIsEmpty ? (
          <p className="text-xs leading-relaxed text-muted">
            Al guardar se descargarán los últimos tres meses de licitaciones de PLACSP.
            Tarda unos minutos y podrás seguir el avance en la portada.
          </p>
        ) : null}
      </div>
    </form>
  );
}
