"use client";

import * as React from "react";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

const base =
  "h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground placeholder:text-muted/60 focus:border-accent focus:outline-none disabled:opacity-50";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(base, "num", className)} {...props} />,
);
Input.displayName = "Input";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select ref={ref} className={cn(base, "pr-6", className)} {...props}>
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(base, "h-auto py-2 font-mono", className)} {...props} />;
}

export function Switch({ checked, onCheckedChange, id }: { checked: boolean; onCheckedChange: (v: boolean) => void; id?: string }) {
  return (
    <SwitchPrimitive.Root
      id={id}
      checked={checked}
      onCheckedChange={onCheckedChange}
      className="relative h-4.5 w-8 shrink-0 rounded-full border border-border bg-background transition-colors data-[state=checked]:border-accent data-[state=checked]:bg-accent/30"
    >
      <SwitchPrimitive.Thumb className="block h-3 w-3 translate-x-0.5 rounded-full bg-muted transition-transform data-[state=checked]:translate-x-4 data-[state=checked]:bg-accent" />
    </SwitchPrimitive.Root>
  );
}

/** Label + control + optional hint, used by every form. */
export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: React.ReactNode;
  hint?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("flex min-w-0 flex-col gap-1", className)}>
      <span className="text-[11px] text-muted">{label}</span>
      {children}
      {hint && <span className="text-[10.5px] leading-tight text-muted/80">{hint}</span>}
    </label>
  );
}

/** Numeric input that keeps a string draft so users can type "-", "1." etc. Emits numbers (or null when empty). */
export function NumberField({
  label,
  value,
  onChange,
  step,
  min,
  max,
  hint,
  nullable = false,
  className,
}: {
  label: React.ReactNode;
  value: number | null;
  onChange: (v: number | null) => void;
  step?: number;
  min?: number;
  max?: number;
  hint?: React.ReactNode;
  nullable?: boolean;
  className?: string;
}) {
  return (
    <Field label={label} hint={hint} className={className}>
      <Input
        type="number"
        value={value ?? ""}
        step={step}
        min={min}
        max={max}
        placeholder={nullable ? "none" : undefined}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") return onChange(nullable ? null : (min ?? 0));
          const n = Number(raw);
          if (Number.isFinite(n)) onChange(n);
        }}
      />
    </Field>
  );
}

export function ToggleField({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-2 py-1.5">
      <div className="min-w-0">
        <div className="text-[12px]">{label}</div>
        {hint && <div className="text-[10.5px] text-muted">{hint}</div>}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
