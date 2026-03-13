"use client";

import {
  type InputHTMLAttributes,
  forwardRef,
  useState,
} from "react";
import { Eye, EyeOff } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  togglePassword?: boolean;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, type, togglePassword, ...props }, ref) => {
    const [showPassword, setShowPassword] = useState(false);

    const isPassword = type === "password";
    const resolvedType =
      isPassword && togglePassword && showPassword ? "text" : type;

    return (
      <div className="space-y-1.5">
        {label && (
          <label className="block text-sm font-medium text-aide-text-secondary">
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            type={resolvedType}
            className={cn(
              "w-full h-10 rounded-lg border bg-aide-bg-secondary px-3 py-2 text-sm text-aide-text-primary placeholder-aide-text-muted outline-none transition-all focus-visible:ring-2 focus-visible:ring-aide-accent-blue/25 input-focus-ring",
              error
                ? "border-aide-accent-red focus:border-aide-accent-red"
                : "border-aide-border focus:border-aide-border-focus",
              isPassword && togglePassword && "pr-10",
              className
            )}
            {...props}
          />
          {isPassword && togglePassword && (
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-aide-text-muted transition-colors hover:text-aide-text-secondary"
              tabIndex={-1}
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
        {error && (
          <p className="text-xs text-aide-accent-red">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
