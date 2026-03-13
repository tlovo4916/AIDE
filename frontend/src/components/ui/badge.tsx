import { type HTMLAttributes, forwardRef } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

const VARIANT_STYLES = {
  default:
    "border-aide-border bg-aide-bg-tertiary text-aide-text-secondary",
  phase:
    "border-aide-accent-blue/30 bg-aide-accent-blue/10 text-aide-accent-blue",
  success:
    "border-aide-accent-green/30 bg-aide-accent-green/10 text-aide-accent-green",
  warning:
    "border-aide-accent-amber/30 bg-aide-accent-amber/10 text-aide-accent-amber",
  danger:
    "border-aide-accent-red/30 bg-aide-accent-red/10 text-aide-accent-red",
  agent:
    "border-aide-accent-blue/30 bg-aide-accent-blue/10 text-aide-accent-blue",
} as const;

type BadgeVariant = keyof typeof VARIANT_STYLES;

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        VARIANT_STYLES[variant],
        className
      )}
      {...props}
    />
  )
);
Badge.displayName = "Badge";

export { Badge };
export type { BadgeVariant };
