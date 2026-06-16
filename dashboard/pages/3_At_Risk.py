"""At-risk students — focused list with bulk feedback generation."""

from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="At-risk · SLA", page_icon="⚠️", layout="wide")

health = api.require_api()
api.render_sidebar(health)

st.title("⚠️ At-risk students")
st.caption("Students with low engagement and a declining quiz trend — prioritise outreach.")

df = api.students_frame(api.list_students())
at_risk = df[df["at_risk_flag"].fillna(False)].copy()

c1, c2 = st.columns(2)
c1.metric("At-risk students", len(at_risk))
c2.metric("Share of cohort", f"{(len(at_risk) / max(len(df), 1)) * 100:.0f}%")

if at_risk.empty:
    st.success("🎉 No students are currently flagged as at risk.")
    st.stop()

st.dataframe(
    at_risk[["student_id", "name", "program", "engagement_score",
             "quiz_trend", "submission_rate"]],
    width="stretch",
    hide_index=True,
    column_config={
        "student_id": "ID",
        "name": "Name",
        "program": "Program",
        "engagement_score": st.column_config.ProgressColumn(
            "Engagement", min_value=0, max_value=100, format="%.0f"
        ),
        "quiz_trend": "Quiz trend",
        "submission_rate": st.column_config.NumberColumn("On-time %", format="%.0f%%"),
    },
)

st.divider()
st.subheader("Bulk feedback")
provider = health.get("llm_provider")
st.caption(
    f"Generate personalized feedback for every at-risk student (provider: `{provider}`). "
    "With the real OpenAI provider this makes one call per student and may take a while."
)

if st.button("Generate feedback for all at-risk students", type="primary"):
    ids = at_risk["student_id"].tolist()
    progress = st.progress(0.0, text="Starting…")
    results: dict[str, dict] = {}
    errors: dict[str, str] = {}
    for i, sid in enumerate(ids, start=1):
        progress.progress(i / len(ids), text=f"Generating {i}/{len(ids)} ({sid})…")
        try:
            results[sid] = api.get_feedback(sid)
        except api.ApiError as exc:
            errors[sid] = str(exc)
    progress.empty()
    st.session_state["bulk_feedback"] = {"results": results, "errors": errors}

bulk = st.session_state.get("bulk_feedback")
if bulk:
    if bulk["errors"]:
        st.warning(f"{len(bulk['errors'])} student(s) failed; showing the rest.")
    names = dict(zip(at_risk["student_id"], at_risk["name"], strict=False))
    for sid, result in bulk["results"].items():
        with st.expander(f"{names.get(sid, sid)} ({sid}) — via {result['provider']}"):
            for para in [p for p in result["feedback"].split("\n\n") if p.strip()]:
                st.write(para)
