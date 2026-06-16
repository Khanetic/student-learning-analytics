"use client";

import type { SessionActivity } from "@/lib/types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Day-of-week × hour-of-day login heatmap. Built with CSS grid (no chart lib
// needed) so it stays crisp and responsive.
export function SessionHeatmap({ sessions }: { sessions: SessionActivity[] }) {
  if (sessions.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">No sessions.</p>;
  }
  // grid[day][hour] = count. JS getDay(): 0=Sun..6=Sat → remap to Mon-first.
  const grid = Array.from({ length: 7 }, () => new Array(24).fill(0));
  let max = 0;
  for (const s of sessions) {
    const d = new Date(s.login_at);
    const day = (d.getDay() + 6) % 7;
    const hour = d.getHours();
    grid[day][hour] += 1;
    max = Math.max(max, grid[day][hour]);
  }

  const cell = (count: number) => {
    if (count === 0) return "hsl(var(--muted))";
    const intensity = 0.25 + 0.75 * (count / max);
    return `hsl(var(--primary) / ${intensity})`;
  };

  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-[3px]" style={{ gridTemplateColumns: "auto repeat(24, 1fr)" }}>
        <div />
        {Array.from({ length: 24 }, (_, h) => (
          <div key={h} className="text-center text-[9px] text-muted-foreground">
            {h % 6 === 0 ? h : ""}
          </div>
        ))}
        {grid.map((row, day) => (
          <div key={day} className="contents">
            <div className="pr-2 text-right text-[10px] leading-4 text-muted-foreground">
              {DAYS[day]}
            </div>
            {row.map((count, hour) => (
              <div
                key={hour}
                title={`${DAYS[day]} ${hour}:00 — ${count} session(s)`}
                className="h-4 w-full rounded-[2px]"
                style={{ background: cell(count) }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
