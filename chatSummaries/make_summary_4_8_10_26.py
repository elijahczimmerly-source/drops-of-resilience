"""Generate chat summary PDF for 4/8/26 - 4/10/26 (see chatSummaryInstructions.txt)."""
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
h1(
    "4/8/26 - 4/10/26  |  Topics: canonical spatial-downscaling pipeline home, test8_v3 vs test8_v4 "
    "naming, WDF defaults (1.15 vs 1.65), repo-wide script and config path updates, dor-info refresh"
)
body("Chat link: [ENTER LINK HERE]")
divider()

# -- User questions (word for word) ----------------------------------------------
h2("Significant questions (word for word)")
body(
    "Q: Great, I think WDF is good. This should've happened a long time ago, but the pipeline should "
    "not be living in some task folder. Port the pipeline into C:\\drops-of-resilience\\pipeline. "
    "Let's also update the naming scheme for the spatial downscaling scripts: call the last version "
    "with just the .65 blend pr intensity fix test8_v3 and the latest version with "
    "PR_WDF_THRESHOLD_FACTOR = 1.65 test8_v4."
)
body('Q: Update dor info as appropriate')
body(
    'Q: Follow the instructions at "C:\\drops-of-resilience\\chatSummaries\\chatSummaryInstructions.txt" '
    "for this chat"
)
divider()

# -- Resonant LLM lines (deduced acceptance) --------------------------------------
h2("Assistant responses that appeared to resonate (substance retained)")
quote(
    "Canonical implementation: pipeline/scripts/_test8_sd_impl.py - run via test8_v3.py "
    "(default PR_WDF_THRESHOLD_FACTOR 1.15, blend 0.65) or test8_v4.py (default 1.65). "
    "Outputs under <DOR_PIPELINE_ROOT>/output/test8_v3|test8_v4/."
)
quote(
    "Deprecated wrapper 4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py delegates to v4 "
    "and keeps DOR_PIPELINE_ROOT on the task folder when unset so old relative paths still resolve."
)
quote(
    "Sweeps and tooling (WDF sweep, blend sweep, ratio-smooth sweep, dump_noise_bias, "
    "product-comparison config) updated to pipeline paths and test8_v4 output tree; "
    "dor-info.md documents pipeline/, v3 vs v4, DOR_PIPELINE_ROOT, and benchmark path "
    "pipeline/output/test8_v4/experiment_blend0p65/."
)
quote(
    "Historical runs may still live under 4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/; "
    "set DOR_PRODUCT_ROOT if needed until outputs are regenerated under pipeline/."
)

out = r"c:\drops-of-resilience\chatSummaries\4-8-26_to_4-10-26.pdf"
pdf.output(out)
print("Wrote", out)
