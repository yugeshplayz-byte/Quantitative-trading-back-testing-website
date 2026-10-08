import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide", {
  variants: {
    tone: {
      neutral: "bg-surface-2 text-muted border border-border",
      up: "bg-up/15 text-up",
      down: "bg-down/15 text-down",
      warn: "bg-warn/15 text-warn",
      accent: "bg-accent/15 text-accent",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export type Tone = "neutral" | "up" | "down" | "warn" | "accent";
export const severityTone = (s: string): Tone => (s === "high" || s === "bad" ? "down" : s === "medium" || s === "warn" ? "warn" : s === "good" ? "up" : "neutral");
