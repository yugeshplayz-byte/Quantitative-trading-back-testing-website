"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";
import * as React from "react";

export function Tip({ content, children }: { content: React.ReactNode; children?: React.ReactNode }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>
        {children ? (
          <span className="cursor-help">{children}</span>
        ) : (
          <span className="inline-flex cursor-help text-muted hover:text-foreground">
            <Info size={12} />
          </span>
        )}
      </TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className="z-50 max-w-xs rounded-md border border-border bg-surface-2 px-2.5 py-1.5 text-[11px] leading-snug text-foreground shadow-lg"
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
