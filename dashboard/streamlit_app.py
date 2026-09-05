"""AI Finance Controller - Interactive Streamlit Dashboard."""
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.controller import FinanceController
from app.data.generator import generate_all
from app.models.schemas import MatchStatus, ReconciliationRun, ReconciliationResult
from app.agent.explainer import FinanceExplainer

st.set_page_config(
    page_title="AI Finance Controller",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Premium Dark Finance Theme CSS ──────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%);
        border-right: 1px solid rgba(99, 102, 241, 0.15);
    }

    /* Metric Cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(30, 41, 59, 0.95) 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        padding: 12px 16px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
    }
    div[data-testid="metric-container"] label {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        font-weight: 700 !important;
    }

    /* Status Badges */
    .badge {
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        display: inline-block;
    }
    .badge-matched { background: rgba(0, 210, 106, 0.15); color: #00d26a; border: 1px solid rgba(0, 210, 106, 0.3); }
    .badge-likely { background: rgba(163, 230, 53, 0.15); color: #a3e635; border: 1px solid rgba(163, 230, 53, 0.3); }
    .badge-review { background: rgba(255, 165, 0, 0.15); color: #ffa500; border: 1px solid rgba(255, 165, 0, 0.3); }
    .badge-mismatch { background: rgba(255, 68, 68, 0.15); color: #ff4444; border: 1px solid rgba(255, 68, 68, 0.3); }
    .badge-missing { background: rgba(139, 0, 0, 0.15); color: #ff6b6b; border: 1px solid rgba(139, 0, 0, 0.3); }
    .badge-duplicate { background: rgba(156, 39, 176, 0.15); color: #ce93d8; border: 1px solid rgba(156, 39, 176, 0.3); }

    /* Glass Card */
    .glass-card {
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.8) 0%, rgba(30, 41, 59, 0.8) 100%);
        border: 1px solid rgba(99, 102, 241, 0.15);
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
        margin-bottom: 20px;
    }

    .summary-card {
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(30, 58, 95, 0.9) 100%);
        border: 1px solid rgba(59, 130, 246, 0.2);
        padding: 28px;
        border-radius: 16px;
        margin: 16px 0;
    }

    .hero-text {
        font-size: 1.1rem;
        color: #e2e8f0;
        font-style: italic;
        padding: 16px 20px;
        border-left: 3px solid #6366f1;
        background: rgba(99, 102, 241, 0.05);
        border-radius: 0 8px 8px 0;
        margin: 16px 0;
    }

    /* KPI specific colors */
    .kpi-green div[data-testid="stMetricValue"] { color: #00d26a !important; }
    .kpi-red div[data-testid="stMetricValue"] { color: #ff4444 !important; }
    .kpi-blue div[data-testid="stMetricValue"] { color: #60a5fa !important; }
    .kpi-orange div[data-testid="stMetricValue"] { color: #ffa500 !important; }
    .kpi-purple div[data-testid="stMetricValue"] { color: #a78bfa !important; }

    /* Section headers */
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #e2e8f0;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(99, 102, 241, 0.3);
        margin-bottom: 16px;
    }

    .stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Session State ───────────────────────────────────────────────────────────
if 'reconciliation_run' not in st.session_state:
    st.session_state.reconciliation_run = None


def get_status_badge(status: str) -> str:
    """Return HTML badge for a status."""
    badge_map = {
        "MATCHED": "badge-matched",
        "LIKELY_MATCH": "badge-likely",
        "MANUAL_REVIEW": "badge-review",
        "MISMATCH": "badge-mismatch",
        "MISSING": "badge-missing",
        "DUPLICATE": "badge-duplicate",
    }
    css_class = badge_map.get(status, "badge-review")
    display = status.replace("_", " ")
    return f'<span class="badge {css_class}">{display}</span>'


STATUS_COLORS = {
    "MATCHED": "#00d26a",
    "LIKELY_MATCH": "#a3e635",
    "MANUAL_REVIEW": "#ffa500",
    "MISMATCH": "#ff4444",
    "MISSING": "#ff6b6b",
    "DUPLICATE": "#ce93d8",
}


def run_reconciliation():
    """Execute the reconciliation pipeline."""
    progress_bar = st.progress(0, text="Initializing AI Finance Controller...")
    steps = [
        (10, "Loading financial data..."),
        (25, "Normalizing records..."),
        (45, "Running matching engine..."),
        (65, "Detecting exceptions..."),
        (80, "Generating explanations..."),
        (95, "Calculating metrics..."),
    ]
    for pct, label in steps:
        progress_bar.progress(pct, text=label)
        time.sleep(0.15)
    try:
        controller = FinanceController()
        st.session_state.reconciliation_run = controller.run_pipeline()
        progress_bar.progress(100, text="Reconciliation complete!")
        time.sleep(0.3)
        progress_bar.empty()
        st.success("✅ Reconciliation completed successfully!")
        st.rerun()
    except Exception as e:
        progress_bar.empty()
        st.error(f"❌ Error: {e}")


def generate_demo_data():
    """Generate synthetic demo data."""
    with st.spinner("Generating synthetic financial data..."):
        try:
            generate_all()
            st.success("✅ Demo data generated! Click 'Run Reconciliation' to process.")
        except Exception as e:
            st.error(f"Error: {e}")


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏦 AI Finance Controller")
    st.caption("Autonomous Reconciliation for Finance Operations")
    st.markdown("---")

    nav = st.radio(
        "Navigation",
        ["📊 Dashboard", "🔍 Reconciliation", "⚠️ Exceptions",
         "🔎 Transaction Explorer", "ℹ️ About"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Generate Data", use_container_width=True):
            generate_demo_data()
    with col2:
        if st.button("▶️ Reconcile", type="primary", use_container_width=True):
            run_reconciliation()

    st.markdown("---")
    st.link_button("🔗 GitHub Repository", "https://github.com/Divyankghinmine/Sentinel-Finance", use_container_width=True)
    st.link_button("📺 Watch Demo Video", "https://youtube.com", use_container_width=True)

    st.markdown("---")
    st.caption("⚙️ System Info")
    from app.core.config import AI_MODE, DATA_DIR
    st.caption(f"Mode: `{AI_MODE}`")
    st.caption(f"Engine: `Deterministic + Fuzzy`")
    st.caption(f"Data: `{DATA_DIR}`")
    st.caption("Version: `1.0.0`")


# ── Main Content ────────────────────────────────────────────────────────────
if st.session_state.reconciliation_run is None:
    # Welcome screen
    st.markdown("# 🏦 AI Finance Controller")
    st.markdown("### Autonomous Reconciliation for Finance Operations")
    st.markdown("")
    st.markdown('<div class="hero-text">"The AI doesn\'t pretend everything matches. It knows what it can reconcile and clearly identifies what needs a human."</div>', unsafe_allow_html=True)

    st.markdown("")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("""<div class="glass-card">
            <h4>📥 Multi-Source Ingestion</h4>
            <p style="color: #94a3b8;">Bank statements, ERP ledger, and payment processor data unified in one pipeline.</p>
        </div>""", unsafe_allow_html=True)
    with cols[1]:
        st.markdown("""<div class="glass-card">
            <h4>🎯 Smart Matching</h4>
            <p style="color: #94a3b8;">Exact + fuzzy matching with transparent weighted scoring across 5 dimensions.</p>
        </div>""", unsafe_allow_html=True)
    with cols[2]:
        st.markdown("""<div class="glass-card">
            <h4>🚨 Honest Exceptions</h4>
            <p style="color: #94a3b8;">Every unresolved record gets a clear explanation and recommended action.</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("")
    st.info("👉 **Generate demo data** and click **Run Reconciliation** in the sidebar to begin.")

else:
    run: ReconciliationRun = st.session_state.reconciliation_run
    metrics = run.metrics
    results = run.results
    explainer = FinanceExplainer()

    page = nav.split(" ", 1)[1] if " " in nav else nav

    if page == "Dashboard":
        st.markdown("# 📊 Executive Dashboard")
        st.caption(f"Run ID: `{run.run_id}` | Timestamp: `{run.timestamp[:19]}`")
        st.markdown("")

        # KPI Row
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.markdown('<div class="kpi-blue">', unsafe_allow_html=True)
            st.metric("Total Records", metrics.total_records)
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="kpi-green">', unsafe_allow_html=True)
            st.metric("Matched", metrics.matched)
            st.markdown('</div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="kpi-green">', unsafe_allow_html=True)
            st.metric("Match Rate", f"{metrics.match_rate:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
        with c4:
            exceptions_count = metrics.likely_matches + metrics.manual_review
            st.markdown('<div class="kpi-orange">', unsafe_allow_html=True)
            st.metric("Review Needed", exceptions_count)
            st.markdown('</div>', unsafe_allow_html=True)
        with c5:
            unresolved = metrics.mismatches + metrics.missing
            st.markdown('<div class="kpi-red">', unsafe_allow_html=True)
            st.metric("Unresolved", unresolved)
            st.markdown('</div>', unsafe_allow_html=True)
        with c6:
            st.markdown('<div class="kpi-purple">', unsafe_allow_html=True)
            st.metric("Processing Time", f"{metrics.processing_time:.2f}s")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("")

        # Charts row
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown('<div class="section-header">Reconciliation Overview</div>', unsafe_allow_html=True)
            status_data = {}
            for r in results:
                s = r.status.value
                status_data[s] = status_data.get(s, 0) + 1

            fig = go.Figure(data=[go.Pie(
                labels=list(status_data.keys()),
                values=list(status_data.values()),
                hole=0.5,
                marker=dict(colors=[STATUS_COLORS.get(k, "#888") for k in status_data.keys()]),
                textinfo='label+value',
                textfont=dict(size=13),
                hovertemplate='%{label}: %{value} records<br>%{percent}<extra></extra>'
            )])
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e2e8f0'),
                showlegend=True,
                legend=dict(font=dict(size=12)),
                height=380,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.markdown('<div class="section-header">Confidence Distribution</div>', unsafe_allow_html=True)
            confidences = [r.confidence for r in results if r.confidence > 0]
            if confidences:
                fig2 = go.Figure(data=[go.Histogram(
                    x=confidences,
                    nbinsx=20,
                    marker_color='#6366f1',
                    marker_line=dict(color='#818cf8', width=1),
                    opacity=0.85
                )])
                fig2.add_vline(x=0.9, line_dash="dash", line_color="#00d26a", annotation_text="Match threshold")
                fig2.add_vline(x=0.5, line_dash="dash", line_color="#ff4444", annotation_text="Review threshold")
                fig2.update_layout(
                    xaxis_title="Confidence Score",
                    yaxis_title="Count",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0'),
                    height=380,
                    margin=dict(t=20, b=40, l=40, r=20)
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No confidence data available.")

        # Summary Card
        st.markdown("")
        summary = explainer.generate_summary(metrics, results)
        recommendations = explainer.generate_recommendations(results)

        st.markdown(f"""
        <div class="summary-card">
            <h4 style="color: #60a5fa; margin-bottom: 12px;">🤖 Finance Controller Summary</h4>
            <p style="color: #e2e8f0; line-height: 1.7;">{summary}</p>
            <hr style="border-color: rgba(99,102,241,0.2); margin: 16px 0;">
            <h5 style="color: #a78bfa;">Recommended Actions:</h5>
            <ul style="color: #cbd5e1;">
                {''.join(f'<li>{r}</li>' for r in recommendations)}
            </ul>
        </div>
        """, unsafe_allow_html=True)

        if metrics.accuracy is not None:
            st.markdown(f"""
            <div class="glass-card">
                <h4 style="color: #fbbf24;">🎯 Accuracy vs Ground Truth</h4>
                <p style="font-size: 2rem; font-weight: 700; color: #fbbf24;">{metrics.accuracy:.1%}</p>
                <p style="color: #94a3b8;">Evaluated against synthetic ground truth labels</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="section-header">All Reconciliation Results & Solutions</div>', unsafe_allow_html=True)
        
        all_data = []
        for r in results:
            all_data.append({
                "ID": r.source_id,
                "Status": r.status.value,
                "Confidence": f"{r.confidence:.2f}",
                "Problem (Reason)": r.reason,
                "Solution (Action)": r.recommended_action
            })
        
        if all_data:
            st.dataframe(pd.DataFrame(all_data), use_container_width=True, height=400)

    elif page == "Reconciliation":
        st.markdown("# 🔍 Reconciliation Results")
        st.caption(f"{len(results)} total records processed")

        status_filter = st.multiselect(
            "Filter by Status",
            [e.value for e in MatchStatus],
            default=[e.value for e in MatchStatus]
        )

        data = []
        for r in results:
            if r.status.value in status_filter:
                data.append({
                    "Source ID": r.source_id,
                    "Source": r.source_type.value if r.source_type else "",
                    "Target ID": r.target_id or "—",
                    "Target": r.target_type.value if r.target_type else "—",
                    "Status": r.status.value,
                    "Confidence": f"{r.confidence:.2f}",
                    "Amt Diff": f"{r.amount_difference:.2f}",
                    "Date Diff": f"{r.date_difference}d",
                    "Reason": r.reason[:80] + "..." if len(r.reason) > 80 else r.reason
                })

        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, height=500)

            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Results CSV",
                data=csv_data,
                file_name="reconciliation_results.csv",
                mime="text/csv"
            )
        else:
            st.info("No records match the selected filters.")

    elif page == "Exceptions":
        st.markdown("# ⚠️ Exception Queue")

        exceptions = [r for r in results if r.status.value not in ("MATCHED",)]

        if not exceptions:
            st.success("🎉 No exceptions! All records reconciled successfully.")
        else:
            st.caption(f"{len(exceptions)} records require attention")

            # Summary metrics
            ec1, ec2, ec3, ec4 = st.columns(4)
            likely = [r for r in exceptions if r.status == MatchStatus.LIKELY_MATCH]
            reviews = [r for r in exceptions if r.status == MatchStatus.MANUAL_REVIEW]
            mismatches = [r for r in exceptions if r.status == MatchStatus.MISMATCH]
            others = [r for r in exceptions if r.status in (MatchStatus.MISSING, MatchStatus.DUPLICATE)]
            with ec1:
                st.metric("Likely Matches", len(likely))
            with ec2:
                st.metric("Manual Review", len(reviews))
            with ec3:
                st.metric("Mismatches", len(mismatches))
            with ec4:
                st.metric("Missing/Duplicate", len(others))

            st.markdown("")

            # Exception table
            data = []
            for r in exceptions:
                data.append({
                    "Record ID": r.source_id,
                    "Source": r.source_type.value if r.source_type else "",
                    "Target": r.target_id or "—",
                    "Amt Diff": f"{r.amount_difference:.2f}",
                    "Date Diff": f"{r.date_difference}d",
                    "Score": f"{r.score:.3f}",
                    "Status": r.status.value,
                    "Exception": r.exception_type.value if r.exception_type else "—",
                    "Reason": r.reason,
                    "Action": r.recommended_action
                })

            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, height=400)

            # Exception type distribution
            st.markdown("")
            st.markdown('<div class="section-header">Exception Type Distribution</div>', unsafe_allow_html=True)
            exc_types = [r.exception_type.value for r in exceptions if r.exception_type]
            if exc_types:
                exc_counts = pd.Series(exc_types).value_counts()
                fig = go.Figure(data=[go.Bar(
                    x=exc_counts.index.tolist(),
                    y=exc_counts.values.tolist(),
                    marker_color=['#ff4444', '#ffa500', '#ce93d8', '#ff6b6b', '#60a5fa', '#a3e635', '#fbbf24', '#e879f9'][:len(exc_counts)],
                    text=exc_counts.values.tolist(),
                    textposition='outside'
                )])
                fig.update_layout(
                    xaxis_title="Exception Type",
                    yaxis_title="Count",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0'),
                    height=350,
                    margin=dict(t=30, b=40)
                )
                st.plotly_chart(fig, use_container_width=True)

            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Exceptions CSV",
                data=csv_data,
                file_name="exceptions.csv",
                mime="text/csv"
            )

    elif page == "Transaction Explorer":
        st.markdown("# 🔎 Transaction Explorer")
        st.caption("Deep-dive into individual transaction reconciliation")

        tx_options = [f"{r.source_id} | {r.status.value} | Score: {r.confidence:.2f}" for r in results]
        selected = st.selectbox("Select a transaction to explore:", tx_options)

        if selected:
            tx_id = selected.split(" | ")[0]
            tx = next((r for r in results if r.source_id == tx_id), None)

            if tx:
                # Status header
                st.markdown(f"### {tx.source_id} {get_status_badge(tx.status.value)}", unsafe_allow_html=True)
                st.markdown("")

                # Detail columns
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("""<div class="glass-card"><h4 style="color: #60a5fa;">📤 Source Record</h4></div>""", unsafe_allow_html=True)
                    st.json({
                        "ID": tx.source_id,
                        "Type": tx.source_type.value if tx.source_type else "N/A",
                        "Status": tx.status.value,
                        "Confidence": f"{tx.confidence:.4f}"
                    })

                with col2:
                    st.markdown("""<div class="glass-card"><h4 style="color: #a78bfa;">📥 Matched Target</h4></div>""", unsafe_allow_html=True)
                    if tx.target_id:
                        st.json({
                            "ID": tx.target_id,
                            "Type": tx.target_type.value if tx.target_type else "N/A",
                            "Amount Difference": f"{tx.amount_difference:.2f}",
                            "Date Difference": f"{tx.date_difference} days"
                        })
                    else:
                        st.warning("No matching target found.")

                # Score Breakdown
                if tx.score_breakdown:
                    st.markdown("")
                    st.markdown('<div class="section-header">Score Breakdown</div>', unsafe_allow_html=True)

                    bd = tx.score_breakdown.model_dump() if hasattr(tx.score_breakdown, 'model_dump') else vars(tx.score_breakdown)
                    labels = ["Reference", "Amount", "Date", "Vendor", "Currency", "Total"]
                    values = [bd["reference_score"], bd["amount_score"], bd["date_score"],
                              bd["vendor_score"], bd["currency_score"], bd["total_score"]]
                    colors = ["#6366f1", "#6366f1", "#6366f1", "#6366f1", "#6366f1", "#00d26a"]

                    fig = go.Figure(data=[go.Bar(
                        y=labels,
                        x=values,
                        orientation='h',
                        marker_color=colors,
                        text=[f"{v:.3f}" for v in values],
                        textposition='outside'
                    )])
                    fig.add_vline(x=0.9, line_dash="dash", line_color="#00d26a",
                                  annotation_text="Match threshold (0.90)")
                    fig.update_layout(
                        xaxis=dict(range=[0, 1.15], title="Score"),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#e2e8f0'),
                        height=300,
                        margin=dict(t=20, b=40, l=80, r=60)
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # AI Decision
                st.markdown("")
                explanation = explainer.explain_exception(tx)
                st.markdown(f"""
                <div class="summary-card">
                    <h4 style="color: #60a5fa;">🤖 AI Decision</h4>
                    <p style="color: #e2e8f0;">{explanation}</p>
                    <hr style="border-color: rgba(99,102,241,0.2);">
                    <p style="color: #fbbf24;"><strong>Recommended Action:</strong> {tx.recommended_action}</p>
                </div>
                """, unsafe_allow_html=True)

    elif page == "About":
        st.markdown("# ℹ️ About AI Finance Controller")

        st.markdown("""
        <div class="hero-text">"The AI doesn't pretend everything matches. It knows what it can reconcile and clearly identifies what needs a human."</div>
        """, unsafe_allow_html=True)

        st.markdown("")

        st.markdown("### 🏗️ Architecture")
        st.code("""
🏦 Bank CSV ──────🌐
                      │
📒 ERP Ledger ────┼──> Data Ingestion ──> Normalization ──> Matching Engine
                      │                                              │
💳 Payments ──────🌐                                              ▼
                                                          Exception Detection
                                                                │
                                                          AI Explanations
                                                                │
                                                          Metrics & Audit
                                                                │
                                               ┌────────────────┼────────────────🌐
                                               ▼                ▼
                                          FastAPI API    Streamlit Dashboard
        """, language="text")

        st.markdown("### 🎯 Matching Algorithm")
        st.markdown("""
        The reconciliation engine uses a **deterministic weighted scoring** system:

        | Signal | Weight | Method |
        |--------|--------|--------|
        | Reference/ID Similarity | 30% | RapidFuzz ratio |
        | Amount Match | 30% | Percentage difference |
        | Date Proximity | 15% | Day-difference decay |
        | Vendor/Merchant Similarity | 15% | RapidFuzz token sort ratio |
        | Currency Match | 10% | Exact match |

        **Core matching is 100% deterministic.** No LLM is used for financial matching decisions.
        The optional AI layer only provides natural-language explanations.
        """)

        st.markdown("### 🧪 Technology Stack")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            - **Language**: Python 3.11+
            - **API**: FastAPI + Uvicorn
            - **Dashboard**: Streamlit + Plotly
            - **Matching**: RapidFuzz
            """)
        with col2:
            st.markdown("""
            - **Models**: Pydantic v2
            - **Database**: SQLite
            - **Data**: Pandas + NumPy
            - **Testing**: Pytest + httpx
            """)

        st.markdown("### ⚠️ Disclaimer")
        st.warning("""
        This is a **hackathon demonstration project**. It uses synthetic data and deterministic matching.
        It is **not** production-ready financial software. Always verify reconciliation results with
        qualified finance professionals before making business decisions.
        """)
