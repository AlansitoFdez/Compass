import { Skeleton } from "@/components/ui/Skeleton";

/** Shown while a tender page waits on the API for the tender and its analysis. */
export default function Loading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-8 w-full max-w-2xl" />
      <Skeleton className="h-4 w-64" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-32 w-full" />
      <span className="sr-only" role="status">
        Cargando la licitación
      </span>
    </div>
  );
}
