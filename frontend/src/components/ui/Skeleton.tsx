/**
 * A placeholder block for content that is still loading.
 *
 * Every route renders against the live API (`force-dynamic`), so navigation waits on a
 * real request -- without these the screen simply froze on the previous page with no
 * signal that anything was happening.
 */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-sm bg-surface-muted ${className}`}
      aria-hidden="true"
    />
  );
}
