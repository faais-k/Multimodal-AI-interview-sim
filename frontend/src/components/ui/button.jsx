import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm font-medium transition-all duration-fast ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ascent-blue focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-ascent-blue text-white hover:bg-ascent-blue-hover hover:-translate-y-px active:scale-[0.98]",
        secondary: "bg-surface-overlay text-text-primary border border-border hover:border-border-strong hover:bg-white",
        outline: "border border-border bg-transparent hover:bg-surface-overlay hover:text-text-primary",
        ghost: "hover:bg-surface-overlay hover:text-text-primary",
        link: "text-ascent-blue underline-offset-4 hover:underline",
        destructive: "bg-semantic-error text-white hover:bg-red-700",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-12 px-8 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props}
    />
  );
});
Button.displayName = "Button";

export { Button, buttonVariants };
