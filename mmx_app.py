from __future__ import annotations

from datetime import datetime
import os
from typing import Mapping

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from marketing_mix_model import (
    CHANNEL_LABELS,
    CUSTOMER_COL,
    DATE_COL,
    DEFAULT_CHANNELS,
    TARGET_COL,
    build_response_curve,
    estimate_channel_contribution,
    fit_marketing_mix_model,
    generate_recommendations,
    generate_sample_marketing_data,
    get_baseline_scenario,
    normalize_marketing_data,
    optimize_budget,
    prepare_marketing_data,
    simulate_spend_change,
)

try:
    from marketing_mix_model import DEFAULT_ADSTOCK_DECAYS
except ImportError:
    DEFAULT_ADSTOCK_DECAYS = {
        "google_ads": 0.35,
        "meta_ads": 0.40,
        "instagram_ads": 0.38,
        "tv_ads": 0.65,
        "email_marketing": 0.20,
        "promotions": 0.25,
    }

try:
    from marketing_mix_model import evaluate_model_against_baseline
except ImportError:
    def evaluate_model_against_baseline(*args, **kwargs):
        raise ValueError("Train/test evaluation requires the latest marketing_mix_model.py.")


load_dotenv()

st.set_page_config(
    page_title="Marketing Mix Optimizer",
    page_icon="MMX",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
      #MainMenu, footer {visibility: hidden;}
      .block-container {
        max-width: 1360px;
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
      }
      .metric-label {
        color: rgba(226, 232, 240, 0.72);
        font-size: 0.82rem;
        margin-bottom: 0.25rem;
      }
      .metric-value {
        color: #f8fafc;
        font-size: 1.65rem;
        font-weight: 750;
        line-height: 1.1;
      }
      .metric-delta {
        color: #38d7c1;
        font-size: 0.82rem;
        margin-top: 0.18rem;
      }
      .panel {
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.68);
        border-radius: 8px;
        padding: 1rem;
      }
      .recommendation {
        border-left: 3px solid #38d7c1;
        background: rgba(56, 215, 193, 0.08);
        padding: 0.7rem 0.8rem;
        margin-bottom: 0.65rem;
        border-radius: 6px;
        color: #e5eefb;
      }
      .hero {
        border: 1px solid rgba(148, 163, 184, 0.18);
        background:
          linear-gradient(135deg, rgba(56, 215, 193, 0.14), rgba(124, 140, 255, 0.08)),
          rgba(15, 23, 42, 0.76);
        border-radius: 8px;
        padding: 1.35rem 1.45rem;
        margin-bottom: 1rem;
      }
      .hero h2 {
        color: #f8fafc;
        font-size: 2rem;
        line-height: 1.12;
        margin: 0 0 0.45rem;
      }
      .hero p {
        color: rgba(226, 232, 240, 0.78);
        font-size: 1rem;
        margin: 0;
      }
      .feature-card {
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: rgba(15, 23, 42, 0.58);
        border-radius: 8px;
        padding: 0.9rem;
        min-height: 120px;
      }
      .feature-card h4 {
        color: #f8fafc;
        margin: 0 0 0.35rem;
      }
      .feature-card p {
        color: rgba(226, 232, 240, 0.74);
        margin: 0;
      }
      .risk-ok {
        border-left: 3px solid #38d7c1;
      }
      .risk-watch {
        border-left: 3px solid #f59e0b;
      }
      div[data-testid="stMetric"] {
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: rgba(15, 23, 42, 0.55);
        border-radius: 8px;
        padding: 0.8rem 0.95rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_sample_data() -> pd.DataFrame:
    return generate_sample_marketing_data()


@st.cache_data(show_spinner=False)
def train_model(data: pd.DataFrame, regularization: float):
    model = fit_marketing_mix_model(data, regularization=regularization)
    contribution = estimate_channel_contribution(model, data)
    baseline = get_baseline_scenario(data)
    return model, contribution, baseline


@st.cache_data(show_spinner=False)
def evaluate_current_model(data: pd.DataFrame, regularization: float):
    return evaluate_model_against_baseline(data, regularization=regularization)


def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def signed_money(value: float) -> str:
    prefix = "+" if value >= 0 else "-"
    return f"{prefix}${abs(value):,.0f}"


def dataframe_to_markdown_table(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    rows = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in frame.iterrows():
        cells = []
        for value in row:
            if isinstance(value, float):
                cells.append(f"{value:,.2f}")
            else:
                cells.append(str(value))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def prepare_uploaded_data(upload) -> pd.DataFrame:
    if upload is None:
        return load_sample_data()
    frame = pd.read_csv(upload)
    return normalize_marketing_data(frame)


def build_csv_template() -> bytes:
    template = pd.DataFrame(
        [
            {
                DATE_COL: "2026-01-04",
                "google_ads": 12000,
                "meta_ads": 9000,
                "instagram_ads": 7000,
                "tv_ads": 18000,
                "email_marketing": 2500,
                "promotions": 4500,
                TARGET_COL: 260000,
                CUSTOMER_COL: 720,
            }
        ]
    )
    return template.to_csv(index=False).encode("utf-8")


def prediction_chart(predictions: pd.DataFrame) -> alt.Chart:
    long = predictions.melt(
        id_vars=[DATE_COL],
        value_vars=["Actual Revenue", "MMX Prediction", "Baseline Prediction"],
        var_name="Series",
        value_name="Revenue",
    )
    return (
        alt.Chart(long)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(f"{DATE_COL}:T", title=None),
            y=alt.Y("Revenue:Q", title="Revenue"),
            color=alt.Color(
                "Series:N",
                scale=alt.Scale(range=["#f8fafc", "#38d7c1", "#f97316"]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip(f"{DATE_COL}:T", title="Week"),
                alt.Tooltip("Series:N"),
                alt.Tooltip("Revenue:Q", format="$,.0f"),
            ],
        )
        .properties(height=330)
    )


def evaluation_metric_chart(evaluation: Mapping[str, object]) -> alt.Chart:
    model_metrics = evaluation["model_metrics"]
    baseline_metrics = evaluation["baseline_metrics"]
    rows = [
        {"Metric": "MAPE", "Model": "MMX", "Value": model_metrics["mape"]},
        {"Metric": "MAPE", "Model": "Baseline", "Value": baseline_metrics["mape"]},
        {"Metric": "RMSE", "Model": "MMX", "Value": model_metrics["rmse"]},
        {"Metric": "RMSE", "Model": "Baseline", "Value": baseline_metrics["rmse"]},
    ]
    return (
        alt.Chart(pd.DataFrame(rows))
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Metric:N", title=None),
            y=alt.Y("Value:Q", title=None),
            color=alt.Color(
                "Model:N",
                scale=alt.Scale(range=["#38d7c1", "#f97316"]),
                legend=alt.Legend(orient="top"),
            ),
            xOffset="Model:N",
            tooltip=[alt.Tooltip("Model:N"), alt.Tooltip("Metric:N"), alt.Tooltip("Value:Q", format=",.2f")],
        )
        .properties(height=300)
    )


def build_responsible_ai_audit(
    data: pd.DataFrame,
    evaluation: Mapping[str, object] | None,
    contribution: pd.DataFrame,
) -> pd.DataFrame:
    weeks = len(data)
    spend = data[list(DEFAULT_CHANNELS)].sum()
    total_spend = float(spend.sum())
    top_channel_share = float(spend.max() / total_spend) if total_spend else 0.0
    has_customers = CUSTOMER_COL in data.columns and float(data[CUSTOMER_COL].sum()) > 0
    mape = float(evaluation["model_metrics"]["mape"]) if evaluation else None

    rows = [
        {
            "Area": "Data representativeness",
            "Status": "Watch" if weeks < 104 else "Managed",
            "Risk": "Short history can overstate recent campaigns or miss yearly seasonality.",
            "Mitigation": "Use at least two years of weekly data where possible and refresh the model monthly.",
        },
        {
            "Area": "Channel concentration",
            "Status": "Watch" if top_channel_share > 0.45 else "Managed",
            "Risk": f"The largest channel is {top_channel_share:.0%} of tracked spend.",
            "Mitigation": "Set optimizer bounds and review recommendations before making large reallocations.",
        },
        {
            "Area": "Customer privacy",
            "Status": "Managed" if has_customers else "Watch",
            "Risk": "Customer-level data may contain sensitive identifiers if raw CRM exports are uploaded.",
            "Mitigation": "Use aggregated weekly channel data only; avoid names, emails, device IDs, or protected attributes.",
        },
        {
            "Area": "Model reliability",
            "Status": "Watch" if mape is not None and mape > 10 else "Managed",
            "Risk": "Forecast error can lead to overconfident budget changes.",
            "Mitigation": "Compare against the baseline, monitor MAPE, and show best/base/worst ranges before launch.",
        },
        {
            "Area": "Recommendation hallucination",
            "Status": "Managed",
            "Risk": "Generated recommendations may sound confident even when evidence is weak.",
            "Mitigation": "Ground the AI narrative in model outputs and fall back to deterministic recommendations.",
        },
        {
            "Area": "Fairness and proxy bias",
            "Status": "Watch",
            "Risk": "Geo, audience, or platform targeting can proxy for sensitive groups even without explicit demographics.",
            "Mitigation": "Audit campaign segments outside this prototype before activating recommendations in production.",
        },
    ]

    if not contribution.empty and float(contribution["ROI"].max()) > 3 * max(float(contribution["ROI"].median()), 0.01):
        rows.append(
            {
                "Area": "Outlier ROI",
                "Status": "Watch",
                "Risk": "One channel appears much stronger than the rest, which can signal sparse data or attribution bias.",
                "Mitigation": "Validate with holdout tests or incrementality experiments before major spend shifts.",
            }
        )

    return pd.DataFrame(rows)


def build_executive_report(
    data: pd.DataFrame,
    contribution: pd.DataFrame,
    optimization: Mapping[str, object],
    simulation: Mapping[str, object],
    evaluation: Mapping[str, object] | None,
    recommendations: list[str],
) -> str:
    total_spend_value = float(data[list(DEFAULT_CHANNELS)].sum().sum())
    total_revenue_value = float(data[TARGET_COL].sum())
    total_customers_value = float(data[CUSTOMER_COL].sum()) if CUSTOMER_COL in data.columns else 0.0
    cac_value = total_spend_value / total_customers_value if total_customers_value else None
    top_roi = contribution.sort_values("ROI", ascending=False).iloc[0]
    weakest_roi = contribution.sort_values("ROI", ascending=True).iloc[0]
    allocation = optimization["allocation"][
        ["Channel", "Current Spend", "Recommended Spend", "Spend Shift", "Change %"]
    ].copy()

    lines = [
        "# Marketing Mix Optimization Executive Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Business KPI Snapshot",
        f"- Revenue analyzed: {money(total_revenue_value)}",
        f"- Marketing spend analyzed: {money(total_spend_value)}",
        f"- Marketing ROI: {total_revenue_value / total_spend_value:.2f}x" if total_spend_value else "- Marketing ROI: N/A",
        f"- CAC: {money(cac_value)}" if cac_value is not None else "- CAC: N/A",
        "",
        "## Recommended Budget Action",
        f"- Current next-period budget: {money(optimization['current_budget'])}",
        f"- Recommended next-period budget: {money(optimization['recommended_budget'])}",
        f"- Predicted revenue impact: {signed_money(optimization['revenue_delta'])} ({optimization['revenue_delta_pct']:.1f}%)",
        "",
        "## Channel Insights",
        f"- Highest estimated ROI: {top_roi['Channel']} at {float(top_roi['ROI']):.2f}x",
        f"- Lowest estimated ROI: {weakest_roi['Channel']} at {float(weakest_roi['ROI']):.2f}x",
        "",
        "## Model Evaluation",
    ]

    if evaluation:
        lines.extend(
            [
                f"- Train rows: {evaluation['train_rows']}; test rows: {evaluation['test_rows']}",
                f"- MMX MAPE: {evaluation['model_metrics']['mape']:.2f}%",
                f"- Baseline MAPE: {evaluation['baseline_metrics']['mape']:.2f}%",
                f"- RMSE improvement vs baseline: {evaluation['rmse_improvement_pct']:.1f}%",
            ]
        )
    else:
        lines.append("- Evaluation unavailable because the uploaded dataset is too short.")

    lines.extend(["", "## Active Simulation", f"- Predicted revenue impact: {signed_money(simulation['revenue_delta'])} ({simulation['revenue_delta_pct']:.1f}%)", ""])
    lines.append("## Recommended Allocation")
    lines.append(dataframe_to_markdown_table(allocation))
    lines.extend(["", "## Management Recommendations"])
    lines.extend([f"- {item}" for item in recommendations])
    lines.extend(
        [
            "",
            "## Responsible AI Notes",
            "- Treat recommendations as decision support, not automated media-buying instructions.",
            "- Validate large reallocations with incrementality tests or controlled experiments.",
            "- Use aggregated spend/revenue/customer data and avoid customer-level identifiers.",
        ]
    )
    return "\n".join(lines)


def line_spend_revenue_chart(data: pd.DataFrame) -> alt.Chart:
    frame = data.copy()
    frame["total_spend"] = frame[list(DEFAULT_CHANNELS)].sum(axis=1)
    long = frame.melt(
        id_vars=["date"],
        value_vars=[TARGET_COL, "total_spend"],
        var_name="Metric",
        value_name="Value",
    )
    long["Metric"] = long["Metric"].map({"revenue": "Revenue", "total_spend": "Marketing Spend"})

    return (
        alt.Chart(long)
        .mark_line(strokeWidth=3)
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=["#38d7c1", "#7c8cff"]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Week"),
                alt.Tooltip("Metric:N"),
                alt.Tooltip("Value:Q", format="$,.0f"),
            ],
        )
        .properties(height=320)
    )


def channel_spend_chart(data: pd.DataFrame) -> alt.Chart:
    long = data.melt(
        id_vars=["date"],
        value_vars=list(DEFAULT_CHANNELS),
        var_name="channel",
        value_name="Spend",
    )
    long["Channel"] = long["channel"].map(CHANNEL_LABELS)
    return (
        alt.Chart(long)
        .mark_area(opacity=0.88)
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("Spend:Q", stack=True, title="Weekly spend"),
            color=alt.Color("Channel:N", legend=alt.Legend(orient="bottom")),
            tooltip=[
                alt.Tooltip("date:T", title="Week"),
                alt.Tooltip("Channel:N"),
                alt.Tooltip("Spend:Q", format="$,.0f"),
            ],
        )
        .properties(height=280)
    )


def roi_chart(contribution: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(contribution)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            y=alt.Y("Channel:N", sort="-x", title=None),
            x=alt.X("ROI:Q", title="Estimated revenue per spend dollar"),
            color=alt.Color(
                "ROI:Q",
                scale=alt.Scale(range=["#f97316", "#38d7c1"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Channel:N"),
                alt.Tooltip("Spend:Q", format="$,.0f"),
                alt.Tooltip("Estimated Contribution:Q", format="$,.0f"),
                alt.Tooltip("ROI:Q", format=".2f"),
            ],
        )
        .properties(height=300)
    )


def contribution_chart(contribution: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(contribution)
        .mark_arc(innerRadius=62, outerRadius=122)
        .encode(
            theta=alt.Theta("Estimated Contribution:Q"),
            color=alt.Color("Channel:N", legend=alt.Legend(orient="bottom")),
            tooltip=[
                alt.Tooltip("Channel:N"),
                alt.Tooltip("Estimated Contribution:Q", format="$,.0f"),
                alt.Tooltip("Contribution Share:Q", format=".1%"),
            ],
        )
        .properties(height=300)
    )


def spend_shift_chart(details: pd.DataFrame, current_col: str, scenario_col: str) -> alt.Chart:
    long = details.melt(
        id_vars=["Channel"],
        value_vars=[current_col, scenario_col],
        var_name="Scenario",
        value_name="Spend",
    )
    return (
        alt.Chart(long)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Channel:N", title=None),
            y=alt.Y("Spend:Q", title="Weekly spend"),
            color=alt.Color(
                "Scenario:N",
                scale=alt.Scale(range=["#94a3b8", "#38d7c1"]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Channel:N"),
                alt.Tooltip("Scenario:N"),
                alt.Tooltip("Spend:Q", format="$,.0f"),
            ],
        )
        .properties(height=310)
    )


def response_curve_chart(curve: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(curve)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("Spend:Q", title="Weekly spend"),
            y=alt.Y("Predicted Revenue:Q", title="Predicted revenue"),
            tooltip=[
                alt.Tooltip("Spend:Q", format="$,.0f"),
                alt.Tooltip("Predicted Revenue:Q", format="$,.0f"),
                alt.Tooltip("Incremental Revenue:Q", format="$,.0f"),
            ],
        )
        .properties(height=310)
    )


def maybe_generate_openai_recommendations(
    contribution: pd.DataFrame,
    optimization: Mapping[str, object],
    simulation: Mapping[str, object],
) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        allocation = optimization["allocation"].copy()
        payload = {
            "top_roi": contribution[["Channel", "ROI", "Estimated Contribution"]].head(3).to_dict("records"),
            "recommended_allocation": allocation[
                ["Channel", "Current Spend", "Recommended Spend", "Change %"]
            ].to_dict("records"),
            "optimized_revenue_delta_pct": optimization["revenue_delta_pct"],
            "simulation_revenue_delta_pct": simulation["revenue_delta_pct"],
        }
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MMX_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a marketing analytics consultant. Give 3 concise, "
                        "actionable budget recommendations. Mention revenue, ROI, and CAC."
                    ),
                },
                {"role": "user", "content": str(payload)},
            ],
            temperature=0.35,
        )
        return response.choices[0].message.content or None
    except Exception:
        return None


with st.sidebar:
    st.title("MMX")
    uploaded = st.file_uploader("Marketing dataset", type=["csv"])
    st.download_button(
        "Download CSV template",
        data=build_csv_template(),
        file_name="marketing_mix_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    regularization = st.slider("Model regularization", 0.1, 5.0, 1.5, 0.1)
    use_openai = st.toggle("OpenAI recommendation narrative", value=False)


try:
    raw_data = prepare_uploaded_data(uploaded)
    data = prepare_marketing_data(raw_data)
    model, contribution_df, baseline_scenario = train_model(data, regularization)
except Exception as exc:
    st.error(f"Could not train the marketing mix model: {exc}")
    st.stop()

try:
    evaluation_results = evaluate_current_model(data, regularization)
except Exception:
    evaluation_results = None


total_spend = float(data[list(DEFAULT_CHANNELS)].sum().sum())
total_revenue = float(data[TARGET_COL].sum())
model_roi = float(total_revenue / total_spend) if total_spend else 0.0
total_customers = float(data[CUSTOMER_COL].sum()) if CUSTOMER_COL in data.columns else 0.0
cac = float(total_spend / total_customers) if total_customers else None

st.title("Marketing Mix Optimization Platform")

kpi_cols = st.columns(6)
kpi_cols[0].metric("Revenue", money(total_revenue))
kpi_cols[1].metric("Marketing spend", money(total_spend))
kpi_cols[2].metric("Marketing ROI", f"{model_roi:.2f}x")
kpi_cols[3].metric("CAC", money(cac) if cac is not None else "N/A")
kpi_cols[4].metric("Model R-squared", f"{model.metrics['r2']:.2f}")
kpi_cols[5].metric("MAPE", pct(model.metrics["mape"]))

tabs = st.tabs(
    [
        "Product",
        "Dashboard",
        "Simulation",
        "Optimization",
        "Evaluation",
        "Responsible AI",
        "Model",
    ]
)

with tabs[0]:
    st.markdown(
        """
        <div class="hero">
          <h2>Allocate marketing budget with evidence, not guesswork.</h2>
          <p>
            A decision-support product for growth leaders who need to identify which channels drive revenue,
            simulate budget shifts, and reduce CAC while protecting marketing ROI.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    who, why, how = st.columns(3)
    with who:
        st.markdown(
            """
            <div class="feature-card">
              <h4>Who</h4>
              <p>Marketing managers, growth teams, and finance partners managing multi-channel budgets.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with why:
        st.markdown(
            """
            <div class="feature-card">
              <h4>Why</h4>
              <p>Ad platforms report activity, but executives need revenue impact, ROI, and CAC tradeoffs.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with how:
        st.markdown(
            """
            <div class="feature-card">
              <h4>How</h4>
              <p>MMM prediction, adstock carryover, simulation, optimization, and grounded AI recommendations.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    product_cols = st.columns(4)
    product_cols[0].metric("Business objective", "ROI up")
    product_cols[1].metric("Operating KPI", "CAC down")
    product_cols[2].metric("Planning output", "Budget mix")
    product_cols[3].metric("AI approach", "Prediction + GenAI")

    feature_cols = st.columns(4)
    feature_copy = [
        ("Dashboard", "Channel contribution, spend mix, and revenue trend analysis."),
        ("Simulator", "Budget what-if scenarios with predicted revenue impact."),
        ("Optimizer", "Recommended allocation under a selected spend constraint."),
        ("Governance", "Risk controls for privacy, bias, hallucination, and model reliability."),
    ]
    for col, (title, body) in zip(feature_cols, feature_copy):
        with col:
            st.markdown(
                f"""
                <div class="feature-card">
                  <h4>{title}</h4>
                  <p>{body}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

with tabs[1]:
    left, right = st.columns([1.45, 1])
    with left:
        st.subheader("Spend and revenue trend")
        st.altair_chart(line_spend_revenue_chart(data), use_container_width=True)
    with right:
        st.subheader("Channel contribution")
        st.altair_chart(contribution_chart(contribution_df), use_container_width=True)

    chart_a, chart_b = st.columns([1, 1])
    with chart_a:
        st.subheader("ROI by channel")
        st.altair_chart(roi_chart(contribution_df), use_container_width=True)
    with chart_b:
        st.subheader("Channel spend mix")
        st.altair_chart(channel_spend_chart(data), use_container_width=True)

with tabs[2]:
    st.subheader("Budget simulation")
    sliders = {}
    slider_cols = st.columns(3)
    for idx, channel in enumerate(DEFAULT_CHANNELS):
        with slider_cols[idx % 3]:
            sliders[channel] = st.slider(
                CHANNEL_LABELS[channel],
                min_value=-60,
                max_value=80,
                value=0,
                step=5,
                format="%d%%",
            )

    simulation = simulate_spend_change(model, baseline_scenario, sliders)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Current revenue", money(simulation["current_revenue"]))
    metric_cols[1].metric(
        "Scenario revenue",
        money(simulation["scenario_revenue"]),
        pct(simulation["revenue_delta_pct"]),
    )
    metric_cols[2].metric("Budget change", money(simulation["budget_delta"]))
    metric_cols[3].metric("Scenario budget", money(simulation["scenario_budget"]))

    sim_left, sim_right = st.columns([1.1, 1])
    with sim_left:
        st.altair_chart(
            spend_shift_chart(simulation["details"], "Current Spend", "Scenario Spend"),
            use_container_width=True,
        )
    with sim_right:
        selected_channel = st.selectbox(
            "Diminishing returns channel",
            list(DEFAULT_CHANNELS),
            format_func=lambda value: CHANNEL_LABELS[value],
        )
        curve = build_response_curve(model, baseline_scenario, selected_channel)
        st.altair_chart(response_curve_chart(curve), use_container_width=True)

with tabs[3]:
    current_weekly_budget = sum(float(baseline_scenario[channel]) for channel in DEFAULT_CHANNELS)
    target_budget = st.slider(
        "Next-period marketing budget",
        min_value=float(current_weekly_budget * 0.5),
        max_value=float(current_weekly_budget * 1.5),
        value=float(current_weekly_budget),
        step=500.0,
        format="$%.0f",
    )
    optimization = optimize_budget(model, baseline_scenario, total_budget=target_budget)

    opt_cols = st.columns(4)
    opt_cols[0].metric("Current budget", money(optimization["current_budget"]))
    opt_cols[1].metric("Recommended budget", money(optimization["recommended_budget"]))
    opt_cols[2].metric(
        "Optimized revenue",
        money(optimization["optimized_revenue"]),
        pct(optimization["revenue_delta_pct"]),
    )
    opt_cols[3].metric("Unallocated", money(optimization["unallocated_budget"]))

    opt_left, opt_right = st.columns([1.2, 1])
    with opt_left:
        st.subheader("Recommended allocation")
        st.altair_chart(
            spend_shift_chart(optimization["allocation"], "Current Spend", "Recommended Spend"),
            use_container_width=True,
        )
        st.dataframe(
            optimization["allocation"][
                ["Channel", "Current Spend", "Recommended Spend", "Spend Shift", "Change %"]
            ],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Current Spend": st.column_config.NumberColumn(format="$%.0f"),
                "Recommended Spend": st.column_config.NumberColumn(format="$%.0f"),
                "Spend Shift": st.column_config.NumberColumn(format="$%.0f"),
                "Change %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
    with opt_right:
        st.subheader("AI recommendation panel")
        narrative = (
            maybe_generate_openai_recommendations(contribution_df, optimization, simulation)
            if use_openai
            else None
        )
        deterministic_recommendations = generate_recommendations(contribution_df, optimization, simulation)
        if narrative:
            st.markdown(narrative)
        else:
            for item in deterministic_recommendations:
                st.markdown(f"<div class='recommendation'>{item}</div>", unsafe_allow_html=True)

        st.divider()
        report = build_executive_report(
            data=data,
            contribution=contribution_df,
            optimization=optimization,
            simulation=simulation,
            evaluation=evaluation_results,
            recommendations=deterministic_recommendations,
        )
        st.download_button(
            "Download executive report",
            data=report.encode("utf-8"),
            file_name="marketing_mix_executive_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
        st.download_button(
            "Download allocation CSV",
            data=optimization["allocation"].to_csv(index=False).encode("utf-8"),
            file_name="recommended_budget_allocation.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tabs[4]:
    st.subheader("Train/test evaluation")
    if evaluation_results:
        eval_cols = st.columns(5)
        eval_cols[0].metric("Train rows", f"{evaluation_results['train_rows']}")
        eval_cols[1].metric("Test rows", f"{evaluation_results['test_rows']}")
        eval_cols[2].metric("MMX MAPE", pct(evaluation_results["model_metrics"]["mape"]))
        eval_cols[3].metric("Baseline MAPE", pct(evaluation_results["baseline_metrics"]["mape"]))
        eval_cols[4].metric("RMSE lift", pct(evaluation_results["rmse_improvement_pct"]))

        pred_left, pred_right = st.columns([1.35, 1])
        with pred_left:
            st.altair_chart(prediction_chart(evaluation_results["predictions"]), use_container_width=True)
        with pred_right:
            st.altair_chart(evaluation_metric_chart(evaluation_results), use_container_width=True)

        metrics_df = pd.DataFrame(
            [
                {"Metric": "R-squared", "MMX": evaluation_results["model_metrics"]["r2"], "Baseline": evaluation_results["baseline_metrics"]["r2"]},
                {"Metric": "MAE", "MMX": evaluation_results["model_metrics"]["mae"], "Baseline": evaluation_results["baseline_metrics"]["mae"]},
                {"Metric": "RMSE", "MMX": evaluation_results["model_metrics"]["rmse"], "Baseline": evaluation_results["baseline_metrics"]["rmse"]},
                {"Metric": "MAPE", "MMX": evaluation_results["model_metrics"]["mape"], "Baseline": evaluation_results["baseline_metrics"]["mape"]},
            ]
        )
        st.dataframe(
            metrics_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "MMX": st.column_config.NumberColumn(format="%.2f"),
                "Baseline": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    else:
        st.info("Upload at least 12 dated observations to show train/test evaluation.")

with tabs[5]:
    st.subheader("Responsible AI and risk audit")
    risk_df = build_responsible_ai_audit(data, evaluation_results, contribution_df)
    managed = int((risk_df["Status"] == "Managed").sum())
    watch = int((risk_df["Status"] == "Watch").sum())
    risk_cols = st.columns(4)
    risk_cols[0].metric("Managed controls", managed)
    risk_cols[1].metric("Watch items", watch)
    risk_cols[2].metric("Privacy posture", "Aggregated")
    risk_cols[3].metric("Recommendation mode", "Human review")

    for _, row in risk_df.iterrows():
        css_class = "risk-ok" if row["Status"] == "Managed" else "risk-watch"
        st.markdown(
            f"""
            <div class="feature-card {css_class}">
              <h4>{row['Area']} · {row['Status']}</h4>
              <p><strong>Risk:</strong> {row['Risk']}</p>
              <p><strong>Mitigation:</strong> {row['Mitigation']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.dataframe(risk_df, hide_index=True, use_container_width=True)

with tabs[6]:
    model_left, model_right = st.columns([1, 1])
    with model_left:
        st.subheader("Training data")
        st.dataframe(data.tail(12), hide_index=True, use_container_width=True)
        st.subheader("Adstock carryover settings")
        adstock_df = pd.DataFrame(
            [
                {
                    "Channel": CHANNEL_LABELS[channel],
                    "Carryover Decay": DEFAULT_ADSTOCK_DECAYS[channel],
                    "Interpretation": "Higher values mean spend influence lasts longer.",
                }
                for channel in DEFAULT_CHANNELS
            ]
        )
        st.dataframe(
            adstock_df,
            hide_index=True,
            use_container_width=True,
            column_config={"Carryover Decay": st.column_config.NumberColumn(format="%.2f")},
        )
    with model_right:
        st.subheader("Model diagnostics")
        diagnostics = pd.DataFrame(
            [
                {"Metric": "R-squared", "Value": model.metrics["r2"]},
                {"Metric": "MAE", "Value": model.metrics["mae"]},
                {"Metric": "RMSE", "Value": model.metrics["rmse"]},
                {"Metric": "MAPE", "Value": model.metrics["mape"]},
            ]
        )
        st.dataframe(diagnostics, hide_index=True, use_container_width=True)

        coefficients = (
            model.coefficients.rename_axis("Feature")
            .reset_index(name="Coefficient")
            .sort_values("Coefficient", ascending=False)
        )
        st.dataframe(coefficients, hide_index=True, use_container_width=True)
