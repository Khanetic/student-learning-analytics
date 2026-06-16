import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />
  );
}

// Convenience: a card-shaped chart placeholder used while data loads.
export function ChartSkeleton({ height = 280 }: { height?: number }) {
  return <Skeleton style={{ height }} className="w-full" />;
}
