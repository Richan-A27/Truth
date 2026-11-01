import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary";
}

export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-medium transition-all duration-200 hover:-translate-y-0.5 disabled:opacity-50 disabled:pointer-events-none disabled:translate-y-0";
  const variants = {
    primary: "bg-accent text-white hover:bg-accent-hover",
    secondary: "bg-transparent text-ink border border-border hover:bg-bg-alt",
  };

  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />;
}
