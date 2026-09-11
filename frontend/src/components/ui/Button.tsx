"use client";

import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "quiet";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-strong disabled:opacity-60 disabled:hover:bg-accent",
  quiet:
    "border border-border bg-surface text-foreground hover:border-accent disabled:opacity-60",
};

/** A button that looks interactive and stays legible while disabled. */
export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`rounded-sm px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
    />
  );
}
