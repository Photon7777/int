# Mixalyzer

Mixalyzer is an AI-powered marketing mix optimization platform for growth teams. It helps business users understand which marketing channels drive revenue, evaluate whether the model is reliable, simulate budget changes, optimize next-period allocation, and export stakeholder-ready recommendations.

## Business Problem

Marketing teams often spend across Google, Meta, Instagram, TV, email, promotions, and other channels without a clear view of incremental revenue impact. Last-click attribution can over-credit channels near the purchase and under-credit delayed effects, offline campaigns, seasonality, promotions, and broader business events.

Mixalyzer addresses the core business question:

> Are we overspending on channels that do not convert, and where should the next dollar go?

## Target Users

- Growth teams and marketing analysts who need channel-level ROI evidence.
- Finance teams that need budget recommendations tied to revenue and CAC.
- CMOs and executive leaders who need clear, non-technical planning guidance.
- Small-to-mid-size e-commerce, D2C, subscription, and retail companies.

## Key Features

- Polished product home page with business KPIs and an executive recommendation summary.
- Strategy tab using a Who / Why / How business-case framework.
- CSV upload with auto column mapping and data readiness checks.
- Optional external control variables for holidays, stockouts, product launches, competitor campaigns, promotion events, and macro indicators.
- Marketing mix dashboard with spend/revenue trends, contribution, ROI, CAC, and channel mix.
- Simulation tool for what-if budget changes.
- Budget optimizer for recommended next-period allocation.
- Model comparison against simple and seasonal baselines.
- Model trust badge that tells users whether to trust, caution, or reject the recommendation.
- Confidence ranges for conservative, expected, and optimistic revenue impact.
- Responsible AI audit covering privacy, fairness, reliability, hallucination, over-automation, and data quality.
- Rollout / Pilot Plan tab for a controlled business implementation.
- Executive PDF, allocation workbook, and GenAI evidence workbook exports.

## AI/ML Approach

Mixalyzer uses a Marketing Mix Modeling workflow:

1. Data collection: weekly marketing spend, revenue, customer/conversion counts, and optional event controls.
2. Data preparation: canonical schema, date parsing, numeric checks, readiness scoring, and auto-mapping.
3. Model building: Ridge MMM with adstock carryover, saturation-style spend features, trend, seasonality, and optional controls.
4. Optional Bayesian MMM: lightweight Bayesian regression with posterior-style uncertainty intervals.
5. Generative AI layer: optional OpenAI narrative generation grounded only in the evidence workbook and model outputs.

## Model Evaluation

The app compares the MMM against baselines before recommending action:

- Average baseline: predicts revenue using historical average revenue.
- Seasonality baseline: uses trend, calendar seasonality, and external controls.
- Ridge MMM: uses spend, adstock, saturation, seasonality, and controls.
- Bayesian MMM: adds uncertainty-aware prediction intervals.

The model trust badge uses MAPE and baseline comparison:

- Trust for planning: MMM beats baseline and MAPE is within the user's target.
- Use with caution: MMM beats baseline but MAPE is above the target.
- Do not use recommendation yet: baseline beats MMM.
- Insufficient data: not enough observations for holdout evaluation.

## Responsible AI

Mixalyzer is designed as decision support, not automatic media buying. The audit tab checks:

- Privacy risk from uploaded identifiers such as email, phone, name, customer_id, and user_id.
- Bias/fairness risk when channel exposure differs by region, product, audience, or segment.
- Reliability risk when MMM performs worse than baseline.
- Hallucination risk from unsupported AI-generated claims.
- Over-automation risk if teams apply budget changes without human review.
- Data quality risk from missing weeks, irregular dates, short history, or non-numeric spend.

## Final Project Alignment

Mixalyzer demonstrates the required business AI elements:

- Real business problem: wasted marketing budget and unclear incremental revenue impact.
- Specific target customer: growth, marketing, finance, and executive teams.
- AI-driven solution: MMM prediction, simulation, optimization, and grounded recommendation generation.
- Business KPIs: ROI lift, CAC reduction, revenue lift, forecast error / MAPE, and confidence range.
- Model evaluation: train/test evaluation and baseline comparison.
- Responsible AI: privacy, bias, reliability, hallucination, over-automation, and data quality controls.
- End-to-end workflow: upload data, evaluate readiness, train model, simulate, optimize, audit risks, pilot, and export.

## Demo Instructions

Run locally:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run mmx_app.py
```

The app opens with built-in sample data, so you can demo immediately. To use your own dataset, upload a CSV in the sidebar and review the auto column mapping before interpreting results.

Streamlit Cloud settings:

- Repository: `Photon7777/marketing-mix-optimizer`
- Branch: `main`
- Main file path: `mmx_app.py`

Optional Streamlit secret for AI narrative generation:

```toml
OPENAI_API_KEY = "your_key_here"
```

## Dataset Requirements

Recommended weekly columns:

```text
date
revenue
google_ads
meta_ads
instagram_ads
tv_ads
email_marketing
promotions
new_customers
```

`new_customers` is optional, but it enables CAC reporting.

Optional control columns:

```text
holiday_flag
stockout_flag
promo_event
competitor_campaign
product_launch
macro_index
```

These controls help prevent marketing channels from receiving credit or blame for external business events.

## Project Structure

```text
.
|-- marketing_mix_model.py          # Modeling, mapping, readiness, evaluation, optimization
|-- mmx_app.py                      # Streamlit Mixalyzer product UI
|-- requirements.txt
`-- tests/
    `-- test_marketing_mix_model.py
```

## Verification

Run syntax checks:

```bash
venv/bin/python -m py_compile marketing_mix_model.py mmx_app.py
```

Run tests:

```bash
venv/bin/python -m unittest discover -s tests
```

## Future Improvements

- Add more robust Bayesian MMM with hierarchical priors and MCMC sampling.
- Add geo or segment-level MMM for fairness and regional planning.
- Add experiment/lift-test calibration to validate model recommendations.
- Add automated weekly monitoring after rollout.
- Add authenticated team workspaces and saved planning scenarios.
