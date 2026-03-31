from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        pass
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

pdf = PDF()
pdf.set_margins(20, 20, 20)
pdf.add_page()
pdf.set_auto_page_break(auto=True, margin=20)

def h1(text):
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.ln(4)
    pdf.multi_cell(0, 8, text)
    pdf.ln(2)

def h2(text):
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(60, 60, 60)
    pdf.ln(3)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1)

def body(text):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 6, text)
    pdf.ln(2)

def quote(text):
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(60, 80, 60)
    pdf.set_x(26)
    pdf.multi_cell(pdf.w - 46, 6, text)
    pdf.set_text_color(40, 40, 40)
    pdf.ln(1)

def divider():
    pdf.set_draw_color(200, 200, 200)
    pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
    pdf.ln(3)

# -- Header ---------------------------------------------------------------------
h1("3/29/26 - 3/31/26  |  Topics: pr 3-way regridding comparison, RMSE smoothing paradox, stochastic threshold instability, meaningfulness of within-poor-tier differences")
body("Chat link: 619b05f0-13f7-4472-8bf7-304423d21697")
divider()

# -- Section 1: Per-metric tier shading -----------------------------------------
h2("Understanding the per-metric tier shading system")
body(
    "Q: \"In the regrid_comparison_report.html table, the shading in the rows to the right "
    "of the variable column represented the performance for the individual metrics. The shading "
    "in the variable column represented the variable's overall performance across all metrics. "
    "So, in this original table, RMSE and Ex99 for wind were shaded yellow representing moderate "
    "performance, but overall performance was determined to be poor, so the shading on the left "
    "was red. Similarly, lag1 error for huss was moderate performance, but the shading on the "
    "left was green. This was a good system, I liked this.\""
)
body(
    "The combined report had lost the per-metric row shading, replacing it with a single color "
    "per variable. The original system had two layers: individual metric rows were shaded by "
    "that metric's tier (good/moderate/poor), while the variable column used an overall tier. "
    "This was fixed to match the original."
)
divider()

# -- Section 2: Stochastic threshold instability --------------------------------
h2("Why the chart changed between pipeline runs (stochastic threshold instability)")
body(
    "Q: \"You're right, those charts are actually from different pipeline runs, though I "
    "thought they'd be pretty much the same despite the stochastic bits. RMSE for tasmin "
    "and lag1 for rsds are now no longer hatched (meaning they're considered meaningful "
    "now and weren't before). Determine if this is correct, and what it means.\""
)
quote(
    "Both are borderline cases right at their respective meaningfulness thresholds "
    "(0.5% for RMSE, 5.0% for Lag1). The logic is identical between runs -- the "
    "is_meaningful function hasn't changed. The stochastic component of test8 introduced "
    "tiny variations that pushed these two metrics from just-below to just-above the cutoff.\n\n"
    "tasmin RMSE diff: 0.501% (threshold: 0.5%)\n"
    "rsds Lag1 diff: 5.57% (threshold: 5.0%)\n\n"
    "This actually underscores exactly what the hatching system is designed to communicate: "
    "these differences between NN and bilinear for tasmin RMSE and rsds Lag1 are negligible "
    "in practice. They're right at the boundary where run-to-run noise can flip the "
    "classification either way."
)
divider()

# -- Section 3: The RMSE smoothing paradox for precipitation --------------------
h2("RMSE smoothing paradox: bilinear 'wins' RMSE for pr by being worse")
body(
    "Q: \"In Figure: same 2x2 layout, precipitation three-way (vs bilinear reference), "
    "for RMSE the conservative and nn bars are red, indicating that they are WORSE than "
    "bilinear. These are also the only non-hatched bars, indicating that this is the only "
    "meaningful metric. Is this correct?\""
)
body(
    "Q: \"This is quite surprising to me. Typically, we use conservative specifically for "
    "pr and bilinear for everything else, because conservative is supposed to make more "
    "physical sense than bilinear specifically for pr. Also, the summary at the top of "
    "the report says... 'Bilinear is notably worse for pr... Recommendation: For "
    "precipitation, use either conservative or NN; avoid bilinear.' What's going on here?\""
)
quote(
    "Bilinear smooths the rainfall field. Smoothing dampens extremes and reduces variance. "
    "RMSE penalizes large errors quadratically, so a smoother/blander prediction will have "
    "lower RMSE -- even though it's systematically underpredicting extreme events. This is "
    "a well-known limitation of RMSE: it can reward 'playing it safe' and producing a bland "
    "average rather than capturing the actual distribution.\n\n"
    "The tier system classifies KGE, Ext99, and Lag1 all as 'poor' for pr (best values "
    "across all methods still don't clear the moderate thresholds), so it hatches them as "
    "'not meaningful.' The logic is: if no method can model this metric well, the difference "
    "between methods doesn't matter. That's a reasonable general principle, but for pr it "
    "obscures the key finding -- bilinear is systematically worse on the metrics that matter "
    "most for precipitation (extremes, autocorrelation, overall skill), and its lone "
    "'advantage' (RMSE) is an artifact of the very smoothing that causes those other problems."
)
divider()

# -- Section 4: Challenging within-poor-tier significance ------------------------
h2("Critical pushback: do within-poor-tier differences actually matter?")
body(
    "Q: \"I hear what you're saying about RMSE not being as important as extremes for pr, "
    "but you fail to explain why it should matter that 'bilinear is systematically worse "
    "on the metrics that matter most for precipitation' when KGE, Ext99, and Lag1 are all "
    "poor for pr anyway.\""
)
quote(
    "The tier system's logic is straightforward: if the best performer on a metric can't "
    "even reach 'moderate,' then distinguishing between flavors of 'poor' isn't actionable. "
    "And that's exactly the situation for pr:\n\n"
    "- KGE: Best is 0.029. 'Moderate' starts at 0.30. All three methods are an order of "
    "magnitude away from being useful. The 0.005 difference is noise within a bad result.\n"
    "- Ext99: Best is |13.3%|. 'Moderate' starts at <=10%. All three substantially "
    "underpredict extremes.\n"
    "- Lag1: Best is 0.017. 'Moderate' starts at <=0.015. Close, but still all poor.\n\n"
    "So the chart is actually telling the more defensible story: for precipitation, no "
    "regridding method produces good post-stochastic metrics, and the one metric where you "
    "can detect a meaningful difference (RMSE) slightly favors bilinear."
)
body(
    "This corrected the earlier overstatement. The original summary had said \"avoid bilinear\" "
    "for pr based on within-poor-tier differences. The revised understanding:"
)
quote(
    "The conventional wisdom that conservative is better for pr is a physical/theoretical "
    "argument (conservative preserves mass/flux totals across grid cells), not one that the "
    "empirical post-test8 metrics here are able to confirm or deny -- because test8's "
    "stochastic downscaling overwhelms the regridding signal for precipitation regardless "
    "of method."
)
body(
    "Updated recommendation: conservative remains the standard choice for pr on physical "
    "grounds, but the empirical metrics do not strongly differentiate the methods -- they "
    "offer no reason to deviate from conventional practice, but also no strong empirical "
    "evidence that the choice matters post-test8."
)
divider()

# -- Section 5: WDF and qualitative plot utility ---------------------------------
h2("WDF (Wet Day Frequency) and qualitative plot utility")
body(
    "Q: \"What are WDF Obs% and Sim%?\""
)
body(
    "WDF = Wet Day Frequency. Percentage of days where precipitation >= 0.1 mm/day. "
    "WDF_Obs% is from observed GridMET data, WDF_Sim% is from stochastic downscaled output. "
    "Observed ~32.4%, simulated ~38.3% across all methods -- test8 consistently overpredicts "
    "wet day count by ~6 percentage points regardless of regridding."
)
body(
    "Q: \"Do you think the NN-bilinear plots are actually useful and if so what for?\""
)
quote(
    "For the five non-pr variables, the NN-vs-bilinear pre/post plots serve a specific "
    "purpose: they let you visually confirm what the quantitative metrics already say -- "
    "that the spatial patterns are nearly indistinguishable between methods. That's a useful "
    "sanity check for a supervisor reviewing the work, but they don't convey information "
    "beyond what the metrics tables already tell you. In terms of analytical value: modest. "
    "They're confirmatory visual evidence, not discovery tools."
)

pdf.output("C:/drops-of-resilience/chatSummaries/3-29-26_to_3-31-26.pdf")
print("PDF written.")
