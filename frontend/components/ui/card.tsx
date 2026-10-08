import * as React from "react";
import { cn } from "@/lib/utils";

/** Dense bordered panel with an optional header row (title + actions). */
export function Panel({
  title,
  subtitle,
  actions,
  className,
  bodyClassName,
  children,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("rounded-lg border border-border bg-surface", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
          <div className="min-w-0">
            {title && <h3 className="truncate text-[12px] font-semibold uppercase tracking-wide text-foreground/90">{title}</h3>}
            {subtitle && <p className="text-[11px] text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-3", bodyClassName)}>{children}</div>
    </section>
  );
}
