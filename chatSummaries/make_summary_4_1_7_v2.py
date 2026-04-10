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
    "4/1/26 - 4/7/26  |  Topics: bias correction validation, BC method comparison, OTBC selection, "
    "physics correction, BCCA tail artifacts, conservative vs bilinear regridding, START-HERE onboarding, "
    "bcv scripts 01-08, MRI NPZ paths, WORKLOG, test8_v2 PR intensity fork, Table1 vs joint metrics, "
    "dor-info PR intensity section; product-comparison validation figures (GridMET vs DOR snapshots, "
    "domain-mean time series, full-window and seasonal aggregated maps), figure folder layout, "
    "interpreting Bhuwan's ask (snapshots vs time-mean maps), plan mode vs implementation, full plot run; "
    "DOR weakness inventory, benchmark metric analysis, visual spatial map interpretation, "
    "pr splotchiness root cause analysis, priority ordering, fix plans for splotchiness/WDF/wind"
)
body("Chat link: [ENTER LINK HERE]")
divider()

# -- Section 1: What is CONUS ---------------------------------------------------
h2("What is CONUS?")
body("Q: What exactly is CONUS?")
quote(
    "Continental United States -- the 48 contiguous states (everything except Alaska and Hawaii). "
    "Bhuwan's full pipeline runs bias correction over that entire domain. Our validation uses just "
    "the Iowa crop."
)
divider()

# -- Section 2: BCCA precipitation tail problem ---------------------------------
h2("BCCA compresses precipitation extremes on Iowa but inflates them on CONUS -- why?")
body(
    "Q: Explain the BCCA thing more. BCCA makes pr smaller at the extremes and Bhuwan said "
    "it would make them bigger?"
)
body(
    "Bhuwan's CONUS result: BCCA P99 Error = +17.95 mm/d (positive -- overestimates extreme "
    "precipitation). Our Iowa result: BCCA P99 bias = -25 mm/d across all 5 GCMs (negative -- "
    "underestimates extreme precipitation). Opposite signs."
)
quote(
    "BCCA (Bias Correction Constructed Analogues) works by expressing each future/validation day "
    "as a linear combination of historical analogue days. That linear blending is the problem -- "
    "when you average together a few historical patterns to reconstruct a day, you smooth out "
    "extremes. The result is a distribution that's compressed toward the middle: the highs "
    "aren't high enough, the lows aren't low enough.\n\n"
    "The sign of the P99 error depends on what you're comparing against. At CONUS scale, BCCA's "
    "analogue blending can inflate extremes because it's blending across a huge spatial domain -- "
    "constructing analogues from geographically diverse patterns can produce locally unrealistic "
    "combinations. On a small Iowa crop, the analogue blending acts purely as a smoother -- "
    "there's not enough spatial diversity for the inflation effect. Instead you just get the "
    "compression artifact."
)
quote(
    "Both results point to the same underlying problem: BCCA badly distorts precipitation tails. "
    "The sign difference is a domain-size effect, not an implementation bug."
)
divider()

# -- Section 3: What problem am I bringing to Bhuwan? ---------------------------
h2("What exactly is the 'problem' to bring up with Bhuwan about BCCA?")
body(
    "Q: I'm a little confused -- what exactly is the 'problem' that I'm bringing up with "
    "Bhuwan? What would he change?"
)
quote(
    "He probably wouldn't change anything. BCCA's tail distortion is already a known finding in "
    "his paper. The manuscript explicitly calls out BCCA as having extreme precipitation artifacts, "
    "and Table 2 shows it has by far the worst P99 error (+17.95 mm/d vs the next worst at "
    "~7.6 mm/d). That's one of the paper's conclusions -- BCCA is not recommended for applications "
    "sensitive to extremes.\n\n"
    "What our Iowa result adds is just a data point showing that the problem gets worse (and flips "
    "direction) at smaller spatial scales. That's mildly interesting for a discussion section "
    "footnote, but it's not a bug and doesn't require a code fix.\n\n"
    "'Red flag' was too strong. BCCA is working as implemented, it's just a bad method for "
    "precipitation extremes. Bhuwan already knows that."
)
quote(
    "The things actually worth bringing to Bhuwan are the positive validation results: that the "
    "method rankings hold up on an independent Iowa subset, the physics corrections eliminate all "
    "tasmax<tasmin violations, and the multivariate methods (Gaussian Copula, OTBC, MBCn) improve "
    "inter-variable dependence as expected. That's the 'yes, you implemented these correctly' "
    "confirmation he asked for."
)
divider()

# -- Section 4: Non-conservative regridding concern -----------------------------
h2("Is the non-conservative GridMET regridding a problem in the production pipeline?")
body(
    "Q: Talk to me about the non-conservative regridding of GridMET from 4-100km. Is this a "
    "problem that made its way into our final pipeline, or was it just done this way while "
    "Bhuwan was comparing BC methods?"
)
quote(
    "Two separate regridding steps in play:\n\n"
    "1. Bhuwan's production pipeline -- To train the bias correction, he needed GridMET "
    "observations on the same ~100km grid as the GCM. His scripts reference pre-made files at "
    "Gridmet-4km-Regrided-to-100km.\n\n"
    "2. Our validation scripts -- bcv_io.py uses scipy linear interpolation to compare BC outputs "
    "to observations. This only affects our metric calculations. It touches nothing in the "
    "actual pipeline.\n\n"
    "Our non-conservative interpolation is only in the validation scripts. It doesn't affect "
    "any data product."
)
divider()

# -- Section 5: What is conservative regridding? --------------------------------
h2("What does 'conservative' regridding mean and why is it more correct?")
body(
    "Q: Can you explain what it would mean for that regridding step to be conservative and how "
    "you know this would be more correct? Also, why exactly can't you figure out how it's done "
    "in the production pipeline?"
)
quote(
    "When you go from 4km to 100km, each coarse cell covers roughly 625 fine cells. There are "
    "two basic approaches:\n\n"
    "Bilinear interpolation: Estimates the value at the coarse cell center by interpolating from "
    "nearby fine-grid points. It's asking 'what's the value at this point?'\n\n"
    "Conservative (area-weighted): Computes the weighted average of all fine cells that overlap "
    "the coarse cell, weighted by how much area they contribute. It's asking 'what's the average "
    "across this whole cell?'\n\n"
    "The difference matters most for spatially heterogeneous fields like precipitation. If it "
    "rains heavily on the west side of a 100km cell but not the east side, bilinear interpolation "
    "at the center might give you a middling value or miss the rain entirely depending on where "
    "the center falls. Conservative regridding gives you the true area-average, which is what a "
    "100km GCM cell actually represents.\n\n"
    "For training bias correction, you want the observation target to represent the same spatial "
    "meaning as the GCM cell. A GCM's 100km precipitation is an area-average, so the observation "
    "it trains against should be too."
)
body(
    "After searching the server, found regrid-gridmet-100km.py in the Spatial Downscaling scripts. "
    "Bhuwan's production regridding uses xESMF with mixed methods:"
)
quote(
    "conservative_normed for precipitation and flux variables (pr, rsds) -- line 304.\n"
    "bilinear for state variables (tasmax, tasmin, huss, wind) -- line 304.\n\n"
    "He was thoughtful about it. Conservative for precipitation makes sense because precip is an "
    "area-integral quantity -- total rainfall over a grid cell should be preserved when you "
    "aggregate. Bilinear for temperature/humidity is reasonable since those are smooth continuous "
    "fields where point interpolation doesn't introduce as much error.\n\n"
    "Bottom line: The production pipeline does not have a non-conservative regridding problem for "
    "precipitation. Bhuwan did it right."
)
divider()

# -- Section 6: Which BC method was selected? -----------------------------------
h2("Which BC method did Bhuwan select for the production pipeline?")
body(
    "Q: What did Bhuwan select as the best BC method that we would move forward with in our "
    "final pipeline?"
)
body(
    "Initially could not determine this from the manuscript (draft has no conclusion section yet) "
    "or from the metric tables (all 8 methods compared equally). Searched the spatial downscaling "
    "pipeline scripts."
)
quote(
    "It's OTBC (Optimal Transport Bias Correction).\n\n"
    "The spatial downscaling pipeline -- test8.py and test8_v2.py -- both explicitly consume "
    "mv_otbc output. The script headers say 'Stochastic Spatial Disaggregation (Post-OTBC)'. "
    "And test8_v2.py line 45 points directly at MPI/mv_otbc as its input directory.\n\n"
    "Looking at the validation metrics, that's a reasonable pick -- it ranks #2 in Frobenius "
    "norm (good inter-variable dependence), #3 in MAE, and #4 in lag-1 error. It's not the "
    "single best on any one metric, but it's consistently near the top across all of them "
    "without any glaring weakness."
)
divider()

# -- Section 7: Plot-by-plot analysis -------------------------------------------
h2("Plot-by-plot validation analysis")
body(
    "Reviewed all 10 validation plots. Key observations that resonated:"
)
body(
    "Bias maps (plots 1-2): All methods look similar -- this is expected and good. All MV "
    "methods start from QDM-corrected marginals; differences between methods show up in "
    "dependence and temporal structure, not mean spatial bias."
)
body(
    "QQ plot (plot 3): QDM and OTBC hug the 1:1 line. BCCA dramatically compresses upper "
    "tail -- observed ~17 mm/d maps to ~6.5 mm/d. Classic analogue-blending artifact."
)
body(
    "Correlation heatmap (plot 4): Mostly pale for OTBC. Largest error is pr-wind (~0.1) "
    "which makes sense -- storm coupling is hard to reproduce. Temperature-humidity pairs "
    "nearly white."
)
body(
    "Compound scatter (plot 5): Point clouds for Obs, QDM, OTBC overlap substantially. "
    "Joint distribution preserved."
)
body(
    "Dry spell KDE (plot 6): All three lines (Obs, QDM, OTBC) on top of each other. "
    "OTBC not disrupting wet/dry sequencing."
)
body(
    "Summary bars (plot 7): BCCA has by far the highest Frobenius error (~1.27). Spatial MBC "
    "second highest (~0.64). Point-wise MV methods cluster low (~0.21-0.22). QDM has lowest "
    "lag-1 error."
)
body(
    "Physics violations (plot 8): Spatial MBC dominates with ~2.5% pre-correction. All others "
    "under 0.15%. Post-correction near zero for most; Spatial MBC retains small residual (~0.5%)."
)
body(
    "Psychrometric scatter (plots 9-10): Very few violations pre-physics, none visible post. "
    "Not much change between the two -- Iowa's climate rarely approaches saturation limits. "
    "Violation rates much lower than CONUS because Iowa is continental and temperate."
)
divider()

# -- Section 8: Spatial MBC residual tolerance ----------------------------------
h2("Why does Spatial MBC still have residual violations post-physics?")
body(
    "Q: Tell me about the small residual orange on Spatial MBC in the violation rate plot."
)
quote(
    "Our validation computes saturation specific humidity using a simple Magnus formula. "
    "Bhuwan's production physics correction uses its own psychrometric routine (in "
    "evaluate_multivariate_v2.py on his machine). If his routine uses slightly different "
    "coefficients, a different formula, or a different assumed surface pressure, then his "
    "saturation threshold is slightly different from ours.\n\n"
    "Spatial MBC shows this more than other methods because it has the most points near the "
    "saturation boundary to begin with (2.5% pre-correction vs <0.15% for most others). "
    "When you have more points crowded near the limit, more of them fall into that tiny gap "
    "between 'Bhuwan's qsat' and 'our qsat.'\n\n"
    "If you wanted to confirm this, you could check whether the residual violations are all "
    "very small in magnitude (huss barely exceeding our qsat by like 1e-4 kg/kg) rather than "
    "large. That would confirm it's a tolerance/formula mismatch, not a correction failure."
)
divider()

# -- Section 9: START-HERE onboarding (later chat) ------------------------------
h2("START-HERE.md: what the agent did first")
body(
    "Q: Start in START-HERE.md.\n"
    "The agent followed the onboarding steps: read dor-info.md, bhuwan-info.txt, and Priorities.txt; "
    "summarized active priorities (spatial downscaling for pr, test8_v2, literature on regridding); "
    "confirmed the server path \\\\abe-cylo\\\\modelsdev\\\\Projects\\\\WRC_DOR\\\\ is reachable and matches "
    "dor-info.md layout (Data/, Spatial_Downscaling/, etc.)."
)
divider()

# -- Section 10: Bias-correction-validation plan implemented --------------------
h2("Bias-correction-validation: full run of plan.md (later chat)")
body(
    "Q: Go follow the plan in bias-correction-validation.\n"
    "The agent implemented the planned pipeline under bias-correction-validation/: bcv_config.py (paths, "
    "MODELS, METHODS, VAR_MAP, 2006-2014 validation window), bcv_io.py (NPZ discovery, validation slice, "
    "Raw yearly concat, GridMET linear interpolation to GCM lat/lon with lon 0-360, obs temperature K to C), "
    "and scripts 01_marginal_checks through 08_summary_table plus run_all.py."
)
body(
    "Key implementation decisions that resonated as fixes: (1) Multivariate historical filenames are not "
    "always 18500101: MRI uses 19000101-20141231. historical_bc_path() uses a glob and prefers 1850 when "
    "multiple matches exist so MRI is not dropped. (2) Cropped qdm has no wind NPZ: marginal/temporal "
    "scripts skip qdm+wind; dependence script omits qdm because it needs six variables. (3) Post-physics "
    "loads BCPC with *_physics_corrected.npz for MV methods; pre-physics uses BC/ only."
)
body(
    "Outputs written to bias-correction-validation/output/: metrics CSVs (01-05), plots PNGs (06-07), "
    "summary_table.csv (08), and findings.md (interpretation and caveats). Full pipeline re-run is long "
    "(on the order of tens of minutes) due to network NPZ reads from Cropped_Iowa."
)
divider()

# -- Section 11: WORKLOG.md ------------------------------------------------------
h2("WORKLOG: ongoing decision log in the repo (later chat)")
body(
    "Q: Keep a log of everything you are doing for this task and why you are making the decisions in the "
    "bias-correction-validation folder.\n"
    "The agent added bias-correction-validation/WORKLOG.md: retrospective table of decisions vs rationale "
    "(interpolation choice, MRI glob, qdm wind, domain-mean Spearman, Magnus q_sat, MPI-only default plots, "
    "etc.), list of artifacts, follow-ups, and a template to append future dated entries at the top."
)
divider()

# -- Section 12: PR intensity - other variables' metrics vs multivariate --------
h2("PR intensity experiment: do non-PR Table1 metrics move when PR moves a lot?")
body(
    "Q: Multivariate processes can depend on PR - check the metrics for the other variables. "
    "(User already knew separate runs differ slightly and that non-PR formulas were not changed.)"
)
body(
    "Resonant answer (short form the user asked for after a long first pass): Only PR uses the "
    "intensity/blend logic. Other variables use the same rules as before. Tiny CSV differences "
    "on tas/wind/etc. are mostly different random draws between runs, not PR 'rewriting' those "
    "variables. Anything that pools all variables in one number must move when PR moves."
)
body(
    "Quantitative read from parity vs experiment V8_Table1_Pooled_Metrics_Stochastic.csv: "
    "PR shifts materially (e.g. KGE on the order of ~15-20% relative, RMSE several percent). "
    "tasmax, tasmin, rsds, wind, huss show only tiny relative shifts (~1e-4 to 1e-3 on KGE/RMSE) - "
    "not proportional to the PR change. So: not a meaningful 'PR drove multivariate Table1' effect "
    "for those per-variable rows."
)
quote(
    "In test8_v2_pr_intensity.py, intensity/blend applies only when var_name == 'pr'. Schaake is "
    "applied per-variable (loop over v), so there is no designed cross-variable formula coupling "
    "from the PR intensity change. Joint / multivariate summaries (e.g. Frobenius-style metrics "
    "over the full stack) still move when PR moves because PR is in the aggregate."
)
divider()

# -- Section 13: dor-info.md - local PR intensity documentation -----------------
h2("dor-info.md updated: Local test8_v2 PR intensity experiment")
body(
    "Q: Update dor-info for PR intensity work (plan: one new section after the bilinear local "
    "pipeline scripts table)."
)
body(
    "Done: added 'Local: test8_v2 PR intensity experiment' with link to "
    "test8-v2-pr-intensity/PR_INTENSITY_EXPLAINED.md; paths for test8_v2_pr_intensity.py, "
    "sweep_pr_intensity_blend.py, output/test8_v2_pr_intensity/; env table "
    "(PR_USE_INTENSITY_RATIO, PR_INTENSITY_BLEND, PR_INTENSITY_OUT_TAG, TEST8_MAIN_PERIOD_ONLY, "
    "TEST8_SEED, DOR_TEST8_V2_PR_INTENSITY_ROOT, DOR_TEST8_PR_DATA_DIR); how to read Table1 vs "
    "joint metrics; no bit-for-bit claim for non-PR across runs without TEST8_SEED alignment."
)
divider()

# -- Section 14: Plan mode / implementation note (this chat) ----------------------
h2("Plan to implementation (PR intensity doc)")
body(
    "User ran a plan to insert the PR intensity section; implementation matched the plan: concise "
    "section, link to PR_INTENSITY_EXPLAINED.md, env names cross-checked to the script docstring, "
    "optional pointer to blend_sweep_results.csv from sweep_pr_intensity_blend.py."
)
divider()

# -- Section 15: Same thread / handoff (PR intensity work) ----------------------
h2("Same conversation window: PR intensity pipeline notes (handoff)")
body(
    "Blend env PR_INTENSITY_BLEND scales (ratio_ext - ratio) * weight when intensity is on, not "
    "r_ext alone; wording for Bhuwan used 'attenuate' when blend is below 1. Sweep script fix: "
    "empty blend_sweep_results.csv still gets a header. Stale lock / resume sweep; PowerShell: "
    "avoid $pid in foreach when stopping processes (use another variable name). Removed legacy "
    "PR intensity comparison folders under bilinear-vs-nn-regridding pipeline output. "
    "PR_INTENSITY_EXPLAINED.md revised for blend-on-delta clarity. Optional ranked metrics extract "
    "and Bhuwan-comparable column tables discussed in thread."
)
divider()

# -- Section 16: Validation-period plots (product-comparison) -------------------
h2("Product-comparison: validation-period figures vs GridMET")
body(
    "Work delivered: shared loader benchmark_io.load_aligned_stacks (align 2006-2014 with "
    "load_obs / load_dor / load_loca2 / load_nex + align_to_obs_with_dates); plot_validation_period.py "
    "for domain-mean daily time series (GridMET, DOR blend 0.65, LOCA2 on pr/tasmax/tasmin only, NEX) "
    "and side-by-side maps. Snapshot dates from config plus calendar day of maximum domain-mean "
    "observed pr."
)
quote(
    "Individual-day maps answer: on real weather, does the field look like the target in pattern "
    "and placement? Time-averaged maps answer: over the validation window, is there a systematic "
    "spatial problem? Hand-picked days are standard for the first; seasonal or full-period means "
    "are common for the second."
)
divider()

# -- Section 17: Figure inventory (partial vs full run) -------------------------
h2("Expected PNG counts vs what was on disk (UNC run interruptions)")
body(
    "Q: What should be in output/figures vs what is there? Expected: six validation_ts_<var>.png, "
    "thirty validation_maps (six variables times five dates), after aggregation twelve more "
    "(six mean + six seasonal). A partial run left only some variables; completing wind and huss "
    "required a targeted second run, then a full script run produced six + thirty + twelve files."
)
divider()

# -- Section 18: How to read the validation plots --------------------------------
h2("What to look for so the validation plots 'look good'")
quote(
    "Time series: co-moving seasonality across products; DOR should track GridMET more closely "
    "than LOCA2/NEX. Red flags: DOR wrong units, out of phase for months, or huge isolated spikes "
    "on one line only."
)
quote(
    "Maps (shared 2-98% color scale): same large-scale pattern left and right on the same day; "
    "for pr, rain where it rains in obs. Red flags: systematic striping only on DOR, arbitrary "
    "flip, one panel mostly NaN, repeatable geographic shift across dates."
)
body(
    "For rsds, large NEX level offset vs GridMET can still be expected (documented elsewhere); "
    "focus on spatial structure and DOR vs GridMET for the pipeline."
)
divider()

# -- Section 19: What Bhuwan likely meant by validation period / side by side -----
h2("Matching Bhuwan's wording: time series vs maps, aggregation")
body(
    "Q: Do these plots match 'plot the VALIDATION PERIOD for each var with the target side by side'?"
)
quote(
    "Strong match if he meant: see the test window with obs next to your fields in space (maps) "
    "and how the period tracks in domain mean (time series). Partial match if he meant every "
    "product (LOCA2, NEX) also gets a map next to GridMET -- maps were DOR-only; LOCA2/NEX on "
    "the time series only."
)
body(
    "Q: Did he want the period without plotting individual days (averaging)? Domain-mean time "
    "series already use every day. Maps need either picked days or temporal aggregation; "
    "averaging over the window for maps is normal and often closer to 'validation period' "
    "wording in space than a single Tuesday."
)
divider()

# -- Section 20: Aggregated side-by-side maps (implementation) --------------------
h2("Time-aggregated GridMET | DOR maps (config + script)")
body(
    "Implemented: FIG_VALIDATION_INDIVIDUAL_DAYS and FIG_VALIDATION_TIME_AGG under "
    "output/figures/dor side-by-side/ (individual days vs time aggregated). "
    "validation_agg_mean_<var>.png = nanmean over full 2006-2014; "
    "validation_agg_seasonal_<var>.png = four rows (DJF/MAM/JJA/SON), each row GridMET | DOR "
    "with per-row 2-98% scaling. Refactor: _pair_vmin_vmax, _save_obs_dor_pair. README and WORKLOG "
    "updated for paths."
)
divider()

# -- Section 21: Plan mode vs 'nothing happened' ---------------------------------
h2("Why the aggregated work was not in the repo yet (plan mode)")
body(
    "Q: What's the problem? Nothing broken -- plan mode had blocked edits until explicit "
    "'go ahead and implement'. Separate issue: script had targeted flat figures/ while snapshots "
    "had been moved into dor side-by-side/individual days/; the plan aligned outputs to that layout."
)
divider()

# -- Section 22: Full plot_validation_period.py run ------------------------------
h2("Regenerate all validation figures: timing and NumPy warnings")
body(
    "Q: Generate those plots. Full run completed successfully (~28.5 min): six time series, "
    "thirty snapshot maps, twelve aggregated maps. Snapshot dates included 2014-09-09 as "
    "high domain-mean pr day."
)
quote(
    "RuntimeWarning: Mean of empty slice on np.nanmean(st.dor, ...) during aggregated steps -- "
    "can indicate slices with no finite DOR values; PNGs still wrote. If DOR panels in agg figures "
    "look flat or empty, trace load_dor/masking; otherwise warnings can be treated as noise or "
    "suppressed with explicit finite checks."
)
divider()

# ===============================================================================
# SECOND CHAT SESSION (4/7/26 continued)
# ===============================================================================

h1("--- Second chat session (4/7/26) ---")
divider()

# -- Section 23: Full DOR weakness inventory from benchmark ----------------------
h2("DOR weakness inventory: every metric where DOR underperforms")
body(
    "Q: Take a look at ALL of the numbers for the benchmarking and take inventory of any and all "
    "places where DOR is weak."
)
body(
    "Agent produced a variable-by-variable comparison of DOR vs LOCA2 vs NEX across every metric "
    "(KGE, RMSE, Bias, Ext99 Bias%, Lag1 Err, WDF), plus per-cell metrics from Table2. "
    "Saved as product-comparison/dor-weaknesses.md."
)
body("Key findings that resonated:")
quote(
    "PR: Ext99 is nearly perfect (+0.13%) -- DOR's standout metric, dramatically better than "
    "LOCA2 (-4.6%) and NEX (-25.3%). But RMSE is worst of three (9.91 vs LOCA2 9.47, NEX 8.64), "
    "WDF overpredicts by +3.4pp, and KGE is ~0 (fundamental GCM limitation, all products have it)."
)
quote(
    "Tasmax: DOR trails both LOCA2 and NEX on KGE (0.801 vs 0.810 vs 0.817) and RMSE "
    "(8.12 vs 7.94 vs 7.73). Small gap but consistent. Wins on Ext99 and Lag1."
)
quote(
    "Tasmin: DOR wins everything -- best KGE, RMSE, Ext99, Lag1."
)
quote(
    "Wind: KGE ~0.08 (near zero, same GCM timing problem as pr). Ext99 -7.5% (dampens extremes). "
    "Still beats NEX on every metric."
)
quote(
    "Structural: multiplicative vars (pr, wind) have near-zero KGE. Consistent warm bias in "
    "tasmax/tasmin. Stochastic noise slightly worsens Lag1 for rsds and huss vs NEX's noise-free "
    "BCSD approach."
)
divider()

# -- Section 24: Overall assessment of DOR quality --------------------------------
h2("Is DOR a good final product?")
body(
    "Q: Where does DOR stand? Is our spatial downscaling a good final product, or do we need to "
    "keep working on it?"
)
quote(
    "DOR is competitive with established products and has a clear win on extreme precipitation -- "
    "the metric that matters most for WEPP/SWAT+. Additive variables (temperature, radiation, "
    "humidity) are strong. The product is publishable but not finished. Pr RMSE and WDF have room "
    "to improve. Diminishing returns on additive variables, but pr still has meaningful room."
)
divider()

# -- Section 25: LOCA2 missing vars clarification --------------------------------
h2("LOCA2 doesn't have rsds/wind/huss (clarification)")
body(
    "Q: When you said DOR 'dominates NEX on rsds, huss, and wind' were you implying DOR is "
    "middle of the road vs LOCA2?"
)
quote(
    "No -- LOCA2 simply doesn't have rsds, wind, or huss data on the server. DOR vs NEX is the "
    "only comparison available for those three, and DOR wins convincingly on all of them."
)
divider()

# -- Section 26: Visual analysis of all plots ------------------------------------
h2("Visual analysis of all benchmark plots (Cursor-generated)")
body(
    "Q: Look at all the plots and tell me what you see."
)
body(
    "Summary charts: KGE bar chart makes the pr/wind near-zero problem visually obvious. PR Ext99 "
    "bias chart is the most compelling single figure -- DOR's bar is invisible (nearly zero) vs "
    "LOCA2 (~-5%) and NEX (~-25%). NEX rsds bias map is uniformly dark red (+20-40 W/m2) across "
    "Iowa."
)
body(
    "Time series: pr is chaotic -- no product tracks observed storm timing. tasmax/tasmin lines "
    "nearly on top of each other across all products. rsds shows DOR hugging GridMET while NEX "
    "rides above. Wind is messy, similar to pr."
)
body(
    "Single-day spatial maps: tasmax/tasmin show broad gradients but visible GCM-cell blockiness "
    "in DOR. PR shows completely different storm placement between DOR and GridMET -- visually "
    "alarming but expected (GCM weather vs real weather). Wind has wrong spatial patterns day-to-day."
)
divider()

# -- Section 27: Single-day maps look bad -- is it? ------------------------------
h2("Why single-day DOR maps look so different from GridMET (and why it's okay)")
body(
    "Q: The single-day maps look pretty bad to me. Is it?"
)
quote(
    "It looks worse than it is. The GCM is simulating its own atmosphere -- it produces its own "
    "storm systems on its own timeline. It's not trying to reproduce what actually happened on "
    "July 25, 2009. When you compare a single day side-by-side, the spatial patterns will look "
    "like two different days -- because they basically are.\n\n"
    "The pipeline isn't designed to get individual days right. It's designed to get the statistics "
    "right -- the right amount of rain over the full period, the right frequency of extreme events, "
    "the right seasonal cycle, the right number of wet days.\n\n"
    "The real question is: does WEPP need the right weather on the right day, or does it need "
    "realistic weather statistics? If it's the latter -- which is the standard use case for "
    "climate projections -- then the maps looking 'wrong' on individual days is expected and "
    "acceptable."
)
divider()

# -- Section 28: Time-aggregated maps look much better ---------------------------
h2("Time-aggregated and seasonal maps: what they show")
body(
    "Q: Cursor made some aggregated-over-time plots. Tell me what you see."
)
body(
    "Time-mean maps (full 2006-2014): tasmax, tasmin, rsds, huss all closely match GridMET spatial "
    "patterns. PR captures the wetter-east/drier-west gradient with correct magnitudes. Wind is "
    "the weakest match -- lacks fine-scale terrain features."
)
body(
    "Seasonal maps: all four seasons (DJF/MAM/JJA/SON) track observed gradients well for "
    "temperature, radiation, and humidity. PR seasonal cycle captured. Wind blockiness persists "
    "across all seasons."
)
divider()

# -- Section 29: User's own observations on the aggregated maps -------------------
h2("User's visual observations on the aggregated maps")
body(
    "User noticed several things the agent had partially missed or described differently:"
)
body(
    "- DOR huss heavier on high extremes, lighter on low extremes vs GridMET in the time-mean")
body(
    "- PR 'splotchiness' (irregular blobs) rather than 'blockiness' (GCM cell squares) in "
    "time-mean maps -- distinct from the single-day GCM-cell artifacts")
body(
    "- Tasmax and tasmin both light on lower temperatures at the top (north) of the domain -- "
    "a systematic warm bias concentrated in the north")
body(
    "- Same northern warm bias appears in huss (temperature-dependent)")
divider()

# -- Section 30: What the visual observations mean --------------------------------
h2("Interpreting the visual observations: GCM gradient + stochastic noise artifacts")
body("Q: What does all of this mean?")
quote(
    "Northern warm bias (tasmax, tasmin, huss): MPI has a weaker-than-observed north-south "
    "temperature gradient over Iowa. The delta-mapping preserves whatever gradient the GCM "
    "produces, so this is inherited from the GCM through the bias correction. Not a downscaler "
    "problem."
)
quote(
    "PR splotchiness: the stochastic noise has a spatial correlation length of 35 pixels for pr. "
    "When you average thousands of days of multiplicative noise, those spatially correlated noise "
    "patterns don't perfectly cancel out -- they leave residual splotches. This is a real artifact "
    "of the stochastic step. GridMET doesn't have this because it's observed data."
)
divider()

# -- Section 31: Root cause of pr splotchiness ------------------------------------
h2("Root cause analysis: exactly what creates the pr splotchiness")
body(
    "Q: What exactly would need to be done to fix the pr splotchiness?"
)
body(
    "Agent traced the full causal chain through test8_v2_pr_intensity.py code:")
body(
    "1. Asymmetric clip [0.1, 8.5] on noise multiplier (line 535): downside capped at -90%, "
    "upside at +750%. At high-CV pixels, left tail gets truncated more than right, making "
    "E[noise_mult] > 1.0.")
body(
    "2. WDF threshold censoring (lines 540-543): removes small positive values but can't remove "
    "large ones. Creates spatially varying upward bias at dry-but-variable pixels.")
body(
    "3. AR(1) persistence (rho=0.5, line 528): positive noise excursions persist over multiple "
    "days, compounding the clip and WDF asymmetries.")
body(
    "4. 35px correlation length (line 590): sets the spatial scale of the resulting splotches -- "
    "the noise kernel footprint made visible by the biases that prevent cancellation.")
quote(
    "Recommended fix: empirical per-pixel noise debiasing. After calibration, run the noise "
    "multiplier chain forward on the training period and record the per-pixel mean effective "
    "multiplier. Divide by this during inference, forcing the long-run mean to 1.0 everywhere. "
    "Preserves Ext99 (individual-day multipliers unchanged), Lag1 (AR(1) structure unchanged), "
    "and the heavy tail.")
divider()

# -- Section 32: Priority ordering discussion ------------------------------------
h2("Priority ordering: what to fix and in what order")
body(
    "Q: User proposed priorities: 1. pr RMSE/KGE, 2. splotchiness, 3. tasmax, 4. wind."
)
body("Agent reordered and triaged:")
quote(
    "1. Splotchiness first (not second) -- fixes systematic spatial bias that inflates pr RMSE. "
    "Must be in place before other pr tuning.\n"
    "2. WDF overprediction (+3.4pp) -- next actionable pr weakness after splotchiness.\n"
    "3. PR KGE is NOT ACTIONABLE -- fundamental GCM limitation, all products have it.\n"
    "4. PR RMSE beyond the splotch fix is also mostly not actionable.\n"
    "5. Tasmax gap (1-2%) is inherited from GCM/BC, not the downscaler. Document, don't fix.\n"
    "6. Wind: not originally prioritized, but Bhuwan later requested it be worked on."
)
quote(
    "Key insight: splotch fix applies to both pr and wind (shared multiplicative pathway). "
    "All three plans (splotch, WDF, wind) must be separate test runs. Splotch first because "
    "it changes the baseline for WDF tuning."
)
divider()

# -- Section 33: Plans created ---------------------------------------------------
h2("Fix plans created")
body(
    "Three plan documents written:")
body(
    "7-fix-pr-splotchiness/PLAN.md: detailed root cause (4 mechanisms with code line references), "
    "the fix (empirical per-pixel noise debiasing in calibrate()), scoping (pr + wind, not additive "
    "vars), 5-step implementation (diagnostic baseline, debiasing calibration pass, apply in "
    "downscale_day, validate, sensitivity check), 4 alternatives considered (log-space noise, "
    "reduce noise factor, symmetric clip, separate occurrence model).")
body(
    "8-WDF-overprediction-fix/PLAN.md: noise-threshold interaction diagnosis (noise pushes dry days "
    "above threshold asymmetrically), the fix (noise-aware Monte Carlo threshold calibration using "
    "50 noise samples per training day -- calibrate against noisy distribution instead of "
    "deterministic sim_base), removes need for PR_WDF_THRESHOLD_FACTOR fudge, target <1pp WDF error. "
    "Must run after splotch fix.")
body(
    "10-improve-wind/PLAN.md: two phases. Phase 1 (low risk): separate wind noise factor, sweep "
    "0.16-0.30 to fix Ext99 -7.5% underprediction. Phase 2 (moderate risk): apply monthly "
    "WindEffect terrain modulation fields from server (1681x1921 multiplicative factors, range "
    "0.74-1.35) to inject sub-GCM spatial structure. Need to ask Bhuwan why USE_GEO_STATIC is "
    "currently disabled before implementing Phase 2.")
divider()

# -- Section 34: DJF/MAM/JJA/SON explained ---------------------------------------
h2("What DJF, MAM, JJA, SON mean")
body(
    "Q: What do DJF, MAM, JJA, SON mean?\n"
    "DJF = Dec/Jan/Feb (winter), MAM = Mar/Apr/May (spring), "
    "JJA = Jun/Jul/Aug (summer), SON = Sep/Oct/Nov (fall)."
)
divider()

# -- Section 35: Files updated ---------------------------------------------------
h2("Files updated in this session")
body(
    "- product-comparison/dor-weaknesses.md (new: full weakness inventory)\n"
    "- dor-info.md (benchmark results summary, visual spatial analysis, restructured Open Questions "
    "into Active/Not Actionable/Completed, BC Data paths updated for new server layout, "
    "wind improvement item added)\n"
    "- Priorities.txt (rewritten with new ordering: splotch fix > WDF > wind > not-actionable items)\n"
    "- 7-fix-pr-splotchiness/PLAN.md (new)\n"
    "- 8-WDF-overprediction-fix/PLAN.md (new)\n"
    "- 10-improve-wind/PLAN.md (new)"
)
divider()

pdf.output("C:/drops-of-resilience/chatSummaries/4-1-26_to_4-7-26.pdf")
print("PDF written.")
