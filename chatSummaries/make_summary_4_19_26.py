"""Generate chat summary PDF for 4/19/26 (chatSummaryInstructions.txt). Day after last range 4/14-4/18."""
from fpdf import FPDF


class PDF(FPDF):
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


# -----------------------------------------------------------------------------
h1(
    "4/19/26  |  Topics: START-HERE onboarding; native-suite benchmark deltas "
    "(dor_native vs loca2_native vs nex_native, test8_v4 CSVs); "
    "NATIVE_SUITE_METRIC_COMPARISON.md; interpreting cross-suite metrics for DOR vs LOCA2/NEX; "
    "rank flips (PR KGE, PR Lag1); what native suites add beyond GridMET for product evaluation"
)
body("Chat link: [ENTER LINK HERE]")
divider()

h2("Significant questions (word for word)")
body("start in START-HERE.md")
body(
    "Go through 6-product-comparison and give me a detailed account of any metrics that changed "
    "significantly between dor_native and the other two resolution suites"
)
body(
    "put this detailed account in a markdown file in C:\\drops-of-resilience\\6-product-comparison"
)
body(
    "Okay, now explain what these changes MEAN, if anything, for our understanding of how our "
    "(dor) product compares to theirs. Explain in simple terms."
)
body(
    "Make this more concrete. What do the numbers actually mean for comparing our products? "
    "Are there any metrics where they beat us at GridMet resolution but we beat them at their "
    "resolution and what would this mean?"
)
body(
    "I'm not quite getting what I want out of your explanations. I'm looking for you to interpet "
    "the numbers, and, in simple terms, tell me what we learned from benchmarking at LOCA2 and "
    "NEX native resolutions (that we didn't already know from benchmarking at GridMet), that is "
    "USEFUL for evaluating our product"
)
body(
    'Okay, add this to "C:\\drops-of-resilience\\6-product-comparison\\NATIVE_SUITE_METRIC_COMPARISON.md"'
)
body(
    'Update/add to "C:\\drops-of-resilience\\chatSummaries\\4-19-26.pdf" using instructions in '
    '"C:\\drops-of-resilience\\chatSummaries\\chatSummaryInstructions.txt"'
)
divider()

h2("Assistant lines that resonated (word for word excerpts)")
quote(
    "Absolute metric levels are not strictly comparable across suites: shifts mix real skill "
    "differences with regridding, domain footprint, and how extremes behave under interpolation."
)
quote(
    "The largest DOR shifts are wet-day frequency: simulated WDF rises ~1.7-2.3 percentage points "
    "on native grids vs the GridMET mesh, with observed WDF also ~0.5-0.8 pp higher."
)
quote(
    "Lag-1 error falls a lot in relative terms on nex_native: about 0.00389 -> 0.00294 (~-25% of "
    "the error metric). That is the clearest non-PR DOR change that stands out numerically."
)
quote(
    "LOCA2 pr Ext99 is less negative on loca2_native (~+0.7 pp vs GridMET mesh)-a material change "
    "for that metric. Lag1 error worsens ~0.01 on native-grid evaluations vs dor_native."
)
quote(
    "PR KGE vs LOCA2: LOCA2 slightly ahead on GridMET; DOR slightly ahead on loca2_native (tiny "
    "margins). PR Lag1 DOR vs NEX: NEX ahead on GridMET; DOR ahead on nex_native. Ranking flipped."
)
quote(
    "For PR RMSE: on all suites NEX < LOCA2 < DOR - same order. For PR Ext99: DOR closest to zero "
    "everywhere; you beat them on extremes in all three suites."
)
quote(
    "Native suites test: If a reviewer says 'you only look good because you tuned to GridMET on a "
    "4km grid,' we can say the same qualitative comparison mostly holds when obs and fields are "
    "evaluated on LOCA2's or NEX's Iowa footprint-at least for the headline metrics."
)
quote(
    "From GridMET: how DOR stacks up for Iowa GridMET users. From native suites: the same headline "
    "story mostly holds when the scoring grid matches LOCA2 or NEX better; fragile metrics are "
    "flagged; strong conclusions (especially PR: they win RMSE, we win extremes) do not depend on "
    "evaluating only on the 4 km mesh. That stability is the main new, useful result-confidence "
    "that the headline GridMET comparison is not a mesh-only artifact."
)
quote(
    "Native suites are a robustness check on relative performance vs those archives under remapped "
    "GridMET truth, not validation against their training/obs products."
)
divider()

out = r"C:\drops-of-resilience\chatSummaries\4-19-26.pdf"
pdf.output(out)
print(f"Wrote {out}")
