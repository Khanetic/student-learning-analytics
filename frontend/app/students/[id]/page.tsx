"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { ApiErrorBanner } from "@/components/api-error-banner";
import { IndicatorRadar } from "@/components/charts/indicator-radar";
import { QuizTrendLine } from "@/components/charts/quiz-trend-line";
import { SessionHeatmap } from "@/components/charts/session-heatmap";
import { FeedbackPanel } from "@/components/feedback-panel";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartSkeleton, Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export default function StudentDetailPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const student = useApi(() => api.getStudent(id), [id]);
  const quizzes = useApi(() => api.getQuizAttempts(id), [id]);
  const sessions = useApi(() => api.getSessions(id), [id]);

  if (student.error) {
    return (
      <>
        <BackLink />
        <ApiErrorBanner error={student.error} onRetry={student.reload} />
      </>
    );
  }

  const s = student.data;
  const ind = s?.indicators;

  return (
    <>
      <BackLink />
      {student.loading || !s ? (
        <Skeleton className="mb-6 h-9 w-64" />
      ) : (
        <PageHeader title={s.name} subtitle={`${s.program} · ${s.student_id}`} />
      )}

      {ind && (
        <div className="mb-4 flex flex-wrap gap-2">
          <Badge variant={ind.at_risk_flag ? "danger" : "success"}>
            {ind.at_risk_flag ? "At-Risk" : "Healthy"}
          </Badge>
          <Badge variant="muted">Engagement {ind.engagement_score.toFixed(1)}</Badge>
          <Badge variant="muted">Quiz trend: {ind.quiz_trend}</Badge>
          <Badge variant="muted">{ind.time_on_task_hours.toFixed(1)} h/wk</Badge>
          <Badge variant="muted">Submission {ind.submission_rate.toFixed(0)}%</Badge>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Indicator Profile</CardTitle>
          </CardHeader>
          <CardContent>
            {student.loading ? (
              <ChartSkeleton height={300} />
            ) : ind ? (
              <IndicatorRadar indicators={ind} />
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No indicators computed for this student.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quiz Score Trend</CardTitle>
          </CardHeader>
          <CardContent>
            {quizzes.loading ? (
              <ChartSkeleton />
            ) : quizzes.error ? (
              <ApiErrorBanner error={quizzes.error} onRetry={quizzes.reload} />
            ) : (
              <QuizTrendLine attempts={quizzes.data ?? []} />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>Session Activity (day × hour)</CardTitle>
          </CardHeader>
          <CardContent>
            {sessions.loading ? (
              <ChartSkeleton height={180} />
            ) : sessions.error ? (
              <ApiErrorBanner error={sessions.error} onRetry={sessions.reload} />
            ) : (
              <SessionHeatmap sessions={sessions.data ?? []} />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4">
        <FeedbackPanel studentId={id} />
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/students"
      className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" /> Back to students
    </Link>
  );
}
