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
    "4/8/26 - 4/10/26  |  Topics: pipeline home (test8_v3/v4), WDF defaults, dor-info; "
    "START-HERE onboarding; disk cleanup (~820 GB); PR correlation-length sweep "
    "(PLAN-CORR-LENGTH-SWEEP), default pr corr_len 15 px; WDF threshold finalized at 1.65; "
    "RMSE decomposition (why noise-tuning can't close gap to NEX); "
    "cross-variable noise conditioning plan (PLAN-CROSS-VARIABLE-NOISE)"
)
body("Chat link: [ENTER LINK HERE]")
divider()

# -- Earlier thread (pipeline port / naming / dor-info) -------------------------
h2("Earlier session - significant questions (word for word)")
body(
    "Q: Great, I think WDF is good. This should've happened a long time ago, but the pipeline should "
    "not be living in some task folder. Port the pipeline into C:\\drops-of-resilience\\pipeline. "
    "Let's also update the naming scheme for the spatial downscaling scripts: call the last version "
    "with just the .65 blend pr intensity fix test8_v3 and the latest version with "
    "PR_WDF_THRESHOLD_FACTOR = 1.65 test8_v4."
)
body("Q: Update dor info as appropriate")
body(
    'Q: Follow the instructions at "C:\\drops-of-resilience\\chatSummaries\\chatSummaryInstructions.txt" '
    "for this chat"
)
divider()

h2("Earlier session - assistant lines that resonated")
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
divider()

# -- This chat: START-HERE + priorities -----------------------------------------
h2("4/10/26 - user request: follow START-HERE.md")
body(
    "User asked to start from START-HERE.md. Assistant read dor-info.md, bhuwan-info.txt, and "
    "Priorities.txt in order; confirmed repo layout; verified UNC "
    r"\\abe-cylo\modelsdev\Projects\WRC_DOR\ "  # raw string for backslashes
    "(Data/, Spatial_Downscaling/ with Scripts/, test8_v2/) against dor-info spot-check; "
    "no dor-info edit required. Active priority: fix pr RMSE (9-additional-pr-RMSE-fixes/)."
)
divider()

# -- This chat: disk cleanup ----------------------------------------------------
h2("4/10/26 - user request: free space on C: and D: for PR RMSE work")
body(
    "User asked to remove large artifacts from prior tasks not needed for PLAN-CORR-LENGTH-SWEEP. "
    "Assistant removed: NPZ under 4-test8-v2-pr-intensity/output and D:\\WRC_DOR_runs (CSVs/manifests "
    "kept); extra bilinear memmaps/regridded_npy (kept only cmip6_inputs_19810101-20141231.dat, "
    "gridmet_targets_19810101-20141231.dat, geo_mask.npy); entire nearest_neighbor tree on C:; "
    "gridmet_cropped; D:\\Research\\Projects\\WRC\\dor_nn_data (~181 GB duplicate NN data); "
    "D:\\drops-resilience-data\\ec_cmip6_build duplicate. Approx. 820+ GB logical size freed."
)
quote(
    "Tradeoff noted in chat: full parity/blend0p65 NPZ called out in dor-info as previously retained "
    "for benchmarks were deleted; metrics CSVs remain; regenerate or copy from server if arrays needed again."
)
divider()

# -- This chat: autonomous PLAN-CORR-LENGTH-SWEEP --------------------------------
h2("4/10/26 - user request: follow PLAN autonomously with live WORKLOG")
body(
    "Q: Autonomously follow PLAN-CORR-LENGTH-SWEEP.md in 9-additional-pr-RMSE-fixes/; maintain "
    "WORKLOG.md with decisions, non-CSV results, test explanations; exhaust the plan without handing "
    "off steps to the user."
)
body(
    "Implementation: DOR_PR_CORR_LENGTH env in pipeline/scripts/_test8_sd_impl.py (process_variable) "
    "for pr only; tasmin/huss stay 35 px. test8_v4.py lives only under pipeline/scripts/ - "
    "sweep_corr_length.py sets DOR_PIPELINE_ROOT to 4-test8-v2-pr-intensity but invokes repo "
    "pipeline/scripts/test8_v4.py. TEST8_SKIP_NPZ_SAVE added to skip main-period NPZ after metrics "
    "(optional); figures need NPZ so full sweep used normal saves."
)
body(
    "Sweep ran all six values 15,25,35,45,55,70 on local 216x192 bilinear memmaps (~90 min CPU total). "
    "Outputs: output/corr_length_sweep.csv, output/corr_length_findings.md, figures/dor_val_corr_len_*.png."
)
quote(
    "Result: pr RMSE decreased monotonically as correlation length shortened (best 9.903 at 15 px; "
    "9.937 at 70 px). Non-pr Table1 rows identical between corr_len_15 and corr_len_35; wind Ext99 "
    "unchanged across runs. Default pr corr_len when env unset updated from 35 to 15 px per plan success path."
)
quote(
    "Control corr_len=35 in-sweep (RMSE 9.916) did not exactly match older D:\\ experiment_wdf_factor_1p65_216 "
    "(9.910) - treated as code/pipeline-id drift; internal six-way comparison remains valid."
)
divider()

# -- Continued session: WDF finalized at 1.65 ----------------------------------
h2("4/10/26 (continued) - significant questions (word for word)")
body(
    "Q: The results are in. Update the relevant documents and explain"
)
body(
    "Q: We have now come to the part of the task where, once I've seen what looks like successful "
    "results, I need to understand exactly what I've just tested and changed before I talk to Bhuwan. "
    "Please explain what this threshold does, why it was hardcoded at 1.15 before, how we attained "
    "the number 1.5, and why 1.5 makes sense. Also, should we 1. hardcode the threshold at 1.5, "
    "2. keep the sweep_wdf_threshold script to run every time we run our pipeline, or 3. absorb "
    "the logic from sweep_wdf_threshold into the downscaling script?"
)
body(
    "Q: Verify that the new 'best' downscaling script doesn't hurt ANY of the metrics for ANY of "
    "the variables (even if this change is only for pr, the multivariate steps mean changing pr "
    "could change the other variables). Be thorough. Then, if all goes well, plot the pr spatial "
    "map side by side with gridmet (time aggregated)"
)
body(
    "Q: 1.65 seems like the best number to move forward with. Update all the relevant documents "
    "real quick"
)
divider()

h2("4/10/26 (continued) - WDF finalized - assistant lines that resonated")
quote(
    "WDF threshold factor = 1.65 achieves WDF Sim% = 32.337 vs Obs% = 32.317 (+0.02pp). "
    "Ext99 Bias% unchanged at -0.054%. RMSE unchanged at 9.910. This is essentially perfect "
    "WDF matching with zero cost to any other metric."
)
quote(
    "All non-pr variables (tasmax, tasmin, rsds, wind, huss) are byte-identical between the "
    "old factor=1.15 run and the new factor=1.65 run. The threshold only affects pr wet/dry "
    "classification in the noise step."
)
quote(
    "The threshold compensates for an asymmetry: multiplicative noise pushes dry-margin pixels "
    "above the wet-day threshold more easily than it pushes wet-margin pixels below it, because "
    "the noise is proportional to the base value. Factor 1.65 raises the internal threshold so "
    "that the noise-induced false wet days are suppressed."
)
divider()

# -- Continued session: corr_len data mismatch ---------------------------------
h2("4/10/26 (continued) - data path confusion identified")
body(
    "Q: Wait, so which part was wrong/unfaithful to Bhuwan's script?"
)
body(
    "Q: We don't need to re-run, the relative finding still holds. However, I do want you to "
    "update dor info and the plan file and anything else relevant to make sure something like "
    "this never happens again"
)
divider()

h2("4/10/26 (continued) - data path confusion - assistant lines that resonated")
quote(
    "The corr_len sweep ran on local bilinear data (3,999 NaN border pixels) instead of server "
    "Regridded_Iowa (6,147 NaN border pixels). WDF Obs% = 32.547 vs 32.317 confirms the wrong "
    "dataset. Relative comparisons within the sweep are valid but absolute numbers don't match "
    "published benchmarks."
)
quote(
    "Bhuwan's test8_v2.py hardcodes E:\\SpatialDownscaling\\Regridded_Iowa. The refactored code "
    "faithfully reproduces all logic (including np.full(nan) for invalid pixels) but accepts "
    "data paths via env vars - the bug was in the sweep script pointing to local bilinear data, "
    "not in the pipeline itself."
)
quote(
    "Three distinct 216x192 datasets exist: (1) Server Regridded_Iowa (6,147 NaN, WDF Obs% 32.317 "
    "- CORRECT), (2) Local bilinear (3,999 NaN, WDF Obs% 32.547 - WRONG for benchmarks), "
    "(3) Data_Regrided_Gridmet (different grid entirely - WRONG). Updated dor-info.md with "
    "explicit NaN counts and WDF fingerprints for each."
)
divider()

# -- Continued session: RMSE decomposition and cross-variable plan ----------------
h2("4/10/26 (continued) - RMSE gap analysis and cross-variable noise plan")
body(
    "Q: Okay, now let's talk about the relative results we did get. Am I wrong in saying that "
    "this strategy failed to change RMSE significantly enough to beat NEX?"
)
body(
    "Q: Are you SURE we can't beat NEX on RMSE with some other creative strategy that doesn't "
    "hurt Ext99 or something else significantly? Really think outside the box here"
)
body("Q: What is r?")
body(
    "Q: Explain this more, explain what these things are: 'DOR has no idea which pixels are wet "
    "on which days. It gets the climatological pattern right (via spatial_ratio) and the overall "
    "variability right (via noise), but the daily spatial pattern is random.'"
)
body(
    "Q: And this fix you're suggesting, how ambitious is it and how likely is it to work?"
)
body(
    "Q: Could bias correction at a 4km help with any part of this or nah"
)
body(
    "Q: Okay. Take your idea and put it in the planning file. Full explanation, make sure you "
    "articulate the things I found confusing very well. And before the plan, include a full "
    "explanation of why all of those other things are unlikely to improve RMSE and put that "
    "piece in dor info also"
)
divider()

h2("4/10/26 (continued) - RMSE analysis - assistant lines that resonated")
quote(
    "RMSE^2 = 2*sigma^2*(1 - r). With sigma ~ 7.1 mm/day and r ~ 0.025, DOR's RMSE is 9.91. "
    "To match NEX (8.64) while keeping Ext99 perfect, need r ~ 0.26. NEX achieves low RMSE by "
    "compressing variance (Ext99 = -25.3%), not by having better correlation (KGE = 0.002)."
)
quote(
    "The entire noise-optimization budget is 0.7 RMSE (stochastic 9.91 minus deterministic 9.21). "
    "Even perfectly optimized noise cannot reach NEX's 8.64. The corr_len sweep confirmed: best "
    "value improved RMSE by 0.013. The gap to NEX is 1.27. Noise tuning operates on the wrong "
    "term of the decomposition."
)
quote(
    "spatial_ratio captures the long-term climatological pattern - which pixels are wetter on "
    "average over 25 years. The stochastic noise generates realistic day-to-day variability so "
    "the distribution of rain amounts matches observations. But on any given day, which specific "
    "pixels are wet vs dry is essentially a random guess. That's what r ~ 0 means - the daily "
    "spatial pattern is uncorrelated with reality."
)
quote(
    "Cross-variable noise conditioning: the GCM has real daily spatial skill for temperature "
    "(KGE ~ 0.80) and humidity (KGE ~ 0.78). Precipitation is physically tied to these fields - "
    "fronts occur where temperature gradients are strongest, convection where humidity is high. "
    "The idea: use the GCM's temperature/humidity fields to inform WHERE the precipitation noise "
    "puts rain, instead of making it fully random. Blend: alpha * weather_signal + (1-alpha) * "
    "random_noise."
)
quote(
    "Phase 0 feasibility diagnostic: fit obs_pr_anomaly ~ GCM_tasmax + GCM_tasmin + GCM_huss + "
    "GCM_wind + GCM_rsds on training data. If R^2 > 0.05, there's signal worth pursuing. If "
    "R^2 ~ 0, the GCM doesn't carry usable spatial information about precipitation placement "
    "at 4km after regridding from ~100km. The idea is dead - document the gap as a structural "
    "consequence of preserving realistic variance."
)
quote(
    "Bias correction operates on the marginal distribution of each variable independently - it "
    "fixes 'how much rain falls at this pixel over many days' but doesn't address 'which pixels "
    "are wet TODAY.' The r ~ 0 problem is about daily spatial pattern, not distributional bias. "
    "BC can't help here."
)
divider()

out = r"c:\drops-of-resilience\chatSummaries\4-8-26_to_4-10-26.pdf"
pdf.output(out)
print("Wrote", out)
