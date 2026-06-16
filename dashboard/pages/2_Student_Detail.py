"""Student detail — indicators, radar, quiz trend, activity heatmap, AI feedback."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api_client as api

st.set_page_config(page_title="Student detail · SLA", page_icon="🔎", layout="wide")

health = api.require_api()
api.render_sidebar(health)

st.title("🔎 Student detail")

students = api.list_students()
ids = [s["student_id"] for s in students]
labels = {s["student_id"]: f"{s['student_id']} · {s['name']}" for s in students}

if not ids:
    st.warning("No students found.")
    st.stop()

default = st.session_state.get("selected_student", ids[0])
default_idx = ids.index(default) if default in ids else 0
student_id = st.selectbox("Student", ids, index=default_idx, format_func=lambda i: labels[i])
st.session_state["selected_student"] = student_id

try:
    student = api.get_student(student_id)
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

ind = student.get("indicators")

# --- header ----------------------------------------------------------------
head_l, head_r = st.columns([3, 1])
head_l.subheader(f"{student['name']}")
head_l.caption(f"{student['program']} · enrolled {student['enrollment_date']}")
if ind and ind["at_risk_flag"]:
    head_r.error("⚠️ At risk")
elif ind:
    head_r.success("✓ On track")

if not ind:
    st.info("No indicators computed for this student yet. Run the indicators pipeline.")
    st.stop()

# --- indicator metrics -----------------------------------------------------
m = st.columns(5)
m[0].metric("Engagement", f"{ind['engagement_score']:.0f}/100")
m[1].metric("Time on task", f"{ind['time_on_task_hours']:.1f} h/wk")
m[2].metric("Quiz trend", ind["quiz_trend"].title(), delta=f"{ind['quiz_trend_slope']:+.2f}")
m[3].metric("Regularity", f"{ind['session_regularity']:.1f}", help="Std days between logins")
m[4].metric("On-time", f"{ind['submission_rate']:.0f}%")

st.divider()

# --- radar + quiz trend ----------------------------------------------------
radar_col, trend_col = st.columns(2)

with radar_col:
    st.subheader("Indicator profile")
    axes = ["Engagement", "On-time", "Time on task", "Regularity", "Quiz improvement"]
    values = [
        ind["engagement_score"],
        ind["submission_rate"],
        min(ind["time_on_task_hours"] / 8.0, 1.0) * 100,        # cap 8 h/wk
        (1 - min(ind["session_regularity"] / 7.0, 1.0)) * 100,  # lower std = better
        min(max((ind["quiz_trend_slope"] + 5) / 10.0, 0.0), 1.0) * 100,
    ]
    fig = go.Figure(
        go.Scatterpolar(r=values + [values[0]], theta=axes + [axes[0]],
                        fill="toself", line_color="#4C78A8")
    )
    fig.update_layout(height=360, margin=dict(t=30, b=20),
                      polar=dict(radialaxis=dict(range=[0, 100], visible=True)),
                      showlegend=False)
    st.plotly_chart(fig, width="stretch")

with trend_col:
    st.subheader("Quiz score trend")
    try:
        attempts = api.get_quiz_attempts(student_id)
    except api.ApiError as exc:
        attempts = []
        st.warning(str(exc))
    if attempts:
        qdf = pd.DataFrame(attempts)
        qdf["submitted_at"] = pd.to_datetime(qdf["submitted_at"])
        qdf = qdf.sort_values("submitted_at")
        fig = go.Figure(
            go.Scatter(x=qdf["submitted_at"], y=qdf["score"], mode="lines+markers",
                       line_color="#4C78A8")
        )
        fig.update_layout(height=360, margin=dict(t=30, b=20),
                          yaxis=dict(range=[0, 100], title="Score"), xaxis_title="")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No quiz attempts recorded.")

# --- session activity heatmap ----------------------------------------------
st.subheader("Session activity (day × hour)")
try:
    sessions = api.get_sessions(student_id)
except api.ApiError as exc:
    sessions = []
    st.warning(str(exc))

if sessions:
    sdf = pd.DataFrame(sessions)
    sdf["login_at"] = pd.to_datetime(sdf["login_at"])
    sdf["weekday"] = sdf["login_at"].dt.dayofweek
    sdf["hour"] = sdf["login_at"].dt.hour
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    matrix = (
        sdf.pivot_table(index="weekday", columns="hour", values="login_at",
                        aggfunc="count", fill_value=0)
        .reindex(index=range(7), columns=range(24), fill_value=0)
    )
    fig = go.Figure(
        go.Heatmap(z=matrix.values, x=[f"{h:02d}" for h in range(24)], y=days,
                   colorscale="Blues", colorbar=dict(title="Logins"))
    )
    fig.update_layout(height=320, margin=dict(t=10, b=10), xaxis_title="Hour of day")
    st.plotly_chart(fig, width="stretch")
else:
    st.info("No sessions recorded.")

st.divider()

# --- AI feedback panel -----------------------------------------------------
st.subheader("🤖 AI feedback")
st.caption(f"Generated via the RAG pipeline (provider: `{health.get('llm_provider')}`).")

if st.button("Generate personalized feedback", type="primary"):
    with st.spinner("Retrieving guidance and generating feedback…"):
        try:
            result = api.get_feedback(student_id)
        except api.ApiError as exc:
            st.error(str(exc))
            result = None
    if result:
        st.session_state[f"feedback_{student_id}"] = result

result = st.session_state.get(f"feedback_{student_id}")
if result:
    st.success(f"Feedback generated by `{result['provider']}`.")
    for para in [p for p in result["feedback"].split("\n\n") if p.strip()]:
        st.write(para)
    if result.get("context"):
        with st.expander("Retrieved pedagogy context"):
            for c in result["context"]:
                st.markdown(f"**{c['title']}** · _{c['source']}_")
                st.caption(c["text"])
