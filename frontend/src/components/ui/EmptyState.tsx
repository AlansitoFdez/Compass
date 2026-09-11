import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";

/** Nothing to show, with the reason -- never a bare "no results". */
export function EmptyState({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <Card className="px-6 py-10 text-center">
      <p className="text-base font-medium">{title}</p>
      {children ? (
        <div className="mx-auto mt-2 max-w-prose text-sm text-muted">{children}</div>
      ) : null}
    </Card>
  );
}
