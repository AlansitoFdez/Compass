import type { ReactNode } from "react";

/**
 * The app's one raised surface.
 *
 * Exists so "a bordered box on --surface" is defined once instead of being retyped with
 * slightly different padding and radius in each screen, which is what flattens a layout:
 * when every block is a card with the same edge, nothing reads as more important than
 * anything else.
 */
export function Card({
  children,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "li" | "article";
}) {
  return (
    <Tag
      className={`rounded-md border border-border bg-surface shadow-raised ${className}`}
    >
      {children}
    </Tag>
  );
}
