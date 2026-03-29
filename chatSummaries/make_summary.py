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
h1("3/22/26 - 3/28/26  |  Topics: lit review refinement, interpolation vs analog-based downscaling, ISIMIP3 comparison, pipeline design justification")
body("Chat link: [ENTER LINK HERE]")
divider()

# -- Section 1: Understanding the pipeline survey table -------------------------
h2("What are 'Constructed analogs', 'Analog regression', and 'B-spline'?")
body("Q: Help me understand the table more. What do 'Constructed analogs', 'Analog regression', and 'B-spline' mean?")
quote(
    "Constructed Analogs -- Instead of interpolating the GCM field to a fine grid, the method looks "
    "at each day's coarse GCM pattern and asks: 'which days in the historical observed record had a "
    "similar large-scale pattern?' It finds the best-matching observed days (the 'analogs') and "
    "constructs the fine-scale output as a weighted combination of those observed days' high-resolution "
    "fields. The spatial detail comes entirely from real observations -- the GCM only provides the "
    "large-scale signal that selects which observed days to use. LOCA refines this by doing the analog "
    "search locally (each region picks its own best-matching days), and MACA adds multivariate "
    "constraints so that temperature and precipitation analogs are selected jointly.\n\n"
    "Analog Regression (GARD) -- A hybrid of the analog approach and traditional regression. Like "
    "constructed analogs, it searches the historical record for days with similar large-scale GCM "
    "patterns. But instead of directly blending those observed days' fine-scale fields, it fits a "
    "regression model using the analog days' data -- learning local statistical relationships. The "
    "regression coefficients from the analog pool are then applied to the current GCM day to produce "
    "fine-scale output. This gives it more flexibility than pure analogs (it can extrapolate slightly "
    "beyond the observed range) while still grounding the spatial structure in observations.\n\n"
    "B-spline (CHELSA) -- A smooth mathematical interpolation method, similar in spirit to bilinear "
    "but higher-order. Bilinear fits a flat plane through the 4 nearest grid points -- piecewise-linear, "
    "continuous but with visible kinks at cell boundaries. B-spline fits a smooth curve (typically cubic) "
    "through a wider neighborhood, producing output that is continuous and has continuous first and "
    "second derivatives -- no kinks. The result is a smoother, more natural-looking field."
)

body(
    "Where they sit on the spectrum:\n"
    "- NN -> bilinear -> B-spline: increasingly smooth interpolation of the GCM field itself (the GCM "
    "values are the output, just spatially refined)\n"
    "- Constructed analogs / analog regression: fundamentally different -- the GCM values are never "
    "interpolated to the fine grid; they're only used as a search key to pull real observed spatial "
    "patterns"
)
divider()

# -- Section 2: Interpolation vs analogs ----------------------------------------
h2("Is interpolation or constructed analogs better? Should Bhuwan switch?")
body(
    "Q: Do you think either interpolation or the constructed analogs method is better than the "
    "other? Where do you think analog regression fits into this? Why do you think Bhuwan chose "
    "interpolation, and do you think he should change this?"
)

quote(
    "Neither approach is strictly better. They solve different problems and have different failure modes.\n\n"
    "Constructed analogs produce more realistic-looking daily fields because the spatial structure is "
    "literally copied from a real observed day. Every ridge, valley, lake effect, and rain shadow is "
    "present because it actually happened. Interpolation can never produce that.\n\n"
    "But analogs have a fundamental limitation: they can only produce spatial patterns that have already "
    "been observed. Under climate change, that's a real problem. If Iowa in 2080 regularly experiences "
    "45C days -- something that has never occurred in the GridMET record -- a constructed analog method "
    "has no template to draw from."
)

quote(
    "Analog regression (GARD) sits in a useful middle ground. By fitting regression models from "
    "analog-selected training data rather than directly pasting observed fields, it can extrapolate "
    "slightly beyond the historical range. But 'slightly' is the key word."
)

h2("Why Bhuwan chose interpolation")
quote(
    "1. Variable coverage. Bhuwan's pipeline handles 11 variables. Analog methods are battle-tested "
    "for temperature and precipitation but much less so for radiation, humidity, pressure, and wind. "
    "Interpolation + per-pixel stochastic calibration works identically for all of them.\n\n"
    "2. Clean separation of concerns. The pipeline has a modular structure: crop -> regrid -> BC -> "
    "stochastic downscaling -> physics correction. Each step has one job. Analog methods merge the "
    "regridding and spatial refinement into one step.\n\n"
    "3. test8 already achieves what analogs aim for, conceptually. Per-pixel observed climatology "
    "(m_obs) supplies the fine-scale spatial structure. The GCM contributes only the daily anomaly. "
    "This is philosophically similar to analogs but implemented per-pixel rather than per-pattern, "
    "with the advantage of extrapolability.\n\n"
    "4. Extrapolation. Delta/ratio mapping naturally handles climate change signals outside the "
    "historical range.\n\n"
    "5. Computational simplicity. Bilinear interpolation of 11 variables is trivial. Analog search "
    "at 4km resolution across 11 variables simultaneously would be orders of magnitude more expensive."
)

h2("Should Bhuwan switch to analogs?")
quote(
    "No. The analog approach's main advantage -- physically realistic spatial fields -- is most "
    "valuable when the interpolation-based alternative produces spatially unrealistic output. But "
    "test8's per-pixel calibration already forces the output to respect observed spatial climatology.\n\n"
    "The actual problems in the pipeline -- PR and wind KGE near zero -- are almost certainly not "
    "caused by the interpolation method. They're more likely rooted in the bias correction or "
    "stochastic model for those specific variables. Switching to constructed analogs wouldn't fix "
    "this and would introduce a whole new set of problems.\n\n"
    "The ISIMIP3 trajectory is instructive: they didn't switch to analogs. They kept interpolation "
    "(bilinear) and added a stochastic redistribution step on top -- which is essentially what "
    "Bhuwan already has. His pipeline is already aligned with where the field is heading."
)
divider()

# -- Section 3: Bilinear as unquestioned convention -----------------------------
h2("Did anyone in the pipeline survey question bilinear besides ISIMIP3?")
body(
    "Q: Across the pipeline survey, did anybody question whether bilinear interpolation was the "
    "right move other than ISIMIP3?"
)
quote(
    "No. ISIMIP3 is the only pipeline in the survey that explicitly evaluated or questioned the "
    "interpolation method.\n\n"
    "Everyone else either:\n"
    "- Used bilinear without discussion. NEX-GDDP and ISIMIP2b state 'bilinear' as a matter of "
    "fact in their technical documentation -- no comparison, no justification, no mention of "
    "alternatives. It's treated as an obvious default choice that doesn't require defending.\n"
    "- Skipped interpolation entirely. MACA, LOCA2, BCCA, BCCAQ2, and GARD all use analog-based "
    "methods. You could read their choice as an implicit critique of interpolation, but none of "
    "them frame it that way.\n"
    "- Used a different smooth interpolation without comparing. CHELSA uses B-spline but doesn't "
    "discuss why they chose it over bilinear.\n"
    "- Listed options without recommending. The BCSD R package supports both bilinear and NN, "
    "defaults to bilinear, and provides no guidance on when to choose one over the other.\n\n"
    "The interpolation method for the coarse-to-fine step is treated as a solved, uninteresting "
    "problem by essentially the entire field. Bilinear is the default and nobody has bothered to "
    "rigorously benchmark it against alternatives -- including ISIMIP3, whose comparison was "
    "qualitative (one visual example, no skill metrics). This is either because it genuinely "
    "doesn't matter much (which our own experiment supports), or because the field has a blind "
    "spot here. Probably some of both."
)

h2("User's synthesis")
body(
    "\"Okay, so essentially, everyone that didn't use some kind of analog-based method used "
    "bilinear, and nobody questioned it except ISIMIP3, who considered Conservative, and they "
    "didn't do any kind of quantitative testing. Their comparison was qualitative - they just "
    "assumed that providing smoother looking data as a starting point for their stochastic "
    "downscaling step would produce better outputs.\""
)
divider()

# -- Section 4: Key lit review conclusions --------------------------------------
h2("Key conclusions from the literature review")
quote(
    "1. Bilinear is the community default, but it is unjustified. Every pipeline that interpolates "
    "uses bilinear, but none present quantitative evidence that bilinear is better than alternatives. "
    "It is an unchallenged convention, not a validated choice.\n\n"
    "2. ISIMIP3 is the only pipeline that questioned the interpolation method. Their comparison "
    "(bilinear vs conservative) was qualitative -- one visual example, no skill metrics. They assumed "
    "smoother input to MBCnSD would produce better output but did not test this. They did not "
    "consider NN.\n\n"
    "3. Our bilinear vs NN comparison is the only quantitative evidence on this question that we "
    "have found. Metrics were equivalent across all non-precipitation variables after stochastic "
    "downscaling.\n\n"
    "4. Why the interpolation method is largely inconsequential in our pipeline: test8's delta "
    "mapping derives spatial structure from per-pixel observed climatology (m_obs), not from the "
    "interpolated GCM field. The interpolated value contributes only the daily anomaly."
)

pdf.output("C:/drops-of-resilience/chatSummaries/3-22-26_to_3-28-26.pdf")
print("PDF written.")
