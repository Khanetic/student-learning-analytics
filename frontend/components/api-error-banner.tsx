"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ApiError } from "@/lib/api";

export function ApiErrorBanner({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const unreachable = error.status === 0;
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm sm:flex-row sm:items-center">
      <AlertTriangle className="h-5 w-5 shrink-0 text-danger" />
      <div className="flex-1">
        <p className="font-medium text-danger">
          {unreachable ? "Backend API is unreachable" : "Something went wrong"}
        </p>
        <p className="text-muted-foreground">{error.message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" /> Retry
        </Button>
      )}
    </div>
  );
}
