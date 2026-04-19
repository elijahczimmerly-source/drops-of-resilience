"""Generate chat summary PDF for 4/14/26 - 4/18/26 (chatSummaryInstructions.txt)."""
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


# -- Header ----------------------------------------------------------------------
h1(
    "4/14/26 - 4/18/26  |  Topics: Archiving Attempt 2 under descriptive pipeline id "
    "(test8_pr_tex_att2_b062_rs1); scrubbing test8_v5 strings from 9-fix-pr-splotchiness-attempt-2 "
    "(docs, benchmark CSV, plot filenames); canonical NPZ path experiment_blend0p62_ratio_smooth1p0; "
    "UTF-16 log capture recovery as short stubs; chat summary workflow (this file)"
)
body("Chat link: [ENTER LINK HERE]")
divider()

# -- User question --------------------------------------------------------------
h2("4/18/26 - significant question (word for word)")
body(
    'I still see a whole lot of stuff referencing test8_v5 in '
    "C:\\drops-of-resilience\\9-fix-pr-splotchiness-attempt-2. "
    "You were supposed to rename test8_v5, remember?"
)
divider()

# -- Resonant assistant lines (cleanup scope and verification) ----------------
h2("Assistant lines that resonated (word for word excerpts)")
quote(
    "Renaming artifacts to the canonical pipeline id test8_pr_tex_att2_b062_rs1, updating docs and "
    "logs, replacing CSV pipeline_id values, and renaming archived benchmark PNGs."
)
quote(
    "Replaced LEGACY_TEST8_V5_OUTPUT.md with ARCHIVED_PIPELINE_OUTPUT_PATHS.md, which only describes "
    "pipeline/output/test8_pr_tex_att2_b062_rs1/experiment_blend0p62_ratio_smooth1p0/."
)
quote(
    "A bulk replace was run with WriteAllText (UTF-8) on e2e_suite_run.log and climate_signal_stages.log, "
    "which corrupted the original UTF-16 captures. Those two files are now short UTF-8 stubs that point "
    "at LOG.md, NEGATIVE_RESULT_ATTEMPT2.md, and ARCHIVED_PIPELINE_OUTPUT_PATHS.md. LOG.md notes this "
    "so provenance is clear."
)
quote(
    "Verification: rg test8_v5 under 9-fix-pr-splotchiness-attempt-2 returns no matches."
)
quote(
    "Still using test8_v5 elsewhere (not in that folder): e.g. 6-product-comparison/output/"
    "benchmark_summary_test8_v5.csv, stage_diagnostics_extended.csv, and benchmark_bundle/test8_v5/"
    "run_manifest.json. Say if you want those renamed or regenerated to match the new id; that would be "
    "a separate pass from the archive folder."
)
divider()

# -- Second user message (meta: instructions) ----------------------------------
h2("4/18/26 - follow-up (word for word)")
body(
    'follow the instructions in "C:\\drops-of-resilience\\chatSummaries\\chatSummaryInstructions.txt" '
    "for this chat. Today's data is 4/18/26"
)

out = r"C:\drops-of-resilience\chatSummaries\4-14-26_to_4-18-26.pdf"
pdf.output(out)
print(f"Wrote {out}")
