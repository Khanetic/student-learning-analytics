"""Generate personalized feedback from an indicator profile + retrieved context.

The real provider uses a LangChain prompt + OpenAI chat model to write the
message; the offline mock provider assembles an equivalent three-paragraph
message from a deterministic template. Both paths consume the same
``StudentProfile`` and retrieved chunks, so the API behaves identically with or
without an OpenAI key.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sla.rag.provider import ChatModel, get_chat, provider_name
from sla.rag.retrieve import RetrievedChunk

# LangChain prompt used by the real provider.
FEEDBACK_PROMPT_TEMPLATE = """You are a supportive learning coach for a university \
student. Using the student's learning indicators and the retrieved pedagogy \
guidance, write exactly three short paragraphs of personalized, encouraging \
feedback. Paragraph 1: acknowledge their current engagement and effort. \
Paragraph 2: interpret their quiz trend and study habits and give one concrete, \
actionable strategy drawn from the guidance. Paragraph 3: offer encouragement and \
a clear next step. Be specific, warm, and non-judgmental. Do not invent numbers.

Student profile:
{profile}

Retrieved pedagogy guidance:
{context}
"""


@dataclass
class StudentProfile:
    """The indicator profile fed into feedback generation."""

    student_id: str
    name: str
    program: str
    engagement_score: float
    time_on_task_hours: float
    quiz_trend: str
    quiz_trend_slope: float
    session_regularity: float
    submission_rate: float
    at_risk_flag: bool

    def to_text(self) -> str:
        """Render the profile as a compact human-readable block."""
        risk = "yes" if self.at_risk_flag else "no"
        return (
            f"- Name: {self.name} ({self.program})\n"
            f"- Engagement score: {self.engagement_score:.0f}/100\n"
            f"- Active learning time: {self.time_on_task_hours:.1f} hours/week\n"
            f"- Quiz trend: {self.quiz_trend} (slope {self.quiz_trend_slope:+.2f})\n"
            f"- Session regularity (std days between logins): {self.session_regularity:.1f}\n"
            f"- On-time submission rate: {self.submission_rate:.0f}%\n"
            f"- Flagged at risk: {risk}"
        )


@dataclass
class FeedbackResult:
    """Output of feedback generation."""

    feedback: str
    provider: str
    context: list[RetrievedChunk] = field(default_factory=list)


def build_profile_query(profile: StudentProfile) -> str:
    """Build a natural-language query used to retrieve relevant pedagogy."""
    parts: list[str] = []
    if profile.engagement_score < 40:
        parts.append("low engagement and motivation, at risk of disengaging")
    elif profile.engagement_score < 70:
        parts.append("moderate engagement that could be strengthened")
    else:
        parts.append("strong engagement to sustain")

    if profile.quiz_trend == "negative":
        parts.append("declining quiz scores and interpreting quiz feedback")
    elif profile.quiz_trend == "flat":
        parts.append("plateaued quiz performance and effective study habits")
    else:
        parts.append("improving quiz scores")

    if profile.session_regularity > 3:
        parts.append("irregular study sessions needing time management")
    if profile.submission_rate < 60:
        parts.append("missed or late assignment submissions and help-seeking")

    return "Strategies for a student with " + "; ".join(parts) + "."


def _format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no specific guidance retrieved)"
    return "\n\n".join(f"[{c.title}] {c.text}" for c in chunks)


def _template_feedback(profile: StudentProfile, chunks: list[RetrievedChunk]) -> str:
    """Deterministic three-paragraph feedback for the offline provider."""
    tips = [c.title for c in chunks] or ["effective study habits"]
    primary_tip = tips[0]
    secondary_tip = tips[1] if len(tips) > 1 else primary_tip

    if profile.engagement_score >= 70:
        p1 = (
            f"Hi {profile.name}, your engagement score of "
            f"{profile.engagement_score:.0f}/100 shows you are consistently active in "
            f"the course, putting in about {profile.time_on_task_hours:.1f} hours of "
            "focused study each week. That steady presence is a real strength worth "
            "protecting."
        )
    elif profile.engagement_score >= 40:
        p1 = (
            f"Hi {profile.name}, you are staying reasonably engaged with the course "
            f"(engagement {profile.engagement_score:.0f}/100, around "
            f"{profile.time_on_task_hours:.1f} hours/week). There is a solid base here "
            "to build on with a few small adjustments."
        )
    else:
        p1 = (
            f"Hi {profile.name}, your recent engagement has dipped to "
            f"{profile.engagement_score:.0f}/100 (about {profile.time_on_task_hours:.1f} "
            "hours/week). That is a signal to reconnect with the course — and the good "
            "news is that small, regular steps turn this around quickly."
        )

    if profile.quiz_trend == "positive":
        p2 = (
            "Your quiz scores are trending upward, which means your current approach is "
            f"working — keep it going. Drawing on \"{primary_tip}\", gradually increase "
            "the challenge of your practice so the improvement continues."
        )
    elif profile.quiz_trend == "negative":
        p2 = (
            "Your recent quiz scores have been sliding, which is usually an early sign of "
            f"growing gaps rather than ability. Using \"{primary_tip}\", switch from "
            "re-reading to active recall: close the book and test yourself, then review "
            "only what you miss."
        )
    else:
        p2 = (
            "Your quiz scores have plateaued. To break through, change how you practise — "
            f"guided by \"{primary_tip}\", move from recognition to closed-book "
            "self-testing and space your attempts across several days."
        )

    submission_note = (
        " Submitting on time, even imperfectly, will also lift your results."
        if profile.submission_rate < 60
        else ""
    )

    if profile.at_risk_flag:
        p3 = (
            "You have been flagged as at risk, but that is simply a prompt for support, "
            f"not a verdict. Following \"{secondary_tip}\", take one small step today and "
            "reach out to a peer or instructor — early help-seeking is a strength."
            + submission_note
        )
    else:
        p3 = (
            f"Keep building momentum. Informed by \"{secondary_tip}\", pick one concrete "
            "next step for this week and schedule it at a fixed time so it actually "
            "happens." + submission_note
        )

    return f"{p1}\n\n{p2}\n\n{p3}"


class FeedbackGenerator:
    """Produces feedback using the configured provider (real or mock)."""

    def __init__(self, chat: ChatModel | None = None, provider: str | None = None) -> None:
        self._provider = provider or provider_name()
        # Chat client is built lazily so the offline/mock path never imports the
        # OpenAI stack.
        self._chat = chat

    def generate(self, profile: StudentProfile, context: list[RetrievedChunk]) -> FeedbackResult:
        """Generate feedback for one student profile and retrieved context."""
        if self._provider == "mock":
            text = _template_feedback(profile, context)
        else:
            from langchain_core.prompts import PromptTemplate

            chat = self._chat if self._chat is not None else get_chat()
            prompt = PromptTemplate.from_template(FEEDBACK_PROMPT_TEMPLATE).format(
                profile=profile.to_text(),
                context=_format_context(context),
            )
            text = chat.complete(prompt)
        return FeedbackResult(feedback=text.strip(), provider=self._provider, context=context)
