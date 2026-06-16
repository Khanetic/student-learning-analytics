// Mirrors src/sla/api/schemas.py — keep in sync with the FastAPI contract.

export interface Indicators {
  engagement_score: number;
  time_on_task_hours: number;
  quiz_trend: "positive" | "negative" | "flat";
  quiz_trend_slope: number;
  session_regularity: number;
  submission_rate: number;
  at_risk_flag: boolean;
  computed_at: string;
}

export interface Student {
  student_id: string;
  name: string;
  program: string;
  enrollment_date: string;
  indicators: Indicators | null;
}

export interface QuizAttempt {
  quiz_id: string;
  attempt_number: number;
  score: number;
  submitted_at: string;
}

export interface SessionActivity {
  login_at: string;
  duration_minutes: number;
  device_type: string;
}

export interface RetrievedContext {
  title: string;
  source: string;
  text: string;
}

export interface Feedback {
  student_id: string;
  feedback: string;
  provider: string;
  context: RetrievedContext[];
}

export interface Health {
  status: string;
  database: boolean;
  vector_store: boolean;
  llm_provider: string;
}
