import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { Indicators } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Reference caps used to scale unbounded indicators onto a 0–100 axis for the
// radar chart. Mirrors the tunables in src/sla/indicators/compute.py.
const TIME_ON_TASK_CAP_HOURS = 10; // ~hours/week considered "full"
const REGULARITY_CAP_DAYS = 7; // std-dev of login gaps; lower is better

export interface RadarPoint {
  indicator: string;
  value: number; // 0–100, higher is always "better"
}

// Normalize all six indicators to a 0–100 scale where higher == healthier, so
// they can share one radar chart. session_regularity is inverted (low std-dev
// of login gaps == more regular == better).
export function normalizeIndicators(ind: Indicators): RadarPoint[] {
  const clamp = (n: number) => Math.max(0, Math.min(100, n));
  const trendScore =
    ind.quiz_trend === "positive" ? 100 : ind.quiz_trend === "flat" ? 50 : 0;
  const regularityScore = clamp(
    100 - (ind.session_regularity / REGULARITY_CAP_DAYS) * 100
  );
  const timeScore = clamp((ind.time_on_task_hours / TIME_ON_TASK_CAP_HOURS) * 100);

  return [
    { indicator: "Engagement", value: clamp(ind.engagement_score) },
    { indicator: "Time on Task", value: timeScore },
    { indicator: "Quiz Trend", value: trendScore },
    { indicator: "Regularity", value: regularityScore },
    { indicator: "Submission", value: clamp(ind.submission_rate) },
    { indicator: "On Track", value: ind.at_risk_flag ? 20 : 90 },
  ];
}

export function toCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return "";
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    headers.join(","),
    ...rows.map((r) => headers.map((h) => escape(r[h])).join(",")),
  ];
  return lines.join("\n");
}

export function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
