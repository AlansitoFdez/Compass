import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Shown while the matches page waits on the API.
 *
 * Every route is `force-dynamic`, so navigation always waits on a real request -- without
 * this the screen simply froze on whatever was there before, with no sign anything was
 * happening.
 */
export default function Loading() {
  return (
    <div>
      <Skeleton className="h-7 w-80" />
      <Skeleton className="mt-3 h-24 w-full" />
      <div className="mt-8 space-y-3">
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-40 w-full" />
        ))}
      </div>
      <span className="sr-only" role="status">
        Cargando las licitaciones que encajan con tu perfil
      </span>
    </div>
  );
}
