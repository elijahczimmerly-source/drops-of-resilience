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
h1("3/20/26 - 3/21/26  |  Topics: validation metrics (KGE, RMSE, Ext99, Lag1), bilinear vs NN regridding comparison, interpreting results by variable")
body("Chat link: [ENTER LINK HERE]")
divider()

# -- Section 1: Metric explanations --------------------------------------------
h2("What are KGE and RMSE?")
quote(
    "RMSE (Root Mean Squared Error) -- the average magnitude of error between your simulated and "
    "observed values, in the original units of the variable. Lower is better. Straightforward to "
    "interpret: an RMSE of 7.9 for tasmax means your simulated daily max temperature is off by "
    "-7.9 degrees C on average.\n\n"
    "KGE (Kling-Gupta Efficiency) -- a composite score that breaks error into three components: "
    "correlation, bias, and variability. Ranges from -inf to 1, where 1 is perfect. A score of 0 "
    "means the model is no better than just using the mean observed value as your prediction. "
    "Negative scores mean it's actively worse than that baseline."
)

h2("What is Lag1 Error?")
quote(
    "Lag1 error measures how well the model captures day-to-day persistence -- whether a rainy day "
    "tends to be followed by another rainy day, whether a hot day tends to follow another hot day, "
    "etc. It matters for climate applications because getting the temporal structure right (not just "
    "the mean and variance) affects things like drought duration, heat wave length, and growing "
    "season statistics."
)

h2("What is Ext99 Bias%?")
quote(
    "Ext99 Bias% measures how well the model captures the 99th percentile -- i.e., extreme events. "
    "Closer to 0 is better."
)
divider()

# -- Section 2: What makes a result meaningful ----------------------------------
h2("When does the winning model actually matter?")
body("Q: About how big does the % change have to be for it to be meaningful?")
quote(
    "There's no universal answer -- it depends on the metric. The deeper issue is that 'meaningful' "
    "has two different definitions here:\n\n"
    "1. Statistical -- is the difference larger than what you'd expect from noise? You'd need "
    "repeated runs with different random seeds to answer that properly, and we only have one run each.\n\n"
    "2. Practical -- is the difference large enough to affect downstream decisions? For a stochastic "
    "downscaling pipeline feeding into impact modeling, a 0.5% RMSE difference in tasmax probably "
    "doesn't change any conclusions. A 15% difference in Ext99 Bias% for precipitation might."
)

h2("Does KGE have the same relationship with Ext99 as it does with Lag1?")
quote(
    "No, and that's an important distinction.\n\n"
    "KGE measures day-to-day variability -- how well the model tracks the ups and downs of the time "
    "series. A near-zero KGE means the model is failing at that.\n\n"
    "Ext99 measures the 99th percentile bias -- how well the model captures the magnitude of extreme "
    "events. A model can fail at day-to-day variability (low KGE) but still get the distribution of "
    "extremes roughly right, because Ext99 is about the statistical distribution across the whole "
    "record, not about matching specific days.\n\n"
    "So low KGE doesn't invalidate an Ext99 result the way it casts doubt on a Lag1 result. "
    "Lag1 is about temporal structure -- if the model has no day-to-day skill, its temporal "
    "structure is noise. Ext99 is about distributional properties -- those can be meaningful even "
    "when day-to-day skill is low."
)

h2("Why the pr Lag1 result is uncertain")
quote(
    "The concern is about causality. NN wins on Lag1 for pr -- but why? There are two possible "
    "explanations:\n\n"
    "1. Structural: NN preserves the blocky 100km GCM grid boundaries, which happens to produce "
    "slightly better day-to-day autocorrelation structure in precipitation after stochastic downscaling.\n\n"
    "2. Coincidence: test8 is a stochastic model -- it has random components. If you ran it again "
    "with a different random seed, the Lag1 result might flip.\n\n"
    "When a model is barely better than predicting the mean (KGE -0.02), its internal structure is "
    "largely governed by noise rather than signal. A metric win in that regime is hard to trust."
)

h2("Is RMSE or Ext99 more important for wind?")
quote(
    "For wind specifically, Ext99 is probably more important. Wind extremes matter "
    "disproportionately for applications like storm damage, wind energy, and crop stress -- the tail "
    "behavior is what drives real-world impacts. RMSE weights all days equally, so calm days "
    "(the majority) dominate the score."
)
divider()

# -- Section 3: Final verdicts --------------------------------------------------
h2("Per-variable verdict")
quote(
    "tasmax, tasmin, rsds, huss: No meaningful differences on any metric. NN preferred because it "
    "makes fewer assumptions -- bilinear introduces spatial smoothing that requires justification, "
    "NN does not.\n\n"
    "wind: NN preferred. Wins Ext99 by 2.1pp (more important than RMSE for wind applications).\n\n"
    "pr: NN provisional. Only meaningful result is Lag1 (-9.5%), but low overall KGE means this "
    "needs verification across multiple seeds.\n\n"
    "Overall recommendation: switch to NN for all variables."
)

h2("Why Bhuwan might keep bilinear anyway")
quote(
    "Scientific conservatism. The original pipeline was designed with bilinear for a reason: it "
    "smooths the artificial discontinuities at 100km GCM cell boundaries before downscaling. "
    "That's a defensible physical argument. Bilinear also has precedent in the literature for "
    "this type of coarse-to-fine regridding. NN is more commonly associated with categorical data "
    "or cases where you explicitly don't want to interpolate. A reviewer could reasonably ask "
    "'why NN?' and the answer -- 'the metrics were equivalent so we chose the simpler method' -- "
    "is defensible but less intuitive."
)

pdf.output("C:/drops-of-resilience/chatSummaries/3-20-26_to_3-21-26.pdf")
print("PDF written.")
