"""Generate chat summary PDF for 4/12/26 (see chatSummaryInstructions.txt)."""
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
    "4/12/26  |  Topics: PLAN-MULTIVARIATE-SUBGRID-PREDICTION phase renumbering cleanup "
    "(10 bite-sized phases 0-9); variable class rename to dataset-membership terms "
    "(GridMET-and-GCM / GCM-only / GridMET-only / Non-GridMET-observed-only); "
    "bhuwan-info test8_v2 regridding audit (pr = bilinear, others = uncertain); "
    "propagation of regridding finding to dor-info.md and the latest pr RMSE plan"
)
body("Chat link: [ENTER LINK HERE]")
divider()

# -- Continuation of renumbering pass ------------------------------------------
h2("4/12/26 - session opened mid-task: finish phase-renumbering cleanup")
body(
    "Session resumed inside PLAN-MULTIVARIATE-SUBGRID-PREDICTION.md renumbering. Prior splits had "
    "created 10 phases (0 expand, 1 baseline metrics, 2 visual inspection, 3 observation ceiling, "
    "4 interpolation fidelity, 5 Class 3a derivation, 6 Class 3b derivation, 7 Class 2 acquire/verify, "
    "8 GCM prediction, 9 integration). Cleanup pass updated stale cross-references throughout, "
    "renamed scripts (phase2A->phase3A, phase1B->phase3B disambiguated, phase2_interpolation_fidelity"
    "->phase4_, etc.), rewrote Execution order as 10 bite-sized items, rewrote File organization "
    "tree (13 scripts, 7 figure subdirs, 17 output artifacts)."
)
divider()

# -- Question 1: variable class rename -----------------------------------------
h2("4/12/26 - significant question (word for word): class rename")
body(
    'Q: Good. Next change, instead of calling them "GridMet variables", "Non-Gridmet variables", '
    'refer to them as "Gridmet only", "Non-Gridmet Observed Only", "GCM only", or some combination '
    'like "Gridmet and GCM", "Non-Gridmet observed and GCM"'
)
divider()

h2("4/12/26 - class rename - assistant lines that resonated")
quote(
    "Class 1 -> GridMET and GCM (have 4km ground truth AND a GCM equivalent). Class 2 -> GCM only "
    "(GCM field but no GridMET truth, bilinear interp only). Class 3a -> GridMET only (4km truth "
    "but no GCM - e.g. VPD, definitely; rmax/rmin conditional on whether MPI outputs hursmax/hursmin "
    "daily). Class 3b -> Non-GridMET observed only (reanalysis truth only, no GCM, no GridMET - CAPE, "
    "CIN, PWAT, theta-e, lifted index, frontogenesis)."
)
quote(
    "Section header 'Two classes of predictor variables' was itself stale - there are four classes, "
    "not two. Renamed to 'Classes of predictor variables' and updated the opening line to state "
    "variables fall into four classes based on which datasets they appear in (GridMET, GCM, "
    "non-GridMET observed/reanalysis)."
)
quote(
    "Where the doc used 'GridMET variables' to mean Class 1, updated to 'GridMET-and-GCM variables.' "
    "Where it used 'non-GridMET variables' to mean Class 2, updated to 'GCM-only variables.' Phase "
    "scopes (Phases 3, 4, 7), rule statements, and the execution-order summary all now carry the "
    "Class N number alongside the descriptive label as a stable shortcut."
)
divider()

# -- Question 2: test8_v2 regridding audit in bhuwan-info ----------------------
h2("4/12/26 - significant question (word for word): bhuwan-info regridding audit")
body(
    "Q: go through Bhuwan-info.txt to see where he first mentions test8_v2 and see if what "
    "regridding method was used for each variable, including pr"
)
divider()

h2("4/12/26 - regridding audit - assistant lines that resonated")
quote(
    "First mention of test8_v2 is at line 412, where Elijah asks 'How did test8_v2 do on the "
    "metrics? Extremes and WDF?' Bhuwan's reply (lines 414-416): 'It was better. I also used "
    "bilinear interpolation for precipitation. Which worked well for extremes.' So for test8_v2, "
    "pr was switched to bilinear - a change from the prior assumption (lines 200-202) where Bhuwan "
    "said 'for precipitation i believe conservative regriding is required, and we are interpolating "
    "using it's neighbours.'"
)
quote(
    "For the non-pr variables, the file doesn't directly state the test8_v2 method per variable. "
    "The closest is line 479, where Bhuwan says 'bilinear, so it would be comparable with your "
    "test8_v2 run. And I'm not sure about the other variables, let me check' - i.e. Bhuwan himself "
    "wasn't sure what regridding the other variables used in test8_v2 and said he'd check. There's "
    "no follow-up answer in the file."
)
quote(
    "Summary for test8_v2 regridding: pr = bilinear (new in test8_v2, explicit at line 414); "
    "tasmax/tasmin/rsds/wind/huss = bilinear assumed via regrid_to_gridmet.py defaults but NOT "
    "explicitly confirmed - Bhuwan said 'I'm not sure about the other variables, let me check' "
    "(line 479) and never followed up."
)
divider()

# -- Question 3: propagate the finding -----------------------------------------
h2("4/12/26 - significant question (word for word): propagate the finding")
body(
    "Q: Okay, make sure dor info, anything in our bencharking folder, and anything in our latest "
    "plan for fixing pr RMSE reflects this"
)
divider()

h2("4/12/26 - propagation - assistant lines that resonated")
quote(
    "dor-info.md line 54 (pipeline overview) split into 'regrid_to_gridmet.py default: conservative "
    "for PR, bilinear for others' vs 'actually used to produce the test8_v2 inputs: bilinear for "
    "PR (Bhuwan confirmed, bhuwan-info.txt line 414). For the other 5 variables Bhuwan was unsure "
    "and never followed up - assumption is bilinear via the script defaults but not explicitly "
    "confirmed. Any test8_v2-comparable rerun should use bilinear for all variables until Bhuwan "
    "says otherwise.' Line 574 recommendation table already correctly tagged pr as "
    "'Conservative (test8) / Bilinear (test8_v2)' - left as-is."
)
quote(
    "PLAN-MULTIVARIATE-SUBGRID-PREDICTION.md had three stale claims: pipeline overview ('conservative "
    "for pr, bilinear for all others'), Step 0a inventory ('state variable or flux determines "
    "regridding method'), and Step 0b adding new Class 1 ('bilinear for state variables, conservative "
    "for fluxes'). All three updated to note that Bhuwan overrode the script's conservative-for-pr "
    "default to bilinear for the test8_v2 inputs, the state-vs-flux auto-classification is no longer "
    "automatic, and new flux variables should be confirmed with Bhuwan rather than blindly using "
    "the script default."
)
quote(
    "6-product-comparison (the benchmarking folder) - searched README.md, WORKLOG.md, dor-weaknesses.md, "
    "LITERATURE.md, and all scripts. None make per-variable claims about test8_v2 regridding. The "
    "only bilinear/conservative mentions are about NEX-vs-GridMET diagnostics and ISIMIP3 literature, "
    "which are unrelated. No changes needed. 4-test8-v2-pr-intensity/PR_INTENSITY_EXPLAINED.md "
    "already correctly says pr was bilinearly interpolated for test8_v2 (lines 16, 89, 120)."
)
divider()

out = r"c:\drops-of-resilience\chatSummaries\4-12-26.pdf"
pdf.output(out)
print("Wrote", out)
