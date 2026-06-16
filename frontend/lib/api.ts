// Typed client for the FastAPI backend. All calls run in the browser, so the
// base URL must be reachable from the user's machine (the host-published port),
// configured via NEXT_PUBLIC_API_URL.

import type {
  Feedback,
  Health,
  QuizAttempt,
  SessionActivity,
  Student,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8001";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch (e) {
    // Network failure / API unreachable.
    throw new ApiError(
      `Cannot reach the API at ${API_URL}. Is the backend running?`,
      0
    );
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new ApiError(detail, resp.status);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  listStudents: () => request<Student[]>("/students"),
  listAtRisk: () => request<Student[]>("/students/at-risk"),
  getStudent: (id: string) => request<Student>(`/students/${id}`),
  getQuizAttempts: (id: string) =>
    request<QuizAttempt[]>(`/students/${id}/quiz-attempts`),
  getSessions: (id: string) =>
    request<SessionActivity[]>(`/students/${id}/sessions`),
  getFeedback: (id: string) => request<Feedback>(`/students/${id}/feedback`),
  logFeedback: (
    id: string,
    body: { channel?: string; status: string; feedback_text?: string; note?: string }
  ) =>
    request(`/students/${id}/feedback/log`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
