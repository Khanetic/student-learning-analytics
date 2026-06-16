import * as React from "react";

import { cn } from "@/lib/utils";

type Variant = "default" | "danger" | "success" | "muted";

const styles: Record<Variant, string> = {
  default: "bg-primary/10 text-primary",
  danger: "bg-danger/15 text-danger",
  success: "bg-success/15 text-success",
  muted: "bg-muted text-muted-foreground",
};

export function Badge({
  variant = "default",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        styles[variant],
        className
      )}
      {...props}
    />
  );
}
