from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


DATE_COL = "date"
TARGET_COL = "revenue"
CUSTOMER_COL = "new_customers"

CHANNEL_LABELS: Dict[str, str] = {
    "google_ads": "Google Ads",
    "meta_ads": "Meta Ads",
    "instagram_ads": "Instagram Ads",
    "tv_ads": "TV Ads",
    "email_marketing": "Email Marketing",
    "promotions": "Promotions",
}

DEFAULT_CHANNELS = tuple(CHANNEL_LABELS.keys())

_COLUMN_ALIASES = {
    "week": DATE_COL,
    "date": DATE_COL,
    "period": DATE_COL,
    "revenue": TARGET_COL,
    "sales": TARGET_COL,
    "total_revenue": TARGET_COL,
    "customers": CUSTOMER_COL,
    "new_customers": CUSTOMER_COL,
    "customer_acquisitions": CUSTOMER_COL,
    "acquisitions": CUSTOMER_COL,
    "conversions": CUSTOMER_COL,
    "google": "google_ads",
    "google_ads": "google_ads",
    "google_ad_spend": "google_ads",
    "google_ads_spend": "google_ads",
    "search": "google_ads",
    "paid_search": "google_ads",
    "meta": "meta_ads",
    "meta_ads": "meta_ads",
    "facebook": "meta_ads",
    "facebook_ads": "meta_ads",
    "facebook_ads_spend": "meta_ads",
    "instagram": "instagram_ads",
    "instagram_ads": "instagram_ads",
    "instagram_ads_spend": "instagram_ads",
    "tv": "tv_ads",
    "tv_ads": "tv_ads",
    "tv_spend": "tv_ads",
    "email": "email_marketing",
    "email_marketing": "email_marketing",
    "email_spend": "email_marketing",
    "promotions": "promotions",
    "promotion": "promotions",
    "promo": "promotions",
    "discounts": "promotions",
    "discount_spend": "promotions",
}


@dataclass(frozen=True)
class MarketingMixModel:
    channel_cols: tuple[str, ...]
    feature_columns: tuple[str, ...]
    feature_means: pd.Series
    feature_stds: pd.Series
    coefficients: pd.Series
    intercept: float
    date_origin: pd.Timestamp
    date_span_days: int
    metrics: Dict[str, float]

    def predict(self, data: pd.DataFrame | Mapping[str, object]) -> np.ndarray:
        frame = pd.DataFrame([data]) if isinstance(data, Mapping) else data.copy()
        frame = _coerce_model_input(frame, self.channel_cols, require_revenue=False)
        features = build_feature_frame(
            frame,
            self.channel_cols,
            date_origin=self.date_origin,
            date_span_days=self.date_span_days,
        )
        features = features.reindex(columns=self.feature_columns, fill_value=0.0)
        standardized = (features - self.feature_means) / self.feature_stds
        predictions = self.intercept + np.einsum(
            "ij,j->i",
            standardized.to_numpy(dtype=float),
            self.coefficients.to_numpy(dtype=float),
        )
        return np.maximum(predictions.astype(float), 0.0)


def normalize_marketing_data(data: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with common marketing-mix column names normalized."""
    rename_map: Dict[str, str] = {}
    seen_targets = set()

    for column in data.columns:
        normalized = re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
        target = _COLUMN_ALIASES.get(normalized)
        if target and target not in seen_targets:
            rename_map[column] = target
            seen_targets.add(target)

    return data.rename(columns=rename_map).copy()


def prepare_marketing_data(
    data: pd.DataFrame,
    channel_cols: Sequence[str] = DEFAULT_CHANNELS,
    require_revenue: bool = True,
) -> pd.DataFrame:
    """Normalize columns and coerce date, spend, and revenue fields for modeling/UI use."""
    return _coerce_model_input(data, channel_cols, require_revenue=require_revenue)


def generate_sample_marketing_data(weeks: int = 156, seed: int = 42) -> pd.DataFrame:
    """Create a realistic demo dataset with seasonality and saturated channel effects."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp("2026-03-29"), periods=weeks, freq="W-SUN")
    t = np.arange(weeks)

    holiday = np.where(pd.Series(dates).dt.month.isin([11, 12]), 1.0, 0.0)
    seasonal = np.sin(2 * np.pi * t / 52)
    semiannual = np.cos(2 * np.pi * t / 26)
    trend = np.linspace(0, 1, weeks)

    google = 22_000 + 4_500 * seasonal + 4_000 * holiday + rng.normal(0, 2_100, weeks)
    meta = 17_000 + 2_800 * semiannual + 2_500 * holiday + rng.normal(0, 1_900, weeks)
    instagram = 12_500 + 2_600 * np.sin(2 * np.pi * (t + 8) / 52) + rng.normal(0, 1_600, weeks)
    tv = 28_000 + 12_000 * ((t % 13) < 4).astype(float) + rng.normal(0, 3_500, weeks)
    email = 5_800 + 1_200 * holiday + rng.normal(0, 650, weeks)
    promotions = 7_500 + 7_000 * holiday + 3_500 * ((t % 17) < 3).astype(float) + rng.normal(0, 1_200, weeks)

    channel_values = {
        "google_ads": google,
        "meta_ads": meta,
        "instagram_ads": instagram,
        "tv_ads": tv,
        "email_marketing": email,
        "promotions": promotions,
    }
    for channel, values in channel_values.items():
        channel_values[channel] = np.maximum(values, 500 if channel == "email_marketing" else 2_000)

    baseline = 138_000 + 58_000 * trend + 15_000 * seasonal + 22_000 * holiday
    revenue = (
        baseline
        + _saturated_effect(channel_values["google_ads"], scale=30_000, ceiling=112_000)
        + _saturated_effect(channel_values["meta_ads"], scale=24_000, ceiling=70_000)
        + _saturated_effect(channel_values["instagram_ads"], scale=17_000, ceiling=64_000)
        + _saturated_effect(channel_values["tv_ads"], scale=52_000, ceiling=86_000)
        + _saturated_effect(channel_values["email_marketing"], scale=7_500, ceiling=34_000)
        + _saturated_effect(channel_values["promotions"], scale=15_000, ceiling=58_000)
        + rng.normal(0, 9_000, weeks)
    )

    new_customers = np.maximum(
        450
        + revenue / 390
        + 0.0018 * google
        + 0.0022 * instagram
        + 0.0014 * meta
        + rng.normal(0, 55, weeks),
        100,
    )

    frame = pd.DataFrame(
        {
            DATE_COL: dates,
            **channel_values,
            TARGET_COL: revenue,
            CUSTOMER_COL: new_customers.round(0),
        }
    )
    return frame.round(2)


def fit_marketing_mix_model(
    data: pd.DataFrame,
    channel_cols: Sequence[str] = DEFAULT_CHANNELS,
    regularization: float = 1.5,
) -> MarketingMixModel:
    """Fit a ridge regression model on saturated spend and time features."""
    frame = _coerce_model_input(data, channel_cols, require_revenue=True)
    frame = frame.sort_values(DATE_COL).reset_index(drop=True)

    dates = pd.to_datetime(frame[DATE_COL])
    date_origin = dates.min()
    date_span_days = max(int((dates.max() - date_origin).days), 1)

    features = build_feature_frame(
        frame,
        channel_cols,
        date_origin=date_origin,
        date_span_days=date_span_days,
    )
    target = pd.to_numeric(frame[TARGET_COL], errors="coerce").astype(float)

    feature_means = features.mean()
    feature_stds = features.std(ddof=0).replace(0, 1.0)
    standardized = (features - feature_means) / feature_stds

    x_matrix = standardized.to_numpy(dtype=float)
    y_values = target.to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(standardized)), x_matrix])
    penalty = np.eye(design.shape[1]) * float(regularization)
    penalty[0, 0] = 0.0

    gram = np.einsum("ni,nj->ij", design, design)
    rhs = np.einsum("ni,n->i", design, y_values)

    try:
        weights = np.linalg.solve(gram + penalty, rhs)
    except np.linalg.LinAlgError:
        weights = np.linalg.pinv(gram + penalty) @ rhs

    intercept = float(weights[0])
    coefficients = pd.Series(weights[1:], index=features.columns, dtype=float)

    predictions = intercept + np.einsum("ij,j->i", x_matrix, coefficients.to_numpy(dtype=float))
    metrics = _regression_metrics(y_values, predictions)

    return MarketingMixModel(
        channel_cols=tuple(channel_cols),
        feature_columns=tuple(features.columns),
        feature_means=feature_means,
        feature_stds=feature_stds,
        coefficients=coefficients,
        intercept=intercept,
        date_origin=date_origin,
        date_span_days=date_span_days,
        metrics=metrics,
    )


def build_feature_frame(
    data: pd.DataFrame,
    channel_cols: Sequence[str],
    date_origin: pd.Timestamp,
    date_span_days: int,
) -> pd.DataFrame:
    frame = normalize_marketing_data(data)
    dates = pd.to_datetime(frame[DATE_COL])
    week = dates.dt.isocalendar().week.astype("int64").astype(float)
    days_since_origin = (dates - pd.Timestamp(date_origin)).dt.days.astype(float)

    features = pd.DataFrame(index=frame.index)
    features["trend"] = days_since_origin / max(int(date_span_days), 1)
    features["season_sin"] = np.sin(2 * np.pi * week / 52)
    features["season_cos"] = np.cos(2 * np.pi * week / 52)
    features["holiday_q4"] = dates.dt.month.isin([11, 12]).astype("float64")

    for channel in channel_cols:
        spend = pd.to_numeric(frame[channel], errors="coerce").fillna(0).clip(lower=0)
        features[f"log_{channel}"] = np.log1p(spend)

    return features.astype(float)


def estimate_channel_contribution(
    model: MarketingMixModel,
    data: pd.DataFrame,
) -> pd.DataFrame:
    frame = _coerce_model_input(data, model.channel_cols, require_revenue=False)
    actual_prediction = model.predict(frame)

    rows = []
    total_contribution = 0.0
    for channel in model.channel_cols:
        counterfactual = frame.copy()
        counterfactual[channel] = 0.0
        contribution = float((actual_prediction - model.predict(counterfactual)).sum())
        spend = float(pd.to_numeric(frame[channel], errors="coerce").fillna(0).sum())
        total_contribution += contribution
        rows.append(
            {
                "channel": channel,
                "Channel": CHANNEL_LABELS.get(channel, channel.replace("_", " ").title()),
                "Spend": spend,
                "Estimated Contribution": contribution,
                "ROI": contribution / spend if spend else 0.0,
            }
        )

    contribution_df = pd.DataFrame(rows)
    contribution_df["Contribution Share"] = (
        contribution_df["Estimated Contribution"] / total_contribution
        if total_contribution
        else 0.0
    )
    return contribution_df.sort_values("ROI", ascending=False).reset_index(drop=True)


def get_baseline_scenario(data: pd.DataFrame, recent_weeks: int = 4) -> Dict[str, object]:
    frame = _coerce_model_input(data, DEFAULT_CHANNELS, require_revenue=False)
    frame = frame.sort_values(DATE_COL).tail(max(int(recent_weeks), 1))
    scenario: Dict[str, object] = {
        DATE_COL: pd.to_datetime(frame[DATE_COL]).max() + pd.Timedelta(days=7)
    }
    for channel in DEFAULT_CHANNELS:
        scenario[channel] = float(pd.to_numeric(frame[channel], errors="coerce").fillna(0).mean())
    return scenario


def simulate_spend_change(
    model: MarketingMixModel,
    baseline: Mapping[str, object],
    changes_pct: Mapping[str, float],
) -> Dict[str, object]:
    current = _scenario_to_frame(baseline, model.channel_cols)
    scenario = current.copy()

    rows = []
    for channel in model.channel_cols:
        current_value = float(current.at[0, channel])
        pct_change = float(changes_pct.get(channel, 0.0))
        new_value = max(current_value * (1 + pct_change / 100), 0.0)
        scenario.at[0, channel] = new_value
        rows.append(
            {
                "channel": channel,
                "Channel": CHANNEL_LABELS.get(channel, channel),
                "Current Spend": current_value,
                "Scenario Spend": new_value,
                "Change %": pct_change,
                "Spend Shift": new_value - current_value,
            }
        )

    current_revenue = float(model.predict(current)[0])
    scenario_revenue = float(model.predict(scenario)[0])
    current_budget = _sum_budget(current.iloc[0], model.channel_cols)
    scenario_budget = _sum_budget(scenario.iloc[0], model.channel_cols)

    return {
        "current_revenue": current_revenue,
        "scenario_revenue": scenario_revenue,
        "revenue_delta": scenario_revenue - current_revenue,
        "revenue_delta_pct": _safe_pct(scenario_revenue - current_revenue, current_revenue),
        "current_budget": current_budget,
        "scenario_budget": scenario_budget,
        "budget_delta": scenario_budget - current_budget,
        "details": pd.DataFrame(rows),
    }


def build_response_curve(
    model: MarketingMixModel,
    baseline: Mapping[str, object],
    channel: str,
    multipliers: Iterable[float] | None = None,
) -> pd.DataFrame:
    if channel not in model.channel_cols:
        raise ValueError(f"Unknown channel: {channel}")

    multipliers = list(multipliers or np.linspace(0, 2.0, 21))
    base_frame = _scenario_to_frame(baseline, model.channel_cols)
    base_spend = float(base_frame.at[0, channel])
    current_revenue = float(model.predict(base_frame)[0])

    rows = []
    for multiplier in multipliers:
        scenario = base_frame.copy()
        scenario.at[0, channel] = max(base_spend * float(multiplier), 0.0)
        predicted_revenue = float(model.predict(scenario)[0])
        rows.append(
            {
                "Spend Multiplier": float(multiplier),
                "Spend": float(scenario.at[0, channel]),
                "Predicted Revenue": predicted_revenue,
                "Incremental Revenue": predicted_revenue - current_revenue,
            }
        )

    return pd.DataFrame(rows)


def optimize_budget(
    model: MarketingMixModel,
    baseline: Mapping[str, object],
    total_budget: float | None = None,
    min_multiplier: float = 0.25,
    max_multiplier: float = 2.0,
    step_count: int = 90,
) -> Dict[str, object]:
    base_frame = _scenario_to_frame(baseline, model.channel_cols)
    current_values = np.array([float(base_frame.at[0, ch]) for ch in model.channel_cols])
    current_budget = float(current_values.sum())
    budget = float(total_budget if total_budget is not None else current_budget)
    budget = max(budget, 0.0)

    lower = current_values * max(float(min_multiplier), 0.0)
    upper = np.maximum(current_values * max(float(max_multiplier), 1.0), budget / len(current_values))

    if lower.sum() > budget and lower.sum() > 0:
        allocation = lower * (budget / lower.sum())
        remaining = 0.0
    else:
        allocation = lower.copy()
        remaining = budget - float(allocation.sum())

    def predict_for(values: np.ndarray) -> float:
        scenario = base_frame.copy()
        for idx, channel_name in enumerate(model.channel_cols):
            scenario.at[0, channel_name] = float(values[idx])
        return float(model.predict(scenario)[0])

    current_alloc_prediction = predict_for(allocation)
    step = max(budget / max(int(step_count), 1), 1.0)
    iterations = 0

    while remaining > 0.01 and iterations < max(int(step_count) * 4, 1):
        iterations += 1
        best_idx = None
        best_gain_per_dollar = -np.inf
        best_amount = 0.0
        best_prediction = current_alloc_prediction

        for idx in range(len(model.channel_cols)):
            capacity = float(upper[idx] - allocation[idx])
            if capacity <= 0:
                continue
            amount = min(step, remaining, capacity)
            candidate = allocation.copy()
            candidate[idx] += amount
            candidate_prediction = predict_for(candidate)
            gain_per_dollar = (candidate_prediction - current_alloc_prediction) / amount
            if gain_per_dollar > best_gain_per_dollar:
                best_gain_per_dollar = gain_per_dollar
                best_idx = idx
                best_amount = amount
                best_prediction = candidate_prediction

        if best_idx is None or best_gain_per_dollar <= 0:
            break

        allocation[best_idx] += best_amount
        remaining -= best_amount
        current_alloc_prediction = best_prediction

    optimized_prediction = predict_for(allocation)
    baseline_prediction = predict_for(current_values)

    rows = []
    for idx, channel in enumerate(model.channel_cols):
        current_spend = float(current_values[idx])
        recommended = float(allocation[idx])
        rows.append(
            {
                "channel": channel,
                "Channel": CHANNEL_LABELS.get(channel, channel),
                "Current Spend": current_spend,
                "Recommended Spend": recommended,
                "Spend Shift": recommended - current_spend,
                "Change %": _safe_pct(recommended - current_spend, current_spend),
            }
        )

    allocation_df = pd.DataFrame(rows).sort_values("Recommended Spend", ascending=False)
    return {
        "current_budget": current_budget,
        "recommended_budget": float(allocation.sum()),
        "unallocated_budget": max(float(remaining), 0.0),
        "current_revenue": baseline_prediction,
        "optimized_revenue": optimized_prediction,
        "revenue_delta": optimized_prediction - baseline_prediction,
        "revenue_delta_pct": _safe_pct(optimized_prediction - baseline_prediction, baseline_prediction),
        "allocation": allocation_df.reset_index(drop=True),
    }


def generate_recommendations(
    contribution_df: pd.DataFrame,
    optimization: Mapping[str, object],
    simulation: Mapping[str, object] | None = None,
) -> list[str]:
    recommendations: list[str] = []
    if contribution_df.empty:
        return ["Upload more complete spend and revenue data before changing budget allocation."]

    best_roi = contribution_df.sort_values("ROI", ascending=False).iloc[0]
    weakest_roi = contribution_df.sort_values("ROI", ascending=True).iloc[0]
    allocation = optimization.get("allocation")

    if isinstance(allocation, pd.DataFrame) and not allocation.empty:
        increase = allocation.sort_values("Spend Shift", ascending=False).iloc[0]
        decrease = allocation.sort_values("Spend Shift", ascending=True).iloc[0]
        if float(increase["Spend Shift"]) > 0 and float(decrease["Spend Shift"]) < 0:
            recommendations.append(
                "Shift budget from "
                f"{decrease['Channel']} to {increase['Channel']}; the optimizer estimates "
                f"{optimization.get('revenue_delta_pct', 0.0):.1f}% revenue lift at this budget level."
            )
        elif float(optimization.get("revenue_delta", 0.0)) > 0:
            recommendations.append(
                "Keep the budget level steady but rebalance toward the channels with stronger marginal response."
            )

    recommendations.append(
        f"Protect {best_roi['Channel']} because its estimated ROI is "
        f"{float(best_roi['ROI']):.2f} revenue dollars per spend dollar."
    )

    if float(weakest_roi["ROI"]) < float(contribution_df["ROI"].median()):
        recommendations.append(
            f"Audit {weakest_roi['Channel']} creative, targeting, or saturation before adding more spend."
        )

    if simulation:
        delta = float(simulation.get("revenue_delta_pct", 0.0))
        direction = "increase" if delta >= 0 else "decrease"
        recommendations.append(
            f"The active simulation would {direction} predicted revenue by {abs(delta):.1f}%."
        )

    recommendations.append(
        "Track revenue lift, marketing ROI, and CAC together so the recommendation moves business KPIs, not only model scores."
    )
    return recommendations[:5]


def _coerce_model_input(
    data: pd.DataFrame,
    channel_cols: Sequence[str],
    require_revenue: bool,
) -> pd.DataFrame:
    frame = normalize_marketing_data(data)
    required = [DATE_COL, *channel_cols]
    if require_revenue:
        required.append(TARGET_COL)

    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    frame = frame.copy()
    frame[DATE_COL] = pd.to_datetime(frame[DATE_COL], errors="coerce")
    if frame[DATE_COL].isna().any():
        raise ValueError("Date column contains invalid dates.")

    for channel in channel_cols:
        frame[channel] = pd.to_numeric(frame[channel], errors="coerce").fillna(0).clip(lower=0)

    if require_revenue:
        frame[TARGET_COL] = pd.to_numeric(frame[TARGET_COL], errors="coerce")
        if frame[TARGET_COL].isna().any():
            raise ValueError("Revenue column contains non-numeric values.")

    if CUSTOMER_COL in frame.columns:
        frame[CUSTOMER_COL] = pd.to_numeric(frame[CUSTOMER_COL], errors="coerce").fillna(0).clip(lower=0)

    return frame


def _scenario_to_frame(
    baseline: Mapping[str, object],
    channel_cols: Sequence[str],
) -> pd.DataFrame:
    scenario = dict(baseline)
    scenario.setdefault(DATE_COL, pd.Timestamp.today().normalize())
    frame = pd.DataFrame([scenario])
    return _coerce_model_input(frame, channel_cols, require_revenue=False)


def _regression_metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict[str, float]:
    residuals = actual - predicted
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    mape = float(np.mean(np.abs(residuals / np.maximum(np.abs(actual), 1.0))) * 100)
    total_variance = float(np.sum((actual - actual.mean()) ** 2))
    residual_variance = float(np.sum(residuals**2))
    r2 = 1 - residual_variance / total_variance if total_variance else 0.0
    return {"mae": mae, "rmse": rmse, "mape": mape, "r2": float(r2)}


def _saturated_effect(spend: np.ndarray, scale: float, ceiling: float) -> np.ndarray:
    return ceiling * (1 - np.exp(-np.maximum(spend, 0) / scale))


def _sum_budget(row: pd.Series, channel_cols: Sequence[str]) -> float:
    return float(sum(float(row[channel]) for channel in channel_cols))


def _safe_pct(delta: float, base: float) -> float:
    return float((delta / base) * 100) if base else 0.0
