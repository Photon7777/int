from __future__ import annotations

from datetime import datetime
from pathlib import Path
from textwrap import dedent

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"
PDF_PATH = OUT_DIR / "mixalyzer_final_submission_guide.pdf"
MD_PATH = OUT_DIR / "mixalyzer_final_submission_guide.md"

TEAL = colors.HexColor("#0F766E")
TEAL_DARK = colors.HexColor("#115E59")
NAVY = colors.HexColor("#0F172A")
SLATE = colors.HexColor("#334155")
LIGHT = colors.HexColor("#F8FAFC")
MUTED = colors.HexColor("#64748B")
GOLD = colors.HexColor("#F59E0B")
BLUE = colors.HexColor("#4F46E5")
RED = colors.HexColor("#DC2626")


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=29,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontSize=11,
            leading=16,
            textColor=SLATE,
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=TEAL_DARK,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=SLATE,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontSize=9.4,
            leading=13.2,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontSize=8.2,
            leading=11.2,
            textColor=SLATE,
        ),
        "table": ParagraphStyle(
            "Table",
            parent=base["BodyText"],
            fontSize=7.9,
            leading=10.6,
            textColor=colors.HexColor("#1F2937"),
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.6,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontSize=9.2,
            leading=13,
            textColor=NAVY,
            leftIndent=4,
            rightIndent=4,
        ),
    }


STYLES = build_styles()


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def bullets(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, "body"), leftIndent=12) for item in items],
        bulletType="bullet",
        leftIndent=14,
        bulletFontName="Helvetica",
        bulletFontSize=7,
    )


def table(rows: list[list[str]], widths: list[float], font_size: float = 7.9) -> Table:
    header = [p(str(cell), "table_header") for cell in rows[0]]
    body_style = ParagraphStyle(
        f"Table{font_size}",
        parent=STYLES["table"],
        fontSize=font_size,
        leading=font_size + 2.4,
    )
    formatted = [header] + [[Paragraph(str(cell), body_style) for cell in row] for row in rows[1:]]
    built = Table(formatted, colWidths=widths, repeatRows=1, splitByRow=True)
    built.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return built


def callout(title: str, text: str, tone: str = "teal") -> Table:
    palette = {
        "teal": (colors.HexColor("#CCFBF1"), TEAL_DARK),
        "gold": (colors.HexColor("#FEF3C7"), colors.HexColor("#92400E")),
        "blue": (colors.HexColor("#E0E7FF"), colors.HexColor("#3730A3")),
        "red": (colors.HexColor("#FEE2E2"), colors.HexColor("#991B1B")),
    }
    background, border = palette.get(tone, palette["teal"])
    content = [[p(f"<b>{title}</b><br/>{text}", "callout")]]
    built = Table(content, colWidths=[6.7 * inch])
    built.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return built


def header_footer(canvas, doc):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(TEAL)
    canvas.roundRect(0.55 * inch, height - 0.48 * inch, 0.22 * inch, 0.22 * inch, 0.05 * inch, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.setFillColor(NAVY)
    canvas.drawString(0.84 * inch, height - 0.34 * inch, "Mixalyzer Final Submission Guide")
    canvas.setFont("Helvetica", 7.8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - 0.55 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.4)
    canvas.line(0.55 * inch, height - 0.55 * inch, width - 0.55 * inch, height - 0.55 * inch)
    canvas.restoreState()


def section_title(story: list, title: str, intro: str | None = None):
    story.append(p(title, "h1"))
    if intro:
        story.append(p(intro, "body"))


def add_title_page(story: list):
    story.append(Spacer(1, 0.45 * inch))
    story.append(p("Mixalyzer", "title"))
    story.append(
        p(
            "AI-Powered Marketing Mix Optimization for Growth Teams<br/>Final Submission Guide",
            "subtitle",
        )
    )
    story.append(callout(
        "Purpose",
        "This guide explains MMM/MMX, shows how to use the Mixalyzer app, and provides a final presentation narrative aligned to the Week 1 Harnessing AI for Business project requirements.",
        "teal",
    ))
    story.append(Spacer(1, 0.16 * inch))
    story.append(
        table(
            [
                ["Project Element", "Mixalyzer Answer"],
                ["Real business problem", "Marketing teams waste budget when channel decisions rely on last-click attribution, gut feeling, or incomplete ROI analysis."],
                ["Existing market", "Growth, e-commerce, D2C, subscription, retail, marketing analytics, finance, and CMO planning workflows already spend heavily on media measurement."],
                ["AI-driven solution", "Predictive MMM estimates channel response; optimization recommends allocation; grounded GenAI translates evidence into stakeholder-ready recommendations."],
                ["Business KPIs", "Revenue lift, marketing ROI lift, CAC reduction, forecast error / MAPE, confidence range, and conversion volume."],
                ["Responsible AI", "Privacy, fairness, reliability, hallucination, over-automation, and data quality checks are built into the workflow."],
            ],
            [1.55 * inch, 5.15 * inch],
            8.2,
        )
    )
    story.append(Spacer(1, 0.18 * inch))
    story.append(p(f"Generated: {datetime.now().strftime('%B %d, %Y')}", "small"))
    story.append(PageBreak())


def add_mmm_section(story: list):
    section_title(
        story,
        "1. What MMM / MMX Is",
        "Marketing Mix Modeling, often shortened to MMM or MMX, is a business analytics method for estimating how different marketing activities contribute to sales or revenue over time.",
    )
    story.append(callout(
        "Simple definition",
        "MMM asks: when revenue moved up or down, how much of that movement appears connected to each marketing channel after accounting for seasonality, promotions, delayed effects, and external events?",
        "blue",
    ))
    story.append(p("Businesses use MMM because marketing budgets are large, channels interact with each other, and many effects are delayed. It helps leaders decide where to protect spend, where to reduce waste, and where a controlled test or pilot is needed before scaling.", "body"))
    story.append(p("MMM is especially useful when last-click attribution is incomplete. Last-click gives credit to the final touch before conversion. MMM looks at aggregate patterns over time, including offline media, brand effects, promotions, holidays, macro conditions, stockouts, and delayed channel response.", "body"))
    story.append(
        table(
            [
                ["Topic", "Business Meaning", "Mixalyzer Example"],
                ["MMM / MMX", "A model that estimates the relationship between channel spend and revenue over time.", "Ridge MMM or Bayesian MMM predicts revenue from weekly spend, seasonality, adstock, saturation-style features, and controls."],
                ["Required data", "Weekly date, revenue, and spend by channel. Customer/conversion counts improve CAC reporting.", "date, revenue, Google Ads, Meta, Instagram, TV, email, promotions, new_customers."],
                ["Optional controls", "External variables that explain business events not caused by marketing.", "holiday_flag, stockout_flag, promo_event, competitor_campaign, product_launch, macro_index."],
                ["Channel contribution", "Estimated revenue associated with each channel in the model.", "A channel may contribute a large revenue share but still have weak efficiency if spend is also very high."],
                ["ROI", "Revenue contribution per marketing dollar spent.", "ROI of 3.0x means the model estimates three dollars of contribution per one dollar of spend."],
                ["CAC", "Customer acquisition cost: marketing spend divided by customers or conversions.", "If customer counts are uploaded, Mixalyzer estimates whether optimization improves CAC."],
                ["MAPE", "Mean Absolute Percentage Error; average forecast error as a percent.", "Lower MAPE means the model is more reliable for planning."],
                ["Adstock", "Delayed carryover effect from marketing spend.", "TV or brand spend may influence sales for several weeks, not only the week it runs."],
                ["Saturation / diminishing returns", "The idea that each extra dollar eventually produces less incremental revenue.", "A response curve flattens when additional spend is less productive."],
                ["Confidence range", "A conservative-to-optimistic estimate around predicted impact.", "If conservative lift is negative, use a pilot instead of a full rollout."],
            ],
            [1.15 * inch, 2.65 * inch, 2.9 * inch],
            7.45,
        )
    )
    story.append(p("Important caveat: MMM supports decision-making, but it does not prove perfect causality by itself. The best use is to combine MMM with business context, controlled pilots, incrementality tests, and human review.", "body"))
    story.append(callout(
        "How to explain this to stakeholders",
        "MMM is not a magic answer machine. It is a planning tool that turns historical spend and revenue patterns into better budget decisions, with clear uncertainty and risk controls.",
        "gold",
    ))
    story.append(PageBreak())


APP_SECTION_ROWS = [
    ["App Section", "What To Look At", "Business Question", "Good Result", "Warning Signs / Decision Use"],
    ["Home / Landing", "Product story, KPIs, executive recommendation summary, brand positioning.", "What problem does Mixalyzer solve and for whom?", "Clear target customer, measurable KPIs, credible recommendation framing.", "If the business problem is unclear, the project feels technical instead of strategic."],
    ["Strategy", "Who / Why / How, competitive advantage, integrated AI workflow.", "Why does this matter in an existing market?", "Specific users, market pain, and measurable value are easy to explain.", "Avoid vague claims like a platform for everyone."],
    ["Business Goals", "ROI lift target, CAC reduction target, maximum acceptable MAPE.", "What business metric should improve?", "Targets are explicit before looking at model output.", "If goals are not defined, model accuracy is not connected to business value."],
    ["Data Setup", "Readiness score, column mapping, optional control variables.", "Is the data reliable enough to model?", "Required fields mapped, clean dates, enough weekly history, numeric spend/revenue.", "Short history, missing spend, duplicate dates, unmapped columns, no controls for known business events."],
    ["Dashboard", "Revenue/spend trends, contribution, ROI, spend mix, CAC.", "What happened historically and which channels look efficient?", "Channel insights are connected to contribution and ROI, not only spend size.", "A high contribution channel may still be overfunded if ROI is weak."],
    ["Simulation", "What-if spend sliders and conservative/expected/optimistic impact.", "What might happen if we change spend?", "Scenario shows plausible positive expected impact and clear uncertainty.", "Negative conservative case means use a pilot or gather better data."],
    ["Optimization", "Recommended allocation, KPI impact, AI recommendation panel.", "What budget should we use next?", "Optimizer reallocates toward stronger marginal-response channels with clear KPI movement.", "Do not accept the recommendation if model trust is weak or baseline beats MMM."],
    ["Evaluation", "Model comparison, baseline comparison, MAPE, RMSE, trust badge.", "Can we trust the model for planning?", "MMM beats baseline and MAPE is below the selected target.", "If baseline wins, the recommendation should not drive budget yet."],
    ["Responsible AI", "Privacy, fairness, reliability, hallucination, over-automation, data quality.", "What could go wrong and how do we reduce risk?", "Risks are identified with mitigation and status labels.", "Privacy identifiers, segment bias, hallucination risk, and weak data need review."],
    ["Pilot Plan", "Pilot duration, channels to increase/decrease, KPIs to monitor, stop-loss rules.", "How do we implement safely?", "A four-week monitored pilot with weekly KPI review and stop-loss rules.", "Do not jump from model output to permanent media buying without human review."],
    ["Model", "Training data, coefficients, adstock settings, diagnostics, controls included.", "What is inside the model?", "Feature logic is explainable enough for a business stakeholder.", "Unstable coefficients or missing controls should trigger caution."],
]


def add_app_guide_section(story: list):
    section_title(
        story,
        "2. How To Use The Mixalyzer App",
        "This section is written as a step-by-step analyst guide. The goal is not simply to produce charts; the goal is to turn data into a defensible marketing budget recommendation.",
    )
    story.append(p("Recommended workflow:", "h2"))
    story.append(
        table(
            [
                ["Step", "Action", "Output"],
                ["1", "Open the Streamlit app or run it locally.", "Landing page with business problem, target customer, and KPI summary."],
                ["2", "Upload weekly marketing data or use sample data.", "Dataset ready for column mapping and readiness checks."],
                ["3", "Review data readiness and column mapping.", "Confidence that the model is using the right fields."],
                ["4", "Set KPI targets.", "ROI lift, CAC reduction, and MAPE threshold define what success means."],
                ["5", "Review model evaluation.", "MMM is compared with baseline models before recommendations are trusted."],
                ["6", "Analyze dashboard insights.", "Historical trends, contribution, ROI, CAC, and spend mix."],
                ["7", "Run simulations.", "Expected revenue impact and confidence range for budget changes."],
                ["8", "Use optimization.", "Recommended next-period budget allocation and KPI impact."],
                ["9", "Review responsible AI and pilot plan.", "Risk controls and implementation guardrails."],
                ["10", "Export outputs.", "Executive PDF, allocation workbook, and evidence workbook for stakeholders."],
            ],
            [0.45 * inch, 3.1 * inch, 3.15 * inch],
            7.8,
        )
    )
    story.append(Spacer(1, 6))
    story.append(p("Section-by-section interpretation guide:", "h2"))
    story.append(table(APP_SECTION_ROWS, [0.95 * inch, 1.45 * inch, 1.35 * inch, 1.3 * inch, 1.65 * inch], 6.7))
    story.append(PageBreak())
    story.append(p("Decision rules for beginner analysts", "h2"))
    story.append(
        table(
            [
                ["Situation", "What It Means", "Recommended Action"],
                ["MMM beats baseline and MAPE is within target", "The model is useful for planning.", "Use optimization as a pilot recommendation, not an automatic permanent budget change."],
                ["MMM beats baseline but MAPE is above target", "The model adds signal but error is high.", "Use caution, narrow the pilot, and improve data quality."],
                ["Baseline beats MMM", "The model does not yet add enough value.", "Do not use the recommendation. Improve features, add controls, or gather more history."],
                ["Conservative impact range is negative", "Uncertainty is meaningful.", "Pilot the change instead of rolling out fully."],
                ["CAC data is missing", "Cost efficiency cannot be fully measured.", "Upload customer/conversion counts or treat CAC claims as unavailable."],
                ["Privacy identifiers are detected", "Uploaded data may be too granular.", "Remove identifiers before sharing or exporting."],
            ],
            [1.75 * inch, 2.35 * inch, 2.6 * inch],
            7.6,
        )
    )
    story.append(callout(
        "How to use outputs in decision-making",
        "The best recommendation is not the channel with the prettiest chart. It is the budget move that improves business KPIs, has acceptable model trust, includes uncertainty, and can be tested safely.",
        "teal",
    ))
    story.append(p("Suggested stakeholder export package:", "h2"))
    story.append(bullets([
        "Executive PDF: use for leadership and presentation backup.",
        "Allocation workbook: use for finance and marketing planning.",
        "Evidence workbook: use to show that GenAI recommendations are grounded in model outputs.",
        "Pilot plan: use for implementation and weekly monitoring.",
    ]))
    story.append(PageBreak())


PRESENTATION_ROWS = [
    ["Presentation Part", "Main Message", "What To Show"],
    ["Opening hook", "Marketing teams waste money when budget decisions rely only on last-click attribution or gut feeling.", "A simple statement of wasted spend and unclear channel ROI."],
    ["Business problem", "Leaders need to know which channels drive incremental revenue and how to allocate the next budget.", "Current pain: fragmented attribution, delayed effects, seasonality, offline media, and finance pressure."],
    ["Target customer and market", "Growth teams, marketing analysts, finance teams, CMOs, and D2C/e-commerce companies already have this pain.", "Who / Why / How and existing market."],
    ["Why AI is appropriate", "MMM learns response patterns, optimization chooses budget allocation, and GenAI translates evidence.", "Integrated workflow, not a standalone chatbot."],
    ["Product overview", "Mixalyzer is a decision-support platform for marketing budget optimization.", "Landing page and product identity."],
    ["Dataset and pipeline", "The app ingests weekly spend/revenue data, maps columns, checks readiness, and includes external controls.", "Data Setup tab."],
    ["AI/ML approach", "Ridge/Bayesian MMM predicts revenue using adstock, saturation, trend, seasonality, and controls.", "Model tab and Evaluation tab."],
    ["Model evaluation", "The model is compared against baselines using business-relevant forecast error.", "Trust badge, MAPE, RMSE, baseline comparison."],
    ["Business KPIs", "Success is ROI lift, CAC reduction, revenue lift, MAPE, confidence range, and conversion volume.", "Business Goals tab."],
    ["Demo walkthrough", "Move from upload to readiness, dashboard, simulation, optimization, AI recommendation, risk audit, and pilot plan.", "Streamlit app tabs."],
    ["Responsible AI", "Privacy, fairness, reliability, hallucination, over-automation, and data quality risks are audited.", "Responsible AI tab."],
    ["Rollout plan", "Recommendations become a controlled four-week pilot with stop-loss rules.", "Pilot Plan tab."],
    ["Strategic value", "Mixalyzer creates faster planning cycles, transparent decisions, and stronger marketing-finance alignment.", "Strategy tab and closing slide."],
]


SCRIPT_ROWS = [
    ["Part", "Speaker Script"],
    ["Opening hook", "Every marketing team faces the same uncomfortable question: are we spending more on channels that look good in dashboards than on channels that actually drive incremental revenue? Mixalyzer answers that question with a working AI decision-support product."],
    ["Business problem", "Traditional attribution tools often over-focus on the last click. That misses delayed media effects, seasonality, promotions, offline channels, and diminishing returns. The result is budget waste and weak alignment between marketing and finance."],
    ["Target customer", "Our primary users are marketing analysts, growth managers, finance partners, and CMOs at small-to-mid-size e-commerce, D2C, subscription, and retail companies. These teams already spend real money on paid media and need better planning evidence."],
    ["Why AI", "AI is appropriate because this is a pattern-learning and decision-support problem. The model learns response patterns from historical spend and revenue. The optimizer recommends allocation under constraints. The generative layer translates the evidence into executive language."],
    ["Product demo transition", "Now I will show the product workflow from a beginner analyst's perspective: upload data, check readiness, evaluate the model, explore insights, simulate changes, optimize budget, review risk, and export recommendations."],
    ["Data setup demo", "Here, Mixalyzer maps uploaded columns into the MMM schema and checks whether the data is ready. This matters because bad data can make marketing channels receive credit or blame for events they did not cause."],
    ["Evaluation demo", "Before trusting recommendations, Mixalyzer compares MMM to baseline models. If MMM does not beat the baseline or if MAPE is too high, the app warns the user not to rely on the recommendation yet."],
    ["Dashboard demo", "The dashboard separates contribution from efficiency. A channel can contribute a lot because it receives a lot of spend, but ROI tells us whether that spend appears efficient."],
    ["Simulation and optimization demo", "Simulation asks what happens if we change spend. Optimization asks what budget should we use next. The app gives expected impact and a confidence range, so we do not overstate certainty."],
    ["AI recommendation demo", "This is not a chatbot. The recommendation is generated from a structured evidence packet: model metrics, baseline comparison, channel ROI, KPI scorecard, confidence range, and risk audit. If the evidence is weak, the recommendation becomes cautious."],
    ["Responsible AI demo", "The risk audit checks privacy, fairness, reliability, hallucination, over-automation, and data quality. This aligns the model with human review and responsible business deployment."],
    ["Closing", "Mixalyzer turns marketing analytics into a repeatable planning workflow. It improves budget allocation, shortens planning cycles, and gives executives a clearer connection between marketing spend and business KPIs."],
]


def add_presentation_section(story: list):
    section_title(
        story,
        "3. Final Presentation Narrative Flow",
        "The Week 1 project guidance emphasizes business value, existing market, a trained and evaluated AI model, a working product, business KPIs, strategic analysis, and responsible AI. The narrative below is designed to hit those points naturally.",
    )
    story.append(table(PRESENTATION_ROWS, [1.25 * inch, 3.05 * inch, 2.4 * inch], 7.35))
    story.append(PageBreak())
    story.append(p("Speaker script", "h1"))
    story.append(p("Use this as a natural pitch script. Keep it conversational; the app demo should feel like a business workflow, not a code walkthrough.", "body"))
    for part, script in SCRIPT_ROWS[1:]:
        story.append(KeepTogether([p(part, "h3"), p(script, "body")]))
    story.append(Spacer(1, 7))
    story.append(p("How to answer: Why is this not just a chatbot or API wrapper?", "h2"))
    story.append(callout(
        "Answer",
        "The central AI is the trained MMM model and optimizer. The app trains/evaluates a predictive model, compares it to baselines, estimates channel contribution, runs simulations, and optimizes budget. GenAI is only a translation layer that consumes the evidence packet. The product still works without an API key because the evidence-based recommendation logic is built into the app.",
        "blue",
    ))
    story.append(p("How to answer: Why is the AI implementation natural and not forced?", "h2"))
    story.append(bullets([
        "Marketing budget planning is a prediction and optimization problem, so an ML model is central to the workflow.",
        "Executives need understandable recommendations, so GenAI creates value by translating technical outputs into stakeholder language.",
        "The generative layer is grounded in model outputs, KPI results, confidence ranges, and the risk audit.",
        "Human review remains required through the responsible AI audit and pilot plan.",
    ]))
    story.append(PageBreak())


RUBRIC_ROWS = [
    ["Rubric Category", "Course Expectation", "How Mixalyzer Satisfies It", "Evidence To Show"],
    ["Presentation and Research", "Business sector analysis, AI impact, Who / Why / How framework.", "Targets growth, finance, CMO, D2C/e-commerce, subscription, and retail teams in an existing marketing analytics market.", "Strategy tab, final guide, presentation narrative."],
    ["Landing Page and Business Product", "Business context, value proposition, public-facing landing page, meaningful model outputs.", "Branded Mixalyzer landing page explains business problem, KPIs, target customer, and product workflow.", "Home tab, logo/hero assets, KPI cards."],
    ["AI Model Implementation and Evaluation", "Industry-relevant model, performance evaluation, business metrics, baseline comparison.", "Ridge/Bayesian MMM trained on weekly data; evaluated with MAPE/RMSE/R2 and compared to average/seasonality baselines.", "Evaluation tab, Model tab, trust badge."],
    ["End-to-End Integration", "Working UI integrated with model pipeline and business application.", "Data upload -> readiness -> MMM -> baseline comparison -> dashboard -> simulation -> optimization -> evidence packet -> AI recommendation -> risk audit -> pilot plan -> exports.", "Full Streamlit demo and exported PDF/workbooks."],
    ["Responsible AI and Critical Analysis", "Bias, fairness, privacy, ethics, failure scenarios, mitigation.", "Audit table covers privacy, fairness, reliability, hallucination, over-automation, and data quality with status indicators.", "Responsible AI tab and pilot plan."],
]


def add_rubric_section(story: list):
    section_title(
        story,
        "4. Rubric Mapping and Submission Checklist",
        "This section maps Mixalyzer directly to the final project expectations from the Week 1 course guidance.",
    )
    story.append(table(RUBRIC_ROWS, [1.25 * inch, 1.55 * inch, 2.65 * inch, 1.25 * inch], 6.75))
    story.append(Spacer(1, 8))
    story.append(p("Submission checklist", "h2"))
    story.append(bullets([
        "PowerPoint slides explain the business problem, target customer, AI approach, model evaluation, KPIs, responsible AI, and strategic value.",
        "Recorded presentation includes a live product demo or a demo video of Mixalyzer.",
        "Project report or PDF guide explains MMM, app usage, presentation story, and rubric alignment.",
        "Code repository includes the Streamlit app, model logic, tests, README, and assets.",
        "Exports from the app include executive report, allocation workbook, and evidence workbook.",
        "Responsible AI section is discussed during the presentation, not left as an appendix only.",
    ]))
    story.append(callout(
        "Final recommendation",
        "Pitch Mixalyzer as an AI decision-support product for marketing budget optimization. The strongest story is business-first: wasted spend is the problem, MMM is the predictive engine, optimization creates the recommendation, GenAI makes it executive-ready, and responsible AI keeps the rollout safe.",
        "teal",
    ))


def build_markdown() -> str:
    def md_table(rows: list[list[str]]) -> list[str]:
        header = "| " + " | ".join(rows[0]) + " |"
        divider = "| " + " | ".join(["---"] * len(rows[0])) + " |"
        body = ["| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |" for row in rows[1:]]
        return [header, divider, *body]

    sections = [
        "# Mixalyzer Final Submission Guide",
        "",
        "AI-Powered Marketing Mix Optimization for Growth Teams",
        "",
        "This guide explains MMM/MMX, how to use the Mixalyzer app, and how to present the project for the Harnessing AI for Business final submission.",
        "",
        "## What MMM / MMX Is",
        "Marketing Mix Modeling estimates how marketing channels contribute to revenue over time. It differs from last-click attribution because it looks at aggregate time-series patterns, delayed effects, seasonality, external controls, and diminishing returns. MMM supports better decisions, but it does not prove perfect causality by itself.",
        "",
        "### Key MMM Concepts",
        "",
        *md_table(
            [
                ["Concept", "Business Meaning"],
                ["Channel contribution", "Estimated revenue associated with each channel in the model."],
                ["ROI", "Revenue contribution per marketing dollar spent."],
                ["CAC", "Marketing spend divided by customers or conversions."],
                ["MAPE", "Average forecast error as a percentage."],
                ["Adstock", "Delayed carryover effect from marketing spend."],
                ["Saturation", "Extra dollars eventually produce less incremental revenue."],
                ["Confidence range", "Conservative-to-optimistic estimate around predicted impact."],
            ]
        ),
        "",
        "## How To Use Mixalyzer",
        "Open the app, upload data or use sample data, review readiness, confirm column mapping, set KPI targets, evaluate the model against baselines, review dashboard insights, run simulations, use optimization, review risk, use the pilot plan, and export stakeholder outputs.",
        "",
        *md_table(APP_SECTION_ROWS),
        "",
        "## Final Presentation Narrative",
        "Open with marketing budget waste, define the target customer, explain why AI is appropriate, show the product workflow, demonstrate model evaluation and optimization, discuss responsible AI, and close with strategic business value.",
        "",
        *md_table(PRESENTATION_ROWS),
        "",
        "## Speaker Script",
        "",
    ]
    for part, script in SCRIPT_ROWS[1:]:
        sections.extend([f"### {part}", script, ""])
    sections.extend([
        "## Rubric Mapping",
        "",
        *md_table(RUBRIC_ROWS),
        "",
        f"Generated: {datetime.now().strftime('%B %d, %Y')}",
    ])
    return "\n".join(sections)


def build_pdf():
    OUT_DIR.mkdir(exist_ok=True)
    doc = BaseDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.72 * inch,
        bottomMargin=0.58 * inch,
        title="Mixalyzer Final Submission Guide",
        author="Mixalyzer Project Team",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=header_footer)])

    story: list = []
    add_title_page(story)
    add_mmm_section(story)
    add_app_guide_section(story)
    add_presentation_section(story)
    add_rubric_section(story)
    doc.build(story)
    MD_PATH.write_text(build_markdown(), encoding="utf-8")


if __name__ == "__main__":
    build_pdf()
    print(PDF_PATH)
    print(MD_PATH)
