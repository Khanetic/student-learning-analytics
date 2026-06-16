"""Student list — sortable, filterable table with drill-through to detail."""

from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="Students · SLA", page_icon="📋", layout="wide")

health = api.require_api()
api.render_sidebar(health)

st.title("📋 Student list")

df = api.students_frame(api.list_students())
if df.empty:
    st.warning("No students found.")
    st.stop()

# --- filters ---------------------------------------------------------------
f1, f2, f3 = st.columns([2, 2, 1])
search = f1.text_input("Search by name or ID", placeholder="e.g. S0001 or Allison")
programs = f2.multiselect("Program", sorted(df["program"].unique()))
at_risk_only = f3.toggle("At-risk only")

view = df.copy()
if search:
    s = search.lower()
    view = view[
        view["name"].str.lower().str.contains(s) | view["student_id"].str.lower().str.contains(s)
    ]
if programs:
    view = view[view["program"].isin(programs)]
if at_risk_only:
    view = view[view["at_risk_flag"].fillna(False)]

st.caption(f"Showing {len(view)} of {len(df)} students. Click a row, then open the detail page.")

display_cols = [
    "student_id", "name", "program", "engagement_score",
    "quiz_trend", "submission_rate", "at_risk_flag",
]
event = st.dataframe(
    view[display_cols],
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "student_id": "ID",
        "name": "Name",
        "program": "Program",
        "engagement_score": st.column_config.ProgressColumn(
            "Engagement", min_value=0, max_value=100, format="%.0f"
        ),
        "quiz_trend": "Quiz trend",
        "submission_rate": st.column_config.NumberColumn("On-time %", format="%.0f%%"),
        "at_risk_flag": st.column_config.CheckboxColumn("At risk"),
    },
)

selected_rows = event.selection.rows if event and event.selection else []
if selected_rows:
    chosen = view.iloc[selected_rows[0]]
    st.session_state["selected_student"] = chosen["student_id"]
    c1, c2 = st.columns([1, 4])
    if c1.button("Open detail ➜", type="primary", width="stretch"):
        st.switch_page("pages/2_Student_Detail.py")
    c2.info(f"Selected **{chosen['name']}** ({chosen['student_id']}).")
