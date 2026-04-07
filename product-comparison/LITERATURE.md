# Literature context for product comparison

This note frames **published** downscaling products and methods relative to the WRC_DOR pipeline. It does **not** claim that tabulated skill metrics from different validation studies are directly comparable to the numbers in `output/benchmark_summary.csv`.

## LOCA2 (Pierce et al., UCSD / SIO)

- **Method:** Localized Constructed Analogs (LOCA2) — fine-scale spatial detail comes from a historical observation library rather than from interpolating the GCM field for temperature and precipitation.
- **Product:** CONUS-scale, ~6 km, CMIP6, documented for NCA5-related applications.
- **Reference:** LOCA2 North America documentation and Pierce et al. (2023) materials linked from [https://loca.ucsd.edu/](https://loca.ucsd.edu/).
- **Caveat vs our pipeline:** Your product applies **OTBC at coarse scale**, **deterministic regrid**, then **stochastic spatial disaggregation** with Schaake shuffle on six variables. LOCA2’s algorithm, training windows, and multivariate structure differ fundamentally; both are “downscaled climate products,” not the same estimator class.

## NASA NEX-GDDP-CMIP6

- **Method / product:** Statistically downscaled CMIP6 projections at fine resolution over CONUS; NASA Earth Exchange (NEX) distribution (Thrasher et al.; see product README and NASA NEX pages).
- **Reference entry point:** [https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6](https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6) (verify current citation text for manuscripts).
- **Caveat:** NEX and LOCA2 use different BC and pattern-generation assumptions than OTBC + your stochastic step; **MPI-ESM1-2-HR** is the common driver in this repo’s benchmark, not a controlled twin experiment.

## ISIMIP3 (Lange 2019, *Geosci. Model Dev.*)

- **Relevance:** Documents a widely cited **bias correct → bilinear interpolate → stochastic refinement** workflow at global scale. Useful for arguing that **interpolation + stochastic adjustment** is a mainstream architecture, distinct from constructed-analog systems.
- **Citation:** Lange (2019), https://doi.org/10.5194/gmd-12-3055-2019 (see also [`bilinear-vs-nn-regridding/nn-regridding-literature-review.md`](../bilinear-vs-nn-regridding/nn-regridding-literature-review.md)).

## How to cite *this* benchmark

Describe it as: **empirical comparison of three MPI-ESM1-2-HR downscaled products on the Iowa GridMET grid (2006–2014)** against **cropped GridMET observations**, using **pooled KGE / RMSE / Ext99 bias / Lag1 error** (and WDF for precipitation), with LOCA2 limited to variables distributed in the LOCA2 archive (here: `pr`, `tasmax`, `tasmin`).
