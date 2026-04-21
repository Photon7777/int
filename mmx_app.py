from __future__ import annotations

import os
from typing import Mapping

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from marketing_mix_model import (
    CHANNEL_LABELS,
    CUSTOMER_COL,
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
      #MainMenu, footer, header {visibility: hidden;}
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


def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def prepare_uploaded_data(upload) -> pd.DataFrame:
    if upload is None:
        return load_sample_data()
    frame = pd.read_csv(upload)
    return normalize_marketing_data(frame)


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
    regularization = st.slider("Model regularization", 0.1, 5.0, 1.5, 0.1)
    use_openai = st.toggle("OpenAI recommendation narrative", value=False)


try:
    raw_data = prepare_uploaded_data(uploaded)
    data = prepare_marketing_data(raw_data)
    model, contribution_df, baseline_scenario = train_model(data, regularization)
except Exception as exc:
    st.error(f"Could not train the marketing mix model: {exc}")
    st.stop()


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

tabs = st.tabs(["Dashboard", "Simulation", "Optimization", "Model"])

with tabs[0]:
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

with tabs[1]:
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

with tabs[2]:
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
        if narrative:
            st.markdown(narrative)
        else:
            for item in generate_recommendations(contribution_df, optimization, simulation):
                st.markdown(f"<div class='recommendation'>{item}</div>", unsafe_allow_html=True)

with tabs[3]:
    model_left, model_right = st.columns([1, 1])
    with model_left:
        st.subheader("Training data")
        st.dataframe(data.tail(12), hide_index=True, use_container_width=True)
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
