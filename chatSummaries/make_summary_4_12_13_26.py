"""Generate chat summary PDF for 4/12/26-4/13/26 per chatSummaryInstructions.txt."""
from __future__ import annotations

from fpdf import FPDF


class PDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def main() -> None:
    pdf = PDF()
    pdf.set_margins(18, 16, 18)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    def h1(text: str) -> None:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(28, 28, 28)
        pdf.multi_cell(0, 8, text)
        pdf.ln(2)

    def topics(text: str) -> None:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(70, 70, 70)
        pdf.multi_cell(0, 6, text)
        pdf.ln(2)

    def link_line(text: str) -> None:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, text)
        pdf.ln(3)

    def h2(text: str) -> None:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(50, 50, 50)
        pdf.ln(2)
        pdf.multi_cell(0, 7, text)
        pdf.ln(1)

    def q(text: str) -> None:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(35, 35, 90)
        pdf.multi_cell(0, 6, "Q: " + text)
        pdf.ln(1)

    def body(text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(0, 6, text)
        pdf.ln(2)

    def resonant(text: str) -> None:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(55, 75, 55)
        pdf.set_x(pdf.l_margin + 4)
        pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 4, 6, text)
        pdf.ln(2)

    def div() -> None:
        pdf.set_draw_color(210, 210, 210)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(4)

    # --- Title ---
    h1("4/12/26 - 4/13/26")
    topics(
        "Topics: repo gitignore & benchmark figures; LOCA2/NEX resolution & 6-product data flow; "
        "regrid interpolation (server xarray-regrid vs scipy); climate-change signal vs validation benchmark; "
        "pipeline entry points (test8_v2/v3/v4, _test8_sd_impl, regrid under pipeline/); dor-info clarifications"
    )
    link_line("Chat link: [ENTER LINK HERE]")
    div()

    h2("Significant questions (verbatim)")
    q("I tried to push the repo to github and pull onto my laptop for a web meeting, and I noticed that some stuff, including my plots, were missing from 6-product-comparison. It probably has something to do with .gitignore... Make sure the plots are going, and see if anything else needs to be changed with the .gitignore thing")
    q("What are the two scripts I just opened in Cursor")
    q('What about "...\\Downloads\\Compare_All_Signals_Iowa_Parallel.py"')
    q("Is \"signal\" the climate change signal?")
    q("Just to clarify, is crop_loca2_iowa_MPI.py actually changing the resolulution of LOCA2?")
    q("Bilinear interpolation or something different?")
    q("Find regrid_to_gridmet.py in the server. Is the interpolation the same?")
    q("Other than for precipitation? Is the bilinear interpolation the same?")
    q("What resolution is (4km, 100km, etc) are LOCA2 and NEX at by default? You may need to look through 6-product-comparison to find the answer")
    q("Did my benchmarking include how our outputs preserve the climate change signal?")
    q("Where is the regridding script (or scripts)? And is test8_v2 (the script created by Bhuwan before my iterations, should still be in the server) on my PC at all?")
    q("What regridding scripts were used for 6-product-comparison and what exactly are _test8_sd_impl.py and dor_test8_lock.py")
    q("So if 6-product-comparison doesn't run regridding scripts, where is it getting regridded data (filepath please!) and what script was used to regrid THAT data? And ... is pipeline set up to do a run that is the equivalent of test8_v2, as it is clearly set up to do test8_v3 and v4")
    q("Plan: test8_v2 entry point + pipeline regridding scripts - Implement the plan as specified... To-dos from the plan have already been created...")
    q('Make sure pipeline/scripts/regrid/regrid_to_gridmet_bilinear.py is actually bilinear for all variables real quick')
    q("Great. Update dor info to minimize future confusion on the stuff that I had to ask about in this chat")
    q("Follow chatSummaries/chatSummaryInstructions.txt for 4/13 for everything in this conversation")
    div()

    h2("Responses that resonated (deduced; excerpts)")
    resonant(
        "6-product-comparison/output/.gitignore contained *.png - that excluded all benchmark figures; "
        "root .gitignore only ignores .dat / .npy / .npz and pipeline data dirs, not PNGs."
    )
    resonant(
        "Compare_All_Signals_Iowa_Parallel.py: parallel V8 vs LOCA2 vs GridMET; "
        "'signal' in process_future_var = future vs historical change (SSP window vs baseline), "
        "i.e. climate change signal in that script's sense."
    )
    resonant(
        "crop_loca2 uses scipy RegularGridInterpolator default linear - 2D multilinear / bilinear; "
        "not crop-only: it interpolates onto the 216x192 target grid."
    )
    resonant(
        "Server regrid_to_gridmet.py: pr -> conservative via xarray-regrid; other vars -> .linear() "
        "(bilinear). For tas/tmin etc., same mathematical family as scipy linear on lat-lon; "
        "pr differs from crop_loca2 which uses linear for pr too."
    )
    resonant(
        "LOCA2 ~6 km (per LITERATURE.md); NEX-GDDP-CMIP6 native grid 0.25 deg x 0.25 deg; benchmark "
        "interpolates all products to GridMET for comparison."
    )
    resonant(
        "run_benchmark.py only compares 2006-2014 vs GridMET - it does not assess preservation of "
        "a climate change signal (future minus historical)."
    )
    resonant(
        "No file named test8_v2.py in repo as Bhuwan's exact upload; local pipeline uses "
        "_test8_sd_impl.py + test8_v3/v4 (and after implementation, test8_v2.py entry). "
        "Regridding harness lived under 3-bilinear; canonical copy under pipeline/scripts/regrid/."
    )
    resonant(
        "6-product-comparison: DOR from NPZ already on GridMET grid; LOCA2/NEX regridded in load_loca2 / "
        "load_nex via xarray .interp - not by running regrid_to_gridmet inside that folder."
    )
    resonant(
        "regrid_to_gridmet_bilinear.py: REGRID_METHOD all \"bilinear\"; regrid_var maps bilinear to "
        "src_da.regrid.linear(dst_grid_ds)."
    )

    out = r"C:\drops-of-resilience\chatSummaries\4-12-26_to_4-13-26.pdf"
    pdf.output(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
