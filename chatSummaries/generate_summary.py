from fpdf import FPDF

class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

pdf = PDF()
pdf.set_margins(15, 15, 15)
pdf.add_page()
pdf.set_auto_page_break(auto=True, margin=20)

def heading(pdf, text, size=13):
    pdf.set_font('Helvetica', 'B', size)
    pdf.set_text_color(30, 30, 30)
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1)

def subheading(pdf, text):
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(60, 60, 60)
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 6, text)

def body(pdf, text):
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(30, 30, 30)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 6, text)
    pdf.ln(1)

def label(pdf, text):
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, text)
    pdf.ln(1)

def divider(pdf):
    pdf.set_draw_color(200, 200, 200)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

# TITLE BLOCK
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(20, 20, 20)
pdf.multi_cell(0, 9, '3/12/26 - 3/19/26')
pdf.ln(1)
pdf.set_font('Helvetica', 'I', 10)
pdf.set_text_color(80, 80, 80)
pdf.multi_cell(0, 6, 'Topics: Threshold-dependent hydrology, delta-anomaly spatial downscaling, bias correction pipeline design, WEPP watershed modeling')
pdf.ln(2)
pdf.set_font('Helvetica', '', 9)
pdf.set_text_color(100, 100, 100)
pdf.multi_cell(0, 5, 'Chat link: [ENTER LINK HERE]')
pdf.ln(4)
divider(pdf)

# SECTION 1
heading(pdf, 'Threshold-Dependent Processes & Why Extremes Matter')

subheading(pdf, 'Q: What term describes processes that only happen past certain thresholds?')
body(pdf, 'Threshold-dependent processes or threshold effects. In hydrology: exceedance thresholds, critical thresholds, peaks-over-threshold (POT) analysis.')

label(pdf, 'Resonant response:')
body(pdf, '"averages can mask threshold crossings -- two datasets with the same average can have very different extremes, and in a watershed those extremes might be the difference between a flood occurring or not, a channel migrating or staying put, a culvert failing or holding. The phrase often used is that averages obscure the tails, and in threshold-driven systems, the tails are where the action is."')

subheading(pdf, 'Q (self-formulated): "In hydrology there are a lot of responses that only happen past certain thresholds in the data. An average might not capture a passing of one of those thresholds."')
body(pdf, 'Validated. This is an accurate and clear explanation.')

divider(pdf)

# SECTION 2
heading(pdf, 'Delta-Anomaly Method & Bias Correction')

subheading(pdf, 'Q: Is delta-anomaly not considered bias correction?')
body(pdf, 'Yes, it is -- the delta method is a recognized bias correction technique. It only corrects the mean, not the full distribution. Something like quantile mapping corrects bias at every quantile.')

subheading(pdf, 'Q: What time period is monthly_mean_gcm over?')
body(pdf, 'Training period: 1981-2005. The stationarity assumption applied to bias itself -- whatever bias existed historically is assumed to persist into the future.')

subheading(pdf, "Q: Wouldn't doing this for each month have its own problems? You are assuming the gap between a GCM historical month and the future is the same as the gap between observed historical and observed future.")
body(pdf, 'Yes -- this is exactly the stationarity-of-bias assumption. If the GCM bias drifts over time, the correction is wrong. ECDFm partially addresses this by factoring in how the GCM itself changes between historical and future.')

subheading(pdf, 'Q: What does "slope" mean here and what is "departure"?')
label(pdf, 'Resonant response:')
body(pdf, '"Slope = 1.0 means a one-to-one relationship: if the GCM anomaly is 5 degrees above its historical mean, the output is exactly 5 degrees above the observed mean. Nothing is multiplied or shrunk. Departure and anomaly mean the same thing -- how far a value is from its baseline mean."')

subheading(pdf, 'Q: What does "pure" mean, what does "100% extreme preservation" mean, what does "bi-partite" mean?')
body(pdf, '"Pure" = anomaly passes through at slope exactly 1.0, no adjustment. "100% extreme preservation" = direct consequence of slope 1.0, extremes not dampened. "Bi-partite" (from test5) = two separate scaling factors, one for values above the mean (calibrated to 99th percentile) and one for below (calibrated to 1st percentile).')

subheading(pdf, 'Q (catching error): "I\'m looking at the script and bi-partite scaling appears to be associated with continuous variables, not the multiplicative one."')
body(pdf, 'Correct -- the association was backwards. The print statement in test6 explicitly labels continuous variables as Tail-Matched Bi-Partite Scaling.')

divider(pdf)

# SECTION 3
heading(pdf, 'Stochastic Noise')

subheading(pdf, 'Q: Why is he adding noise? What does stochastic mean?')
body(pdf, 'Stochastic means random. The delta-anomaly gives every pixel within a GCM cell a value that is basically the observed climatology plus one shared anomaly -- too clean. Real weather has day-to-day spatial texture.')
label(pdf, 'Resonant response:')
body(pdf, '"The noise adds back natural day-to-day spatial variability. It is spatially correlated (via FFT with a correlation length parameter) so it does not look like TV static -- it looks like smooth regional patterns. The delta-anomaly tells you the regional story; the noise fills in the fine-print."')

subheading(pdf, 'Q: Does adding noise actually bring the data closer to reality or just make it look more realistic? Is it necessary?')
body(pdf, 'Depends on what you are measuring. For watershed-scale aggregates, noise likely washes out. For threshold-dependent processes, noise could push pixels over a threshold that the clean delta-anomaly would have left just below. Whether that is more realistic is an empirical question. Bhuwan may not have tested whether removing it changes anything meaningful.')

divider(pdf)

# SECTION 4
heading(pdf, "Bhuwan's Pipeline & Spatial Downscaling Evolution")

subheading(pdf, 'Key finding: Evolution of scripts (complex to simple)')
body(pdf, 'stage1_dl_super_resolution.py (cGAN, terrain features) -> stage1_ml_downscaling.py (GradientBoosting, terrain) -> test3 (Yeo-Johnson + regression) -> test4/5 (LinearRegression + terrain + bi-partite) -> test6 (pure delta, no terrain, no ML). He tried everything and simplified.')

subheading(pdf, 'Key finding: Bias correction pipeline structure')
body(pdf, 'Current order: multivariate distributional BC at 100km -> interpolate to 4km -> simple delta BC at 4km (test6). The 100km BC compared 8 methods across 5 GCMs including ECC-Schaake, MBCn, R2D2, Gaussian copula, OTBC, Spatial MBC, BCCA. Documented in a full manuscript.')

subheading(pdf, 'Q: Why does test6 still have delta BC if multivariate BC was already done upstream?')
body(pdf, 'QDM corrected the distribution at 100km against coarsened observations. After interpolating to 4km, each pixel has a mean offset from its true 4km observed climatology -- because BC was calibrated to the coarse average. The delta step corrects that mismatch. It is not double-counting.')

subheading(pdf, 'Q: Why not interpolate to 4km first, then apply multivariate distributional BC at 4km?')
body(pdf, 'Theoretically cleaner. Would eliminate the delta step entirely since BC would be anchored to fine-resolution climatology. Computational cost is the practical barrier but manageable with parallelization (~30 min for ECC-Schaake on a gaming PC with 16 cores).')

subheading(pdf, 'Q: Why is interpolation necessary given the boundary problem?')
label(pdf, 'Resonant response (from Claude.ai instance):')
body(pdf, '"Without interpolation you get arbitrary discontinuities between cells where the GCM cell edges used to be. Interpolation corrects a very predictable error, so you are less likely to introduce error in the process."')

divider(pdf)

# SECTION 5
heading(pdf, 'Post-Downscaling BC & What Was Actually Tested')

subheading(pdf, "Q (sharp distinction): \"Those variables require EQM, not the other way around. If the point was to test BC after, why didn't he test other variables with other BC methods?\"")
body(pdf, 'Exactly right. The EQM-after-downscaling in stage1_eqm_postprocessor.py and stage2_dl_2stage.py was reactive -- applied to fix variance collapse in pr and wind caused by ML/DL loss functions, not as a deliberate pipeline design choice.')

label(pdf, 'Resonant response:')
body(pdf, '"Bhuwan never made a deliberate choice that BC-after is better than BC-before. He applied post-downscaling correction exactly once, as a targeted patch for a specific ML failure mode, then moved to a method that did not have that failure mode. The systematic question -- is BC-after better than BC-before as a general pipeline choice, across all variables and methods -- was never posed. That is genuinely unexplored territory in his work."')

divider(pdf)

# SECTION 6
heading(pdf, 'WEPP & Temporal Downscaling')

subheading(pdf, 'Key finding: Where the data goes')
body(pdf, 'The downscaled, bias-corrected data feeds into WEPP (Water Erosion Prediction Project) watershed model runs. Output is thousands of .cli files named by lat/lon coordinate, one per 4km grid point.')

subheading(pdf, 'Key finding: Temporal downscaling is a hard requirement')
body(pdf, 'WEPP .cli files require sub-daily storm breakpoints -- not just daily rainfall totals but how rainfall was distributed within the day (time, cumulative mm pairs). Temporal downscaling from daily GCM output to sub-hourly is not an optional research question but a pipeline necessity. Connects directly to threshold-dependent hydrology: WEPP erosion and runoff calculations depend on storm intensity and timing, not just daily totals.')

pdf.output('C:/Users/elija/drops-of-resilience/chatSummaries/3-12-26_to_3-19-26.pdf')
print('PDF saved successfully')
