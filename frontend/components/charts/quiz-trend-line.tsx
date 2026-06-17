"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { QuizAttempt } from "@/lib/types";

export function QuizTrendLine({ attempts }: { attempts: QuizAttempt[] }) {
  if (attempts.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">No quiz attempts.</p>;
  }
  const data = attempts.map((a, i) => ({
    label: `#${i + 1}`,
    score: a.score,
    quiz: a.quiz_id,
    date: new Date(a.submitted_at).toLocaleDateString(),
  }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
        <YAxis domain={[0, 100]} stroke="hsl(var(--muted-foreground))" fontSize={11} />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Line
          type="monotone"
          dataKey="score"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          dot={{ r: 3 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
