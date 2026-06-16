"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { Feedback } from "@/lib/types";

export function FeedbackPanel({ studentId }: { studentId: string }) {
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setFeedback(await api.getFeedback(studentId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to generate feedback.");
    } finally {
      setLoading(false);
    }
  }

  const paragraphs = feedback
    ? feedback.feedback.split("\n\n").filter((p) => p.trim())
    : [];

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <Sparkles className="h-4 w-4 text-accent" /> AI Feedback
        </CardTitle>
        {feedback && <Badge variant="muted">via {feedback.provider}</Badge>}
      </CardHeader>
      <CardContent className="space-y-4">
        {!feedback && !loading && (
          <p className="text-sm text-muted-foreground">
            Generate personalized, pedagogy-grounded feedback for this student.
          </p>
        )}

        {loading && (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Generating feedback via the RAG pipeline…
          </div>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}

        {paragraphs.length > 0 && (
          <div className="space-y-3 text-sm leading-relaxed">
            {paragraphs.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        )}

        {feedback && feedback.context.length > 0 && (
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">
              Grounded in {feedback.context.length} pedagogy source(s)
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-4">
              {feedback.context.map((c, i) => (
                <li key={i}>
                  <span className="font-medium text-foreground">{c.title}</span> — {c.source}
                </li>
              ))}
            </ul>
          </details>
        )}

        <Button onClick={generate} disabled={loading}>
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {feedback ? "Regenerate" : "Generate Feedback"}
        </Button>
      </CardContent>
    </Card>
  );
}
