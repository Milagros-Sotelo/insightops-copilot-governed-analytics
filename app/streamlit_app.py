"""Six-page Streamlit operating console for InsightOps Copilot."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from insightops.audit import AuditLog
from insightops.copilot import DeterministicCopilot


DATA_DIR = Path(os.getenv("INSIGHTOPS_DATA_DIR", "data/demo"))
MARTS = DATA_DIR / "marts"


@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    names = ("ingestion_runs", "quality_summary", "quality_results", "metric_results", "anomaly_results", "metric_definitions")
    return {name: pd.read_csv(MARTS / f"{name}.csv") for name in names}


st.set_page_config(page_title="InsightOps Copilot", page_icon="IO", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"]{background:#171d2d}.block-container{padding-top:2rem}
.io-card{padding:1rem 1.1rem;border:1px solid #e8e7ee;border-radius:14px;background:white}
.io-label{font-size:.72rem;color:#7568d8;text-transform:uppercase;letter-spacing:.08em}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("InsightOps")
st.sidebar.caption("ASTERIA SERVICES · GOVERNED ANALYTICS")
page = st.sidebar.radio("Workspace", ("Control Center", "Data Quality", "KPI Monitoring", "Anomaly Center", "Copilot", "Report Review"))
st.sidebar.divider()
st.sidebar.success("Deterministic mode · No external AI API")

if not MARTS.exists():
    st.error("Run `python -m insightops.pipeline` to create the demo marts.")
    st.stop()

data = load_data()
runs, quality, metrics, anomalies = data["ingestion_runs"], data["quality_summary"], data["metric_results"], data["anomaly_results"]

if page == "Control Center":
    st.title("Control Center")
    st.caption("From file arrival to approved analytical views")
    cols = st.columns(5)
    cols[0].metric("Runs", f"{len(runs):,}")
    cols[1].metric("Files completed", int(runs["status"].eq("completed").sum()))
    cols[2].metric("Rows accepted", f"{int(runs['rows_accepted'].sum()):,}")
    cols[3].metric("Rows rejected", f"{int(runs['rows_rejected'].sum()):,}")
    cols[4].metric("Avg quality", f"{quality['quality_score'].mean():.2f}")
    st.subheader("Latest processing runs")
    st.dataframe(runs.sort_values("started_at", ascending=False).head(25), use_container_width=True, hide_index=True)

elif page == "Data Quality":
    st.title("Data Quality")
    st.caption("Completeness, validity, uniqueness, consistency and timeliness")
    c1, c2 = st.columns((1.6, 1))
    with c1:
        fig = px.line(quality.reset_index(), x="index", y="quality_score", markers=True, title="Quality score by run")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.metric("Worst file", quality.sort_values("quality_score").iloc[0]["source_file"])
        st.metric("Lowest score", f"{quality['quality_score'].min():.2f}")
        st.metric("Rejected records", int(quality["rows_rejected"].sum()))
    st.subheader("Rule failures")
    st.dataframe(data["quality_results"].sort_values("failed_rows", ascending=False).head(30), use_container_width=True, hide_index=True)

elif page == "KPI Monitoring":
    st.title("KPI Monitoring")
    metric_id = st.selectbox("Metric", sorted(metrics["metric_id"].unique()))
    selected = metrics.loc[metrics["metric_id"].eq(metric_id)].copy()
    latest = selected.iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric(str(latest["name"]), f"{latest['value']:,.2f}")
    c2.metric("Budget", "—" if pd.isna(latest["budget"]) else f"{latest['budget']:,.2f}")
    c3.metric("Budget variance", "—" if pd.isna(latest["budget_variance"]) else f"{latest['budget_variance']:+.1%}")
    melted = selected.melt(id_vars="period", value_vars=["value", "budget"], var_name="series", value_name="amount")
    st.plotly_chart(px.line(melted, x="period", y="amount", color="series", markers=True), use_container_width=True)
    with st.expander("Metric definition"):
        st.write(latest[["metric_id", "definition", "formula", "owner", "frequency", "improvement_direction"]])

elif page == "Anomaly Center":
    st.title("Anomaly Center")
    severity = st.multiselect("Severity", sorted(anomalies["severity"].unique()), default=sorted(anomalies["severity"].unique()))
    filtered = anomalies.loc[anomalies["severity"].isin(severity)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Open alerts", len(filtered))
    c2.metric("Critical", int(filtered["severity"].eq("critical").sum()))
    c3.metric("Latest period", filtered["period"].max())
    st.dataframe(filtered[["severity", "period", "metric_name", "observed_value", "expected_value", "variation", "method", "explanation", "review_status"]], use_container_width=True, hide_index=True)

elif page == "Copilot":
    st.title("Copilot")
    st.caption("Grounded answers · approved SQL views · read-only · fully auditable")
    prompts = ("¿Qué KPI se desviaron este mes?", "¿Por qué bajó el margen?", "¿Qué archivos tuvieron peor calidad?", "¿Qué proveedores concentran mayor gasto?")
    question = st.selectbox("Try a governed question", prompts)
    custom = st.text_input("Or write your question", placeholder="Ask about metrics, anomalies or quality")
    if st.button("Analyze", type="primary"):
        engine = DeterministicCopilot(metrics, anomalies, quality, AuditLog(DATA_DIR / "streamlit_audit.jsonl"))
        try:
            answer = engine.answer(custom or question)
            st.markdown(f"### {answer.answer}")
            if answer.facts:
                st.write("**Verified facts**")
                for fact in answer.facts: st.write(f"- {fact}")
            if answer.hypotheses:
                st.write("**Hypotheses to validate**")
                for item in answer.hypotheses: st.write(f"- {item}")
            st.info(answer.warning)
            with st.expander("Traceability"):
                st.code(answer.sql or "No query executed", language="sql")
                st.write({"period": answer.period, "sources": answer.sources, "metrics": answer.metrics})
        except ValueError as error:
            st.error(str(error))

else:
    st.title("Report Review")
    report_path = DATA_DIR / "report_draft.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    st.caption(f"{report['report_id']} · Status: {report['status']}")
    st.text_area("Executive summary", report["executive_summary"], height=110)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("KPI highlights")
        for item in report["kpi_highlights"]: st.write(f"- {item}")
        st.subheader("Anomalies")
        for item in report["anomalies"]: st.write(f"- {item}")
    with c2:
        st.subheader("Recommendations")
        for item in report["recommendations"]: st.write(f"- {item}")
        st.subheader("Limitations")
        for item in report["limitations"]: st.write(f"- {item}")
    st.warning("Human approval is required before this draft can be considered final or published.")
    approve, reject = st.columns(2)
    approve.button("Approve report", type="primary", use_container_width=True)
    reject.button("Reject and request changes", use_container_width=True)

