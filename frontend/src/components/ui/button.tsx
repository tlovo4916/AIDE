import { type ButtonHTMLAttributes, forwardRef } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

const VARIANT_STYLES = {
  primary:
    "bg-aide-accent-blue text-white hover:bg-aide-accent-blue/90 focus-visible:ring-aide-accent-blue/50",
  secondary:
    "bg-aide-bg-tertiary text-aide-text-primary border border-aide-border hover:bg-aide-bg-elevated focus-visible:ring-aide-border",
  danger:
    "bg-aide-accent-red text-white hover:bg-aide-accent-red/90 focus-visible:ring-aide-accent-red/50",
  ghost:
    "text-aide-text-secondary hover:bg-aide-bg-tertiary hover:text-aide-text-primary focus-visible:ring-aide-border",
} as const;

const SIZE_STYLES = {
  sm: "h-8 rounded-md px-3 text-xs gap-1.5",
  md: "h-9 rounded-md px-4 text-sm gap-2",
  lg: "h-10 rounded-md px-5 text-sm gap-2",
} as const;

type ButtonVariant = keyof typeof VARIANT_STYLES;
type ButtonSize = keyof typeof SIZE_STYLES;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-aide-bg-primary disabled:pointer-events-none disabled:opacity-50",
        VARIANT_STYLES[variant],
        SIZE_STYLES[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";

export { Button };
export type { ButtonVariant, ButtonSize };
