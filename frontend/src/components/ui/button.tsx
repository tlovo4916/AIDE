import { type ButtonHTMLAttributes, forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

const VARIANT_STYLES = {
  primary:
    "bg-aide-accent-blue text-white btn-primary-glow hover:bg-aide-accent-blue/90 focus-visible:ring-aide-accent-blue/50",
  secondary:
    "bg-aide-bg-tertiary text-aide-text-primary border border-aide-border hover:bg-aide-bg-elevated focus-visible:ring-aide-border",
  danger:
    "bg-aide-accent-red text-white hover:bg-aide-accent-red/90 focus-visible:ring-aide-accent-red/50",
  ghost:
    "text-aide-text-secondary hover:bg-aide-bg-tertiary hover:text-aide-text-primary focus-visible:ring-aide-border",
  outline:
    "border border-aide-border bg-aide-bg-secondary text-aide-text-primary hover:bg-aide-bg-tertiary focus-visible:ring-aide-border",
  success:
    "bg-aide-accent-green text-white hover:bg-aide-accent-green/90 focus-visible:ring-aide-accent-green/50",
  link:
    "text-aide-accent-blue underline-offset-4 hover:underline p-0 h-auto focus-visible:ring-aide-accent-blue/50",
} as const;

const SIZE_STYLES = {
  sm: "h-8 rounded-lg px-3 text-xs gap-1.5",
  md: "h-10 rounded-lg px-4 text-sm gap-2",
  lg: "h-11 rounded-lg px-6 text-sm gap-2",
} as const;

type ButtonVariant = keyof typeof VARIANT_STYLES;
type ButtonSize = keyof typeof SIZE_STYLES;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-aide-bg-primary disabled:pointer-events-none disabled:opacity-50",
        VARIANT_STYLES[variant],
        SIZE_STYLES[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
      {children}
    </button>
  )
);
Button.displayName = "Button";

export { Button };
export type { ButtonVariant, ButtonSize };
