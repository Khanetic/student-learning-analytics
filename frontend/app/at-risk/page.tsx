"use client";

import { Download, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ApiErrorBanner } from "@/components/api-error-banner";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { Student } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { downloadCsv, toCsv } from "@/lib/utils";

export default function AtRiskPage() {
  const { data, error, loading, reload } = useApi(() => api.listAtRisk());
  const [bulk, setBulk] = useState<{ running: boolean; done: number; total: number }>({
    running: false,
    done: 0,
    total: 0,
  });

  async function generateAll(students: Student[]) {
    setBulk({ running: true, done: 0, total: students.length });
    for (let i = 0; i < students.length; i++) {
      try {
        const fb = await api.getFeedback(students[i].student_id);
        await api.logFeedback(students[i].student_id, {
          channel: "manual",
          status: "sent",
          feedback_text: fb.feedback,
        });
      } catch {
        /* keep going; per-student failures shouldn't abort the batch */
      }
      setBulk((b) => ({ ...b, done: i + 1 }));
    }
    setBulk((b) => ({ ...b, running: false }));
  }

  function exportCsv(students: Student[]) {
    const rows = students.map((s) => ({
      student_id: s.student_id,
      name: s.name,
      program: s.program,
      engagement_score: s.indicators?.engagement_score ?? "",
      quiz_trend: s.indicators?.quiz_trend ?? "",
      submission_rate: s.indicators?.submission_rate ?? "",
    }));
    downloadCsv("at-risk-students.csv", toCsv(rows));
  }

  if (error) {
    return (
      <>
        <PageHeader title="At-Risk Students" />
        <ApiErrorBanner error={error} onRetry={reload} />
      </>
    );
  }

  const students = data ?? [];

  return (
    <>
      <PageHeader
        title="At-Risk Students"
        subtitle="Low engagement and a negative quiz trend. Prioritize outreach here."
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Button onClick={() => generateAll(students)} disabled={bulk.running || students.length === 0}>
          {bulk.running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          Generate Feedback for All
        </Button>
        <Button variant="outline" onClick={() => exportCsv(students)} disabled={students.length === 0}>
          <Download className="h-4 w-4" /> Export CSV
        </Button>
        {bulk.running && (
          <span className="text-sm text-muted-foreground">
            {bulk.done}/{bulk.total} processed…
          </span>
        )}
        {!bulk.running && bulk.total > 0 && (
          <span className="text-sm text-success">Done — {bulk.total} feedback(s) generated.</span>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : students.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No at-risk students. 🎉
            </p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Program</TH>
                  <TH>Engagement</TH>
                  <TH>Quiz Trend</TH>
                  <TH>Submission</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {students.map((s) => (
                  <TR key={s.student_id}>
                    <TD className="font-medium">{s.name}</TD>
                    <TD className="text-muted-foreground">{s.program}</TD>
                    <TD>{s.indicators?.engagement_score.toFixed(1)}</TD>
                    <TD>
                      <Badge variant="danger">{s.indicators?.quiz_trend}</Badge>
                    </TD>
                    <TD>{s.indicators?.submission_rate.toFixed(0)}%</TD>
                    <TD>
                      <Link
                        href={`/students/${s.student_id}`}
                        className="text-sm text-primary hover:underline"
                      >
                        View
                      </Link>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}
