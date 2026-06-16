"use client";

import { ArrowUpDown, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { ApiErrorBanner } from "@/components/api-error-banner";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { Student } from "@/lib/types";
import { useApi } from "@/lib/use-api";

type SortKey = "name" | "engagement" | "submission";

export default function StudentsPage() {
  const { data, error, loading, reload } = useApi(() => api.listStudents());
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [riskOnly, setRiskOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("engagement");
  const [asc, setAsc] = useState(false);

  const rows = useMemo(() => {
    let list = data ?? [];
    if (query) list = list.filter((s) => s.name.toLowerCase().includes(query.toLowerCase()));
    if (riskOnly) list = list.filter((s) => s.indicators?.at_risk_flag);
    const val = (s: Student) =>
      sortKey === "name"
        ? s.name
        : sortKey === "engagement"
          ? (s.indicators?.engagement_score ?? -1)
          : (s.indicators?.submission_rate ?? -1);
    return [...list].sort((a, b) => {
      const av = val(a);
      const bv = val(b);
      const cmp = typeof av === "string" ? av.localeCompare(bv as string) : (av as number) - (bv as number);
      return asc ? cmp : -cmp;
    });
  }, [data, query, riskOnly, sortKey, asc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(key === "name");
    }
  }

  if (error) {
    return (
      <>
        <PageHeader title="Students" />
        <ApiErrorBanner error={error} onRetry={reload} />
      </>
    );
  }

  return (
    <>
      <PageHeader title="Students" subtitle="Sort and filter the full cohort." />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name…"
            className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none focus:border-primary"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={riskOnly}
            onChange={(e) => setRiskOnly(e.target.checked)}
            className="h-4 w-4 accent-[hsl(var(--danger))]"
          />
          At-risk only
        </label>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <SortableTH label="Name" onClick={() => toggleSort("name")} />
                  <TH>Program</TH>
                  <SortableTH label="Engagement" onClick={() => toggleSort("engagement")} />
                  <TH>Quiz Trend</TH>
                  <SortableTH label="Submission" onClick={() => toggleSort("submission")} />
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {rows.map((s) => (
                  <TR
                    key={s.student_id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/students/${s.student_id}`)}
                  >
                    <TD className="font-medium">{s.name}</TD>
                    <TD className="text-muted-foreground">{s.program}</TD>
                    <TD>{s.indicators ? s.indicators.engagement_score.toFixed(1) : "—"}</TD>
                    <TD className="capitalize">{s.indicators?.quiz_trend ?? "—"}</TD>
                    <TD>{s.indicators ? `${s.indicators.submission_rate.toFixed(0)}%` : "—"}</TD>
                    <TD>
                      {s.indicators?.at_risk_flag ? (
                        <Badge variant="danger">At-Risk</Badge>
                      ) : s.indicators ? (
                        <Badge variant="success">Healthy</Badge>
                      ) : (
                        <Badge variant="muted">No data</Badge>
                      )}
                    </TD>
                  </TR>
                ))}
                {rows.length === 0 && (
                  <TR>
                    <TD className="py-8 text-center text-muted-foreground" colSpan={6}>
                      No students match your filters.
                    </TD>
                  </TR>
                )}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function SortableTH({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <TH>
      <button onClick={onClick} className="flex items-center gap-1 hover:text-foreground">
        {label}
        <ArrowUpDown className="h-3 w-3" />
      </button>
    </TH>
  );
}
