"""Overview page — cohort-level metrics and distributions.

Entry point of the multi-page Streamlit app. All data comes from the FastAPI
backend via :mod:`api_client`; there are no direct database calls.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

import api_client as api

st.set_page_config(page_title="Overview · SLA", page_icon="🎓", layout="wide")

health = api.require_api()
api.render_sidebar(health)

st.title("🎓 Student Learning Analytics")
st.caption("Cohort overview — engagement, risk, and quiz trends across all students.")

students = api.list_students()
df = api.students_frame(students)

if df.empty:
    st.warning("No students found. Run the data pipeline first.")
    st.stop()

with_indicators = df["engagement_score"].notna()
if not with_indicators.any():
    st.info(
        "Students are loaded but indicators have not been computed yet. "
        "Trigger the `dag_indicators` pipeline, then reload."
    )
    st.stop()

ind = df[with_indicators]
total = len(df)
at_risk = int(df["at_risk_flag"].fillna(False).sum())

# --- metric cards ----------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total students", total)
c2.metric("At-risk", at_risk, delta=f"{at_risk / total * 100:.0f}% of cohort",
          delta_color="inverse")
c3.metric("Avg engagement", f"{ind['engagement_score'].mean():.1f} / 100")
c4.metric("Avg quiz slope", f"{ind['quiz_trend_slope'].mean():+.2f}",
          help="Average slope of recent quiz scores (positive = improving)")

st.divider()

# --- distributions ---------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Engagement distribution")
    fig = px.histogram(ind, x="engagement_score", nbins=20,
                       color_discrete_sequence=["#4C78A8"])
    fig.add_vline(x=40, line_dash="dash", line_color="#E45756",
                  annotation_text="at-risk threshold")
    fig.update_layout(height=320, margin=dict(t=10, b=10), xaxis_title="Engagement score",
                      yaxis_title="Students")
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Quiz trend mix")
    trend_counts = (
        ind["quiz_trend"].value_counts().reindex(["positive", "flat", "negative"]).fillna(0)
        .reset_index()
    )
    trend_counts.columns = ["quiz_trend", "count"]
    fig = px.bar(trend_counts, x="quiz_trend", y="count", color="quiz_trend",
                 color_discrete_map={"positive": "#54A24B", "flat": "#B0B0B0",
                                     "negative": "#E45756"})
    fig.update_layout(height=320, margin=dict(t=10, b=10), showlegend=False,
                      xaxis_title="", yaxis_title="Students")
    st.plotly_chart(fig, width="stretch")

left2, right2 = st.columns(2)

with left2:
    st.subheader("Risk split")
    risk_df = (
        df["at_risk_flag"].fillna(False)
        .map({True: "At risk", False: "On track"})
        .value_counts().reset_index()
    )
    risk_df.columns = ["status", "count"]
    fig = px.pie(risk_df, names="status", values="count", hole=0.55,
                 color="status",
                 color_discrete_map={"At risk": "#E45756", "On track": "#54A24B"})
    fig.update_layout(height=320, margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")

with right2:
    st.subheader("Students per program")
    prog = df["program"].value_counts().reset_index()
    prog.columns = ["program", "count"]
    fig = px.bar(prog, x="count", y="program", orientation="h",
                 color_discrete_sequence=["#72B7B2"])
    fig.update_layout(height=320, margin=dict(t=10, b=10), xaxis_title="Students",
                      yaxis_title="")
    st.plotly_chart(fig, width="stretch")

st.caption("Use the pages in the sidebar to drill into the student list, "
           "individual detail, and at-risk students.")
