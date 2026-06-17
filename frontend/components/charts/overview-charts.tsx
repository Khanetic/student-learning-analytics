"use client";

import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Student } from "@/lib/types";

const AXIS = "hsl(var(--muted-foreground))";
const tooltipStyle = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  color: "hsl(var(--card-foreground))",
  fontSize: 12,
};

function withIndicators(students: Student[]) {
  return students.filter((s) => s.indicators !== null);
}

export function EngagementHistogram({ students }: { students: Student[] }) {
  // Bucket engagement scores into 0–10, 10–20, … 90–100.
  const buckets = Array.from({ length: 10 }, (_, i) => ({
    range: `${i * 10}-${i * 10 + 10}`,
    count: 0,
  }));
  for (const s of withIndicators(students)) {
    const idx = Math.min(9, Math.floor(s.indicators!.engagement_score / 10));
    buckets[idx].count += 1;
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Engagement Score Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={buckets}>
            <XAxis dataKey="range" stroke={AXIS} fontSize={11} />
            <YAxis allowDecimals={false} stroke={AXIS} fontSize={11} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))" }} />
            <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function AtRiskDonut({ students }: { students: Student[] }) {
  const ind = withIndicators(students);
  const atRisk = ind.filter((s) => s.indicators!.at_risk_flag).length;
  const data = [
    { name: "Healthy", value: ind.length - atRisk, color: "hsl(var(--success))" },
    { name: "At-Risk", value: atRisk, color: "hsl(var(--danger))" },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>At-Risk vs Healthy</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="mt-2 flex justify-center gap-4 text-xs text-muted-foreground">
          {data.map((d) => (
            <span key={d.name} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
              {d.name} ({d.value})
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function QuizTrendBar({ students }: { students: Student[] }) {
  const counts = { positive: 0, flat: 0, negative: 0 };
  for (const s of withIndicators(students)) counts[s.indicators!.quiz_trend] += 1;
  const data = [
    { trend: "Positive", count: counts.positive, color: "hsl(var(--success))" },
    { trend: "Flat", count: counts.flat, color: "hsl(var(--muted-foreground))" },
    { trend: "Negative", count: counts.negative, color: "hsl(var(--danger))" },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Quiz Trend Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data}>
            <XAxis dataKey="trend" stroke={AXIS} fontSize={11} />
            <YAxis allowDecimals={false} stroke={AXIS} fontSize={11} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))" }} />
            <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.trend} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
