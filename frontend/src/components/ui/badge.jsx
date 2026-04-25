import * as React from "react";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-sm border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-veridian focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-veridian-subtle text-veridian",
        secondary: "border-transparent bg-surface-overlay text-text-secondary",
        outline: "text-text-secondary border-border",
        success: "border-transparent bg-semantic-success-bg text-semantic-success",
        warning: "border-transparent bg-semantic-warning-bg text-semantic-warning",
        error: "border-transparent bg-semantic-error-bg text-semantic-error",
        // Method badges for scoring transparency
        method_llm: "border-veridian text-veridian bg-veridian/5",
        method_cosine: "border-text-muted text-text-secondary bg-surface-overlay",
        method_whisper: "border-semantic-warning text-semantic-warning bg-semantic-warning/10",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Badge({ className, variant, ...props }) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
