from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


FUNNEL_STAGE_ORDER = ["Interested", "Applied", "OA", "Interview", "Offer"]
STATUS_DISPLAY_ORDER = ["Rejected", "Ghosted", "Interested", "Applied", "OA", "Interview", "Offer", "Unknown"]
STATUS_COLOR_DOMAIN = ["Interested", "Applied", "OA", "Interview", "Offer", "Rejected", "Ghosted", "Unknown"]
STATUS_COLOR_RANGE = ["#38bdf8", "#60a5fa", "#a78bfa", "#f59e0b", "#22c55e", "#ef4444", "#94a3b8", "#64748b"]
FOLLOW_UP_BUCKET_ORDER = ["Overdue", "Today", "Next 3 days", "Next 7 days", "Later"]
FOLLOW_UP_BUCKET_COLORS = ["#ef4444", "#f97316", "#f59e0b", "#38bdf8", "#64748b"]
FIT_FILTER_OPTIONS = ["All", "Strong fit (80+)", "Moderate fit (65-79)", "Needs review (<65)", "Unscored"]
CLOSED_STATUSES = {"Offer", "Rejected"}
STATUS_DEPTH_MAP = {
    "Rejected": 0,
    "Ghosted": 1,
    "Interested": 1,
    "Applied": 2,
    "OA": 3,
    "Interview": 4,
    "Offer": 5,
}
PRIORITY_SCORE_MAP = {
    "Apply now": 4,
    "Strong consider": 3,
    "Apply if strategic": 2,
    "Low priority": 1,
}


def _date_series(df: pd.DataFrame, column: str) -> pd.Series:
    raw = df.get(column, pd.Series([], dtype=str))
    return pd.to_datetime(raw.astype(str), errors="coerce").dt.date


def _status_series(df: pd.DataFrame) -> pd.Series:
    return df.get("Status", pd.Series([], dtype=str)).fillna("").astype(str)


def build_pipeline_funnel_df(df: pd.DataFrame) -> pd.DataFrame:
    status_series = _status_series(df)
    rows = []
    previous_count = None

    for index, stage in enumerate(FUNNEL_STAGE_ORDER):
        count = int((status_series == stage).sum())
        if index == 0:
            conversion = 100.0 if count > 0 else 0.0
            conversion_label = "Starting stage"
        elif previous_count:
            conversion = round((count / previous_count) * 100, 1)
            conversion_label = f"{conversion:.1f}% from previous stage"
        else:
            conversion = 0.0
            conversion_label = "No earlier stage volume"

        label = f"{count}" if index == 0 else f"{count}  |  {conversion:.0f}%"
        rows.append(
            {
                "Stage": stage,
                "Count": count,
                "Stage Order": index,
                "Conversion": conversion,
                "Conversion Label": conversion_label,
                "Label": label,
            }
        )
        previous_count = count

    return pd.DataFrame(rows)


def build_weekly_momentum_summary(df: pd.DataFrame, today: date | None = None) -> dict[str, int | str]:
    current_day = today or date.today()
    start_this_week = current_day - timedelta(days=current_day.weekday())
    end_this_week = start_this_week + timedelta(days=6)
    start_last_week = start_this_week - timedelta(days=7)
    end_last_week = start_this_week - timedelta(days=1)

    applied_dates = _date_series(df, "Date Applied")
    follow_up_dates = _date_series(df, "Follow-up Date")
    status_series = _status_series(df)

    applications_this_week = int(((applied_dates >= start_this_week) & (applied_dates <= end_this_week)).sum())
    applications_last_week = int(((applied_dates >= start_last_week) & (applied_dates <= end_last_week)).sum())
    followups_this_week = int(
        ((follow_up_dates >= start_this_week) & (follow_up_dates <= end_this_week) & (~status_series.isin(CLOSED_STATUSES))).sum()
    )
    followups_last_week = int(
        ((follow_up_dates >= start_last_week) & (follow_up_dates <= end_last_week) & (~status_series.isin(CLOSED_STATUSES))).sum()
    )
    interviews_active = int((status_series == "Interview").sum())
    offers_total = int((status_series == "Offer").sum())

    return {
        "week_start": start_this_week.isoformat(),
        "week_end": end_this_week.isoformat(),
        "applications_this_week": applications_this_week,
        "applications_last_week": applications_last_week,
        "followups_this_week": followups_this_week,
        "followups_last_week": followups_last_week,
        "interviews_active": interviews_active,
        "offers_total": offers_total,
    }


def build_weekly_activity_df(df: pd.DataFrame, today: date | None = None, weeks: int = 8) -> pd.DataFrame:
    current_day = today or date.today()
    current_week_start = current_day - timedelta(days=current_day.weekday())
    applied_dates = _date_series(df, "Date Applied").dropna()

    counts: dict[date, int] = {}
    for applied_date in applied_dates:
        week_start = applied_date - timedelta(days=applied_date.weekday())
        counts[week_start] = counts.get(week_start, 0) + 1

    week_starts = [current_week_start - timedelta(days=7 * offset) for offset in reversed(range(weeks))]
    rows = []
    for week_start in week_starts:
        rows.append(
            {
                "Week Start": pd.Timestamp(week_start),
                "Week Label": week_start.strftime("%b %d"),
                "Applications": counts.get(week_start, 0),
            }
        )
    return pd.DataFrame(rows)


def build_fit_outcome_df(df: pd.DataFrame) -> pd.DataFrame:
    fit_numeric = pd.to_numeric(df.get("Fit Score", pd.Series([], dtype=str)), errors="coerce")
    if fit_numeric.empty:
        return pd.DataFrame(columns=["Company", "Role", "Status", "Fit Score", "Stage Depth", "Priority", "Priority Score"])

    data = df.copy()
    data["Fit Score"] = fit_numeric
    data["Status"] = data.get("Status", pd.Series("", index=data.index)).fillna("").astype(str).replace("", "Unknown")
    data["Priority"] = data.get("Priority", pd.Series("", index=data.index)).fillna("").astype(str)
    data["Priority Score"] = data["Priority"].map(PRIORITY_SCORE_MAP).fillna(1).astype(int)
    data["Stage Depth"] = data["Status"].map(STATUS_DEPTH_MAP).fillna(0).astype(int)
    data = data[data["Fit Score"].notna()].copy()
    return data[["Company", "Role", "Status", "Fit Score", "Stage Depth", "Priority", "Priority Score"]]


def build_resume_performance_df(df: pd.DataFrame) -> pd.DataFrame:
    resume_series = df.get("Resume Used", pd.Series([], dtype=str)).fillna("").astype(str).str.strip()
    status_series = _status_series(df)
    filtered = df[resume_series != ""].copy()
    if filtered.empty:
        return pd.DataFrame(columns=["Resume", "Applications", "Interviews", "Offers", "Interview Rate"])

    filtered["Resume"] = resume_series[resume_series != ""]
    filtered["Status"] = status_series[resume_series != ""]

    rows = []
    for resume_name, group in filtered.groupby("Resume"):
        applications = len(group)
        interviews = int(group["Status"].isin({"Interview", "Offer"}).sum())
        offers = int((group["Status"] == "Offer").sum())
        interview_rate = round((interviews / applications) * 100, 1) if applications else 0.0
        rows.append(
            {
                "Resume": resume_name,
                "Applications": applications,
                "Interviews": interviews,
                "Offers": offers,
                "Interview Rate": interview_rate,
            }
        )

    summary = pd.DataFrame(rows)
    return summary.sort_values(["Applications", "Interviews", "Offers", "Interview Rate"], ascending=[False, False, False, False])


def pick_best_resume_summary(resume_performance_df: pd.DataFrame) -> dict[str, object] | None:
    if resume_performance_df.empty:
        return None

    reliable = resume_performance_df[resume_performance_df["Applications"] >= 2].copy()
    candidate = reliable if not reliable.empty else resume_performance_df
    row = candidate.sort_values(["Interview Rate", "Applications"], ascending=[False, False]).iloc[0]
    return {
        "Resume": str(row["Resume"]),
        "Applications": int(row["Applications"]),
        "Interviews": int(row["Interviews"]),
        "Offers": int(row["Offers"]),
        "Interview Rate": float(row["Interview Rate"]),
    }


def build_follow_up_timeline_df(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    current_day = today or date.today()
    follow_up_dates = _date_series(df, "Follow-up Date")
    status_series = _status_series(df)
    valid_dates = follow_up_dates[(follow_up_dates.notna()) & (~status_series.isin(CLOSED_STATUSES))]

    counts = {bucket: 0 for bucket in FOLLOW_UP_BUCKET_ORDER}
    for follow_up_date in valid_dates:
        if follow_up_date < current_day:
            counts["Overdue"] += 1
        elif follow_up_date == current_day:
            counts["Today"] += 1
        elif follow_up_date <= current_day + timedelta(days=3):
            counts["Next 3 days"] += 1
        elif follow_up_date <= current_day + timedelta(days=7):
            counts["Next 7 days"] += 1
        else:
            counts["Later"] += 1

    rows = []
    for index, bucket in enumerate(FOLLOW_UP_BUCKET_ORDER):
        rows.append(
            {
                "Bucket": bucket,
                "Count": counts[bucket],
                "Bucket Order": index,
                "Color": FOLLOW_UP_BUCKET_COLORS[index],
            }
        )
    return pd.DataFrame(rows)


def build_dashboard_trend_badges(
    weekly_momentum: dict[str, int | str],
    funnel_df: pd.DataFrame,
    follow_up_timeline_df: pd.DataFrame,
    resume_performance_df: pd.DataFrame,
) -> list[dict[str, str]]:
    app_delta = int(weekly_momentum["applications_this_week"]) - int(weekly_momentum["applications_last_week"])
    if app_delta > 0:
        app_badge = {
            "label": "Application pace",
            "value": f"Up {app_delta} vs last week",
            "tone": "positive",
        }
    elif app_delta < 0:
        app_badge = {
            "label": "Application pace",
            "value": f"Down {abs(app_delta)} vs last week",
            "tone": "warn",
        }
    else:
        app_badge = {
            "label": "Application pace",
            "value": "Flat week over week",
            "tone": "neutral",
        }

    followup_delta = int(weekly_momentum["followups_this_week"]) - int(weekly_momentum["followups_last_week"])
    if followup_delta > 0:
        followup_badge = {
            "label": "Follow-up pressure",
            "value": f"{followup_delta} more due this week",
            "tone": "warn",
        }
    elif followup_delta < 0:
        followup_badge = {
            "label": "Follow-up pressure",
            "value": f"{abs(followup_delta)} fewer due this week",
            "tone": "positive",
        }
    else:
        followup_badge = {
            "label": "Follow-up pressure",
            "value": "Steady vs last week",
            "tone": "neutral",
        }

    applied_count = int(funnel_df.loc[funnel_df["Stage"] == "Applied", "Count"].iloc[0]) if not funnel_df.empty else 0
    interview_count = int(funnel_df.loc[funnel_df["Stage"] == "Interview", "Count"].iloc[0]) if not funnel_df.empty else 0
    applied_to_interview = round((interview_count / applied_count) * 100, 1) if applied_count else 0.0
    conversion_badge = {
        "label": "Applied to interview",
        "value": f"{applied_to_interview}% conversion",
        "tone": "accent" if applied_to_interview >= 20 else "neutral",
    }

    next_seven_days = int(
        follow_up_timeline_df[
            follow_up_timeline_df["Bucket"].isin(["Overdue", "Today", "Next 3 days", "Next 7 days"])
        ]["Count"].sum()
    )
    workload_badge = {
        "label": "Next 7 days",
        "value": f"{next_seven_days} follow-up item(s)",
        "tone": "warn" if next_seven_days > 0 else "positive",
    }

    best_resume = pick_best_resume_summary(resume_performance_df)
    if best_resume:
        resume_badge = {
            "label": "Best resume",
            "value": f"{best_resume['Resume']} · {best_resume['Interview Rate']:.1f}% interview rate",
            "tone": "accent",
        }
    else:
        resume_badge = {
            "label": "Best resume",
            "value": "Log resume usage to compare versions",
            "tone": "neutral",
        }

    return [app_badge, followup_badge, conversion_badge, workload_badge, resume_badge]


def filter_tracker_rows(
    df: pd.DataFrame,
    *,
    status_filter: list[str] | None = None,
    priority_filter: list[str] | None = None,
    company_search: str = "",
    role_search: str = "",
    followup_filter: str = "All",
    fit_filter: str = "All",
) -> pd.DataFrame:
    filtered = df.copy()

    if status_filter:
        filtered = filtered[filtered["Status"].isin(status_filter)]
    if priority_filter:
        filtered = filtered[filtered["Priority"].isin(priority_filter)]
    if company_search:
        filtered = filtered[filtered["Company"].astype(str).str.contains(company_search, case=False, na=False)]
    if role_search:
        filtered = filtered[filtered["Role"].astype(str).str.contains(role_search, case=False, na=False)]

    if followup_filter == "Overdue only":
        filtered = filtered[filtered["_overdue"]]
    elif followup_filter == "Due today only":
        filtered = filtered[filtered["_due_today"]]

    fit_numeric = pd.to_numeric(filtered.get("Fit Score", pd.Series([], dtype=str)), errors="coerce")
    if fit_filter == "Strong fit (80+)":
        filtered = filtered[fit_numeric >= 80]
    elif fit_filter == "Moderate fit (65-79)":
        filtered = filtered[(fit_numeric >= 65) & (fit_numeric < 80)]
    elif fit_filter == "Needs review (<65)":
        filtered = filtered[fit_numeric < 65]
    elif fit_filter == "Unscored":
        filtered = filtered[fit_numeric.isna()]

    return filtered
