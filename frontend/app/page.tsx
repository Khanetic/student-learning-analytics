"use client";

import { AlertTriangle, CheckCircle2, TrendingUp, Users } from "lucide-react";

import { ApiErrorBanner } from "@/components/api-error-banner";
import {
  AtRiskDonut,
  EngagementHistogram,
  QuizTrendBar,
} from "@/components/charts/overview-charts";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { ChartSkeleton, Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export default function OverviewPage() {
  const { data: students, error, loading, reload } = useApi(() => api.listStudents());

  if (error) {
    return (
      <>
        <PageHeader title="Overview" />
        <ApiErrorBanner error={error} onRetry={reload} />
      </>
    );
  }

  const withInd = (students ?? []).filter((s) => s.indicators);
  const total = students?.length ?? 0;
  const avgEngagement = withInd.length
    ? withInd.reduce((a, s) => a + s.indicators!.engagement_score, 0) / withInd.length
    : 0;
  const avgSubmission = withInd.length
    ? withInd.reduce((a, s) => a + s.indicators!.submission_rate, 0) / withInd.length
    : 0;
  const atRisk = withInd.filter((s) => s.indicators!.at_risk_flag).length;

  return (
    <>
      <PageHeader title="Overview" subtitle="Cohort-wide learning indicators at a glance." />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="space-y-2 py-6">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <KpiCard title="Total Students" value={total} icon={Users} />
            <KpiCard
              title="Avg Engagement"
              value={avgEngagement.toFixed(1)}
              hint="0–100 composite"
              icon={TrendingUp}
            />
            <KpiCard
              title="At-Risk"
              value={atRisk}
              hint={total ? `${((atRisk / total) * 100).toFixed(0)}% of cohort` : ""}
              icon={AlertTriangle}
              accent="danger"
            />
            <KpiCard
              title="Avg Submission Rate"
              value={`${avgSubmission.toFixed(0)}%`}
              hint="on-time assignments"
              icon={CheckCircle2}
              accent="success"
            />
          </>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {loading ? (
          <>
            <ChartSkeleton />
            <ChartSkeleton />
          </>
        ) : (
          <>
            <EngagementHistogram students={students ?? []} />
            <AtRiskDonut students={students ?? []} />
          </>
        )}
      </div>

      <div className="mt-4">
        {loading ? <ChartSkeleton /> : <QuizTrendBar students={students ?? []} />}
      </div>
    </>
  );
}
